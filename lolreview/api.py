import logging
import os
import statistics
import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from lolreview import replay, riot, worlds
from lolreview.cache import Cache, default_path
from lolreview.config import ROOT, load_config, read_env
from lolreview.constants import (
    PLATFORM_TO_CLUSTER,
    QUEUE_RANKED_SOLO,
    REMAKE_MAX_S,
    TIER_INDEX,
    TIERS,
)
from lolreview.ddragon import DataDragon
from lolreview.patterns import patterns_of
from lolreview.schemas import (
    DemoPlayer,
    ErrorResponse,
    GameSummary,
    Health,
    ModelInfo,
    ModelMetrics,
    Patterns,
    Player,
    PlayerGames,
    Rank,
    ReplaySeek,
    ReplaySeekResult,
    ReplayStatus,
    Review,
    WorldsLive,
    WorldsMatches,
)

log = logging.getLogger(__name__)

DEV_ORIGIN = "http://localhost:5173"
DEFAULT_TIER = "SILVER"
DEMO_REPLAY_REASON = "Replays aren't available in demo mode"
PATTERNS_MAX_GAMES = 50
SPARK_POINTS = 12
REVIEW_FORMAT = 6  # bump when the Review JSON gains fields, so older cached reviews are rebuilt


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after_s: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after_s = retry_after_s


def _error_response(err: ApiError) -> JSONResponse:
    body = ErrorResponse.model_validate(
        {
            "error": {
                "code": err.code,
                "message": err.message,
                "retry_after_s": err.retry_after_s,
            }
        }
    )
    return JSONResponse(status_code=err.status, content=body.model_dump(mode="json"))


def _from_riot_error(exc: riot.RiotError) -> ApiError:
    if isinstance(exc, riot.KeyMissingError):
        return ApiError(401, "key_expired", "No Riot API key. Put one after RIOT_API_KEY= in .env.")
    if isinstance(exc, riot.KeyExpiredError):
        return ApiError(401, "key_expired", "The Riot API key was rejected.")
    if isinstance(exc, riot.RateLimitedError):
        return ApiError(
            429, "rate_limited", "Riot's rate limit is full.", max(1, round(exc.retry_after_s))
        )
    if isinstance(exc, riot.NotFoundError):
        return ApiError(404, "match_not_found", "Not found.")
    if isinstance(exc, riot.RiotUnavailableError):
        return ApiError(503, "riot_unavailable", "Riot's API isn't responding.")
    return ApiError(500, "internal", "Something went wrong.")


# Seams with the model and review packages; imported lazily and replaced in tests.
def _load_model(models_dir: Path):
    from lolreview import model

    return model.load_model(models_dir)


def _models_changed(models_dir: Path, current) -> bool:
    from lolreview import model

    return model.models_changed(models_dir, current)


def _build_review(
    match, timeline, participant_id, tier, model, champions, ddragon_version, tier_note
):
    from lolreview import review

    try:
        return review.build_review(
            match, timeline, participant_id, tier, model, champions, ddragon_version, tier_note
        )
    except (review.UnsupportedQueue, review.Remake) as exc:
        raise _unsupported() from exc


def _unsupported() -> ApiError:
    return ApiError(422, "unsupported_queue", "Only ranked solo/duo games can be reviewed.")


def _not_allowed() -> ApiError:
    return ApiError(403, "not_allowed", "This hosted app only shows its owner's games.")


def _allowed_players() -> set[str] | None:
    raw = os.environ.get("LOLREVIEW_ALLOWED_PLAYERS", "")
    allowed = {name.strip().lower() for name in raw.split(",") if name.strip()}
    return allowed or None


def _demo_player() -> DemoPlayer:
    from lolreview import demo

    return DemoPlayer(riot_id=f"{demo.DEMO_NAME}#{demo.DEMO_TAG}", platform=demo.DEMO_PLATFORM)


def _is_allowed(allowed: set[str] | None, name: str, tag: str) -> bool:
    return allowed is None or f"{name}#{tag}".lower() in allowed


def _patch_of(match: dict) -> str:
    return ".".join(str(match["info"]["gameVersion"]).split(".")[:2])


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat().replace("+00:00", "Z")


def _is_remake(info: dict, participant: dict | None = None) -> bool:
    if info.get("gameDuration", 0) < REMAKE_MAX_S:
        return True
    return bool(participant and participant.get("gameEndedInEarlySurrender"))


def _rank_from_entry(entry: dict | None) -> Rank | None:
    if not entry:
        return None
    tier = entry["tier"]
    division = None if tier in ("MASTER", "GRANDMASTER", "CHALLENGER") else entry.get("rank")
    return Rank(tier=tier, division=division, lp=entry.get("leaguePoints", 0))


ROLES = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}


def _real_role(position: str | None) -> str | None:
    return position if position in ROLES else None


def _spark(review: Review) -> list[float] | None:
    """Win chance (0-100, the reviewed player's team) at evenly spaced times, first to last."""
    if not review.curve:
        return None
    end = review.curve[-1].t
    times = [end * i / (SPARK_POINTS - 1) for i in range(SPARK_POINTS)]
    return [round(min(review.curve, key=lambda pt: abs(pt.t - t)).p * 100, 1) for t in times]


def _score_rank(players: list[Player], participant_id: int) -> int | None:
    """Place by score, best first, ties by lower participant_id; None while a score is missing."""
    if any(p.score is None for p in players):
        return None
    order = sorted(players, key=lambda p: (-p.score, p.participant_id))
    return [p.participant_id for p in order].index(participant_id) + 1


def _review_fields(cache: Cache, match_id: str, participant_id: int, version: str) -> dict:
    """Score, badge, rank, grades and spark of a reviewed game, read from its cached review."""
    try:
        review = Review.model_validate(cache.get_review(match_id, participant_id, version))
    except ValueError:  # includes pydantic's ValidationError
        log.warning("cached review of %s no longer validates; leaving its score out", match_id)
        return {}
    me = next((p for p in review.players if p.participant_id == participant_id), None)
    if me is None:
        return {}
    return {
        "score": me.score,
        "badge": me.badge,
        "score_rank": _score_rank(review.players, participant_id),
        "grades": review.summary.me,
        "spark": _spark(review),
    }


class _Context:
    def __init__(self, demo: bool, cache: Cache | None, client, ddragon: DataDragon | None):
        self.demo = demo
        # Demo games never share a cache with real ones.
        demo_cache = default_path().with_name("cache-demo.db")
        self.cache = cache or (Cache(demo_cache) if demo else Cache())
        if demo:
            from lolreview import demo as demo_mod

            self.client = client or demo_mod.DemoRiot()
            self.ddragon = ddragon or DataDragon(
                self.cache, offline=True, offline_champions=demo_mod.DEMO_CHAMPIONS
            )
        else:
            self.client = client or riot.RiotClient(on_key_error="raise", max_429_retries=1)
            self.ddragon = ddragon or DataDragon(self.cache)
        # LOLREVIEW_MODELS_DIR overrides config.toml (the browser tests point it at an empty folder)
        models_dir = Path(
            os.environ.get("LOLREVIEW_MODELS_DIR") or load_config()["paths"]["models_dir"]
        )
        self.models_dir = models_dir if models_dir.is_absolute() else ROOT / models_dir
        self._model = None
        self._model_lock = threading.Lock()

    def model(self):
        with self._model_lock:
            if self._model is None or _models_changed(self.models_dir, self._model):
                self._model = _load_model(self.models_dir)
            return self._model

    # Riot data, through the cache
    def match(self, cluster: str, match_id: str) -> dict:
        match = self.cache.get_match(match_id)
        if match is None:
            match = self.client.match(cluster, match_id)
            self.cache.put_match(match_id, match)
        return match

    def timeline(self, cluster: str, match_id: str) -> dict:
        timeline = self.cache.get_timeline(match_id)
        if timeline is None:
            timeline = self.client.timeline(cluster, match_id)
            self.cache.put_timeline(match_id, timeline)
        return timeline

    def rank_entry(self, platform: str, puuid: str) -> dict | None:
        cached = self.cache.get_rank(platform, puuid)
        if cached is not None:
            return cached["entry"]
        entry = self.client.rank_by_puuid(platform, puuid)
        self.cache.put_rank(platform, puuid, entry)
        return entry

    def champions(self, match: dict) -> tuple[dict[int, tuple[str, str]], str]:
        version = self.ddragon.version_for_patch(_patch_of(match))
        champions = {
            p["championId"]: (p["championName"], p["championName"])
            for p in match["info"]["participants"]
        }
        champions.update(self.ddragon.champions(version))
        return champions, version

    def summary(self, cluster: str, match_id: str, puuid: str) -> dict:
        cached = self.cache.get_summary(match_id, puuid)
        if cached is not None:
            try:
                GameSummary(**cached, reviewed=False)
                return cached
            except ValidationError:
                log.warning("cached summary of %s no longer validates; rebuilding", match_id)
        match = self.match(cluster, match_id)
        info = match["info"]
        me = next((p for p in info["participants"] if p["puuid"] == puuid), None)
        if me is None:
            raise ApiError(404, "match_not_found", "Player not in this match.")
        champions, version = self.champions(match)
        if _is_remake(info, me):
            result = "remake"
        else:
            result = "win" if me["win"] else "loss"
        summary = {
            "match_id": match_id,
            "participant_id": me["participantId"],
            "champion": champions[me["championId"]][0],
            "role": _real_role(me.get("teamPosition") or me.get("individualPosition")),
            "result": result,
            "k": me["kills"],
            "d": me["deaths"],
            "a": me["assists"],
            "cs": me.get("totalMinionsKilled", 0) + me.get("neutralMinionsKilled", 0),
            "duration_s": info["gameDuration"],
            "started_at": _iso(info.get("gameStartTimestamp") or info["gameCreation"]),
            "patch": _patch_of(match),
            "ddragon_version": version,
        }
        GameSummary(**summary, reviewed=False)
        self.cache.put_summary(match_id, puuid, summary)
        return summary

    def tier_for(self, platform: str, match: dict, participant: dict) -> tuple[str, str | None]:
        entry = self.rank_entry(platform, participant["puuid"])
        if entry:
            return entry["tier"], None
        others = [
            p
            for p in match["info"]["participants"]
            if p["participantId"] != participant["participantId"]
        ]
        tiers = []
        for p in others:
            other = self.rank_entry(platform, p["puuid"])
            if other and other["tier"] in TIER_INDEX:
                tiers.append(TIER_INDEX[other["tier"]])
        if not tiers:
            return (
                DEFAULT_TIER,
                f"Nobody in the game is ranked, so {DEFAULT_TIER.title()} was used.",
            )
        tier = TIERS[int(statistics.median_low(tiers))]
        return (
            tier,
            f"You're unranked, so the median rank of the other players ({tier.title()}) was used.",
        )


def create_app(
    demo: bool | None = None,
    dev: bool | None = None,
    cache: Cache | None = None,
    client=None,
    ddragon: DataDragon | None = None,
) -> FastAPI:
    if demo is None:
        demo = os.environ.get("LOLREVIEW_DEMO") == "1"
    if dev is None:
        dev = os.environ.get("LOLREVIEW_DEV") == "1"

    app = FastAPI(title="LeagueVODreview")
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    if dev:
        app.add_middleware(
            CORSMiddleware, allow_origins=[DEV_ORIGIN], allow_methods=["GET", "POST"]
        )

    allowed = _allowed_players()
    state: dict[str, _Context] = {}
    state_lock = threading.Lock()

    def ctx() -> _Context:
        with state_lock:
            if "ctx" not in state:
                state["ctx"] = _Context(demo, cache, client, ddragon)
            return state["ctx"]

    app.state.context = ctx

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return _error_response(exc)

    @app.exception_handler(riot.RiotError)
    async def _riot_error(request: Request, exc: riot.RiotError):
        err = _from_riot_error(exc)
        if err.code == "internal":
            log.error("unexpected Riot error: %s", exc)
        return _error_response(err)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error("unhandled error on %s: %r", request.url.path, exc, exc_info=exc)
        return _error_response(ApiError(500, "internal", "Something went wrong."))

    errors = {
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    }

    @app.get("/api/health", response_model=Health)
    def health():
        c = ctx()
        model = c.model()
        if c.demo:
            key = "ok"
        elif not read_env().get("RIOT_API_KEY", "").strip():
            key = "missing"
        else:
            key = "expired" if c.client.key_status == "expired" else "ok"
        return Health(
            riot_key=key,
            model=ModelInfo(
                kind=model.kind,
                version=model.version,
                trained_at=getattr(model, "trained_at", None),
                patches=getattr(model, "patches", None),
            ),
            demo_player=_demo_player() if c.demo else None,
        )

    @app.get("/api/player/{platform}/{name}/{tag}", response_model=PlayerGames, responses=errors)
    def player(platform: str, name: str, tag: str, start: int = 0, count: int = 10):
        c = ctx()
        platform = platform.lower()
        cluster = PLATFORM_TO_CLUSTER.get(platform)
        if cluster is None:
            raise ApiError(404, "riot_id_not_found", f"Unknown platform {platform}.")
        if not _is_allowed(allowed, name, tag):
            raise _not_allowed()
        start = max(0, start)
        count = max(1, min(count, 100))
        account = c.cache.get_account(cluster, name, tag)
        if account is None:
            try:
                account = c.client.account_by_riot_id(cluster, name, tag)
            except riot.NotFoundError as exc:
                raise ApiError(
                    404,
                    "riot_id_not_found",
                    f"No player called {name}#{tag} on {platform.upper()}.",
                ) from exc
            c.cache.put_account(cluster, name, tag, account)
        puuid = account["puuid"]
        rank = _rank_from_entry(c.rank_entry(platform, puuid))
        ids = c.cache.get_match_ids(puuid, start, count)
        if ids is None:
            ids = c.client.match_ids(cluster, puuid, QUEUE_RANKED_SOLO, start=start, count=count)
            c.cache.put_match_ids(puuid, start, count, ids)
        version = f"{c.model().version}+r{REVIEW_FORMAT}"
        games = []
        for match_id in ids:
            s = c.summary(cluster, match_id, puuid)
            reviewed = c.cache.has_review(match_id, s["participant_id"], version)
            fields = {}
            if reviewed:
                fields = _review_fields(c.cache, match_id, s["participant_id"], version)
            games.append(GameSummary(**s, reviewed=reviewed, **fields))
        game_name = account.get("gameName", name)
        tag_line = account.get("tagLine", tag)
        return PlayerGames(
            puuid=puuid,
            riot_id=f"{game_name}#{tag_line}",
            platform=platform,
            rank=rank,
            games=games,
            next_start=start + count if len(ids) >= count else None,
        )

    @app.get("/api/review/{match_id}", response_model=Review, responses=errors)
    def review(match_id: str, p: int):
        c = ctx()
        version = f"{c.model().version}+r{REVIEW_FORMAT}"
        cached = c.cache.get_review(match_id, p, version)
        if cached is not None:
            return JSONResponse(cached)
        platform = match_id.split("_")[0].lower()
        cluster = PLATFORM_TO_CLUSTER.get(platform)
        if cluster is None:
            raise ApiError(404, "match_not_found", "Match not found.")
        try:
            match = c.match(cluster, match_id)
        except riot.NotFoundError as exc:
            raise ApiError(404, "match_not_found", "Match not found.") from exc
        info = match["info"]
        participant = next((x for x in info["participants"] if x["participantId"] == p), None)
        if participant is None:
            raise ApiError(404, "match_not_found", "Match not found.")
        name = participant.get("riotIdGameName", "")
        tag = participant.get("riotIdTagline", "")
        if not _is_allowed(allowed, name, tag):
            raise _not_allowed()
        if info.get("queueId") != QUEUE_RANKED_SOLO or _is_remake(info, participant):
            raise _unsupported()
        try:
            timeline = c.timeline(cluster, match_id)
        except riot.NotFoundError as exc:
            raise ApiError(404, "match_not_found", "Match not found.") from exc
        tier, tier_note = c.tier_for(platform, match, participant)
        champions, ddragon_version = c.champions(match)
        built = _build_review(
            match, timeline, p, tier, c.model(), champions, ddragon_version, tier_note
        )
        data = Review.model_validate(built).model_dump(mode="json", by_alias=True)
        c.cache.put_review(match_id, p, version, data)
        return JSONResponse(data)

    @app.get("/api/patterns", response_model=Patterns, responses=errors)
    def patterns(games: str = ""):
        # Only cached reviews: never fetches a match or builds a review here.
        c = ctx()
        version = f"{c.model().version}+r{REVIEW_FORMAT}"
        found = []
        for item in games.split(",")[:PATTERNS_MAX_GAMES]:
            match_id, sep, p = item.strip().partition(":")
            if not match_id or not sep or not p.isdigit():
                continue
            review_data = c.cache.get_review(match_id, int(p), version)
            if review_data is not None:
                found.append(review_data)
        return patterns_of(found)

    @app.get("/api/model", response_model=ModelMetrics, responses=errors)
    def model_metrics():
        m = ctx().model()
        metrics = getattr(m, "metrics", None)
        if m.kind != "trained" or not metrics:
            raise ApiError(404, "model_missing", "No trained model yet.")
        return JSONResponse(metrics)

    def replay_match(c: _Context, match_id: str) -> dict:
        cluster = PLATFORM_TO_CLUSTER.get(match_id.split("_")[0].lower())
        if cluster is None:
            raise ApiError(404, "match_not_found", "Match not found.")
        try:
            return c.match(cluster, match_id)
        except riot.NotFoundError as exc:
            raise ApiError(404, "match_not_found", "Match not found.") from exc

    def newest_patch(c: _Context) -> str | None:
        try:
            return ".".join(c.ddragon.versions()[0].split(".")[:2])
        except Exception as exc:
            log.warning("newest patch unknown (%s); skipping the replay patch check", exc)
            return None

    def replay_status_for(match_id: str) -> ReplayStatus:
        c = ctx()
        if c.demo:
            return ReplayStatus(available=False, reason=DEMO_REPLAY_REASON)
        match = replay_match(c, match_id)
        return replay.status(match, newest_patch(c))

    @app.get("/api/replay/status", response_model=ReplayStatus, responses=errors)
    def replay_status(match_id: str):
        return replay_status_for(match_id)

    @app.post("/api/replay/seek", response_model=ReplaySeekResult, responses=errors)
    def replay_seek(body: ReplaySeek):
        status = replay_status_for(body.match_id)
        if not status.available:
            raise ApiError(409, "replay_unavailable", status.reason or replay.REASON_OPEN)
        try:
            replay.seek(body.t)
        except replay.ReplayUnavailable as exc:
            raise ApiError(409, "replay_unavailable", exc.reason) from exc
        return ReplaySeekResult(ok=True)

    @app.get("/api/worlds/live", response_model=WorldsLive, responses=errors)
    def worlds_live():
        return worlds.live_games()

    @app.get("/api/worlds/matches", response_model=WorldsMatches, responses=errors)
    def worlds_matches():
        return worlds.matches()

    @app.get("/api/worlds/match/{match_id}", response_model=WorldsLive, responses=errors)
    def worlds_match(match_id: str):
        return worlds.match_games(match_id)

    return app


app = create_app()
