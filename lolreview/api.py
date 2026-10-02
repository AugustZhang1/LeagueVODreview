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

from lolreview import riot
from lolreview.cache import Cache
from lolreview.config import ROOT, load_config, read_env
from lolreview.constants import (
    PLATFORM_TO_CLUSTER,
    QUEUE_RANKED_SOLO,
    REMAKE_MAX_S,
    TIER_INDEX,
    TIERS,
)
from lolreview.ddragon import DataDragon
from lolreview.schemas import (
    ErrorResponse,
    GameSummary,
    Health,
    ModelInfo,
    ModelMetrics,
    PlayerGames,
    Rank,
    Review,
)

log = logging.getLogger(__name__)

DEV_ORIGIN = "http://localhost:5173"
DEFAULT_TIER = "SILVER"


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


def _models_changed(current) -> bool:
    fn = getattr(current, "models_changed", None)
    if fn is None:
        from lolreview import model

        fn = model.models_changed
    try:
        return bool(fn())
    except TypeError:
        return bool(fn(current))


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


class _Context:
    def __init__(self, demo: bool, cache: Cache | None, client, ddragon: DataDragon | None):
        self.demo = demo
        self.cache = cache or Cache()
        if demo:
            from lolreview import demo as demo_mod

            self.client = client or demo_mod.DemoRiot()
            self.ddragon = ddragon or DataDragon(
                self.cache, offline=True, offline_champions=demo_mod.DEMO_CHAMPIONS
            )
        else:
            self.client = client or riot.RiotClient(on_key_error="raise", max_429_retries=1)
            self.ddragon = ddragon or DataDragon(self.cache)
        models_dir = Path(load_config()["paths"]["models_dir"])
        self.models_dir = models_dir if models_dir.is_absolute() else ROOT / models_dir
        self._model = None
        self._model_lock = threading.Lock()

    def model(self):
        with self._model_lock:
            if self._model is None or _models_changed(self._model):
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
            return cached
        match = self.match(cluster, match_id)
        info = match["info"]
        me = next((p for p in info["participants"] if p["puuid"] == puuid), None)
        if me is None:
            raise ApiError(404, "match_not_found", "Player not in this match.")
        champions, _ = self.champions(match)
        if _is_remake(info, me):
            result = "remake"
        else:
            result = "win" if me["win"] else "loss"
        summary = {
            "match_id": match_id,
            "participant_id": me["participantId"],
            "champion": champions[me["championId"]][0],
            "role": me.get("teamPosition") or me.get("individualPosition"),
            "result": result,
            "k": me["kills"],
            "d": me["deaths"],
            "a": me["assists"],
            "cs": me.get("totalMinionsKilled", 0) + me.get("neutralMinionsKilled", 0),
            "duration_s": info["gameDuration"],
            "started_at": _iso(info.get("gameStartTimestamp") or info["gameCreation"]),
            "patch": _patch_of(match),
        }
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
        app.add_middleware(CORSMiddleware, allow_origins=[DEV_ORIGIN], allow_methods=["GET"])

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
        )

    @app.get("/api/player/{platform}/{name}/{tag}", response_model=PlayerGames, responses=errors)
    def player(platform: str, name: str, tag: str, start: int = 0, count: int = 10):
        c = ctx()
        platform = platform.lower()
        cluster = PLATFORM_TO_CLUSTER.get(platform)
        if cluster is None:
            raise ApiError(404, "riot_id_not_found", f"Unknown platform {platform}.")
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
        version = c.model().version
        games = []
        for match_id in ids:
            s = c.summary(cluster, match_id, puuid)
            reviewed = c.cache.has_review(match_id, s["participant_id"], version)
            games.append(GameSummary(**s, reviewed=reviewed))
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
        version = c.model().version
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

    @app.get("/api/model", response_model=ModelMetrics, responses=errors)
    def model_metrics():
        m = ctx().model()
        metrics = getattr(m, "metrics", None)
        if m.kind != "trained" or not metrics:
            raise ApiError(404, "model_missing", "No trained model yet.")
        return JSONResponse(metrics)

    return app


app = create_app()
