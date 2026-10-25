"""Live Worlds games, from the same public feed lolesports.com reads."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import requests

from lolreview.schemas import (
    WorldsGame,
    WorldsLive,
    WorldsMatch,
    WorldsMatches,
    WorldsMatchTeam,
    WorldsPlayer,
    WorldsPoint,
    WorldsTeam,
)

API = "https://esports-api.lolesports.com/persisted/gw/"
LIVE_URL = API + "getLive"
WORLDS_ID = "98767975604431411"
WINDOW_URL = "https://feed.lolesports.com/livestats/v1/window/"
# The key lolesports.com itself sends; it is public.
HEADERS = {"x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"}
LAG_S = 60  # the feed only has frames up to about this far behind now
STEP_S = 60  # one point on the chart per minute
LOOKBACK_S = 90 * 60

_lock = threading.Lock()
_points: dict[str, dict[int, dict]] = {}  # game -> grid epoch -> that minute's last frame
_starts: dict[str, float] = {}  # game -> epoch of its first frame


def _get(url: str, **params) -> dict | None:
    """The JSON, or None when there is none (204: past the end of a game) or it keeps failing."""
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        except requests.RequestException:
            r = None
        if r is not None and r.status_code == 200:
            return r.json()
        if r is not None and r.status_code == 204:
            return None
        time.sleep(0.5 * (attempt + 1))
    return None


def _window(game_id: str, epoch: float | None = None) -> dict | None:
    """Frames from `epoch` on; with no epoch, the game's first frames."""
    params = {}
    if epoch is not None:
        at = datetime.fromtimestamp(int(epoch) // 10 * 10, UTC)
        params["startingTime"] = at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data = _get(WINDOW_URL + game_id, **params)
    return data if data and data.get("frames") else None


def _epoch(frame: dict) -> float:
    return datetime.fromisoformat(frame["rfc460Timestamp"].replace("Z", "+00:00")).timestamp()


def _history(game_id: str, now: float) -> None:
    """Adds the minutes the chart doesn't have yet."""
    newest = int(now - LAG_S) // STEP_S * STEP_S
    with _lock:
        have = _points.setdefault(game_id, {})
        first = max(have) + STEP_S if have else (int(now) - LOOKBACK_S) // STEP_S * STEP_S
    wanted = range(first, newest + 1, STEP_S)
    with ThreadPoolExecutor(8) as pool:
        got = list(pool.map(lambda e: (e, _window(game_id, e)), wanted))
    with _lock:
        for e, data in got:
            if data is None or data["frames"][-1]["gameState"] != "in_game":
                continue
            frames = data["frames"]
            _points[game_id][e] = frames[-1]
            _starts[game_id] = min(_starts.get(game_id, float("inf")), _epoch(frames[0]))


def _team(info: dict, side: str, frame_team: dict, meta: dict) -> WorldsTeam:
    names = {p["participantId"]: p for p in meta["participantMetadata"]}
    players = [
        WorldsPlayer(
            name=names[p["participantId"]]["summonerName"],
            champion=names[p["participantId"]]["championId"],
            role=names[p["participantId"]]["role"],
            level=p["level"],
            k=p["kills"],
            d=p["deaths"],
            a=p["assists"],
            cs=p["creepScore"],
            gold=p["totalGold"],
        )
        for p in frame_team["participants"]
    ]
    return WorldsTeam(
        code=info["code"],
        name=info["name"],
        side=side,
        series_wins=info["result"]["gameWins"],
        gold=frame_team["totalGold"],
        kills=frame_team["totalKills"],
        towers=frame_team["towers"],
        dragons=len(frame_team["dragons"]),
        barons=frame_team["barons"],
        players=players,
    )


def live_games() -> WorldsLive:
    """Every Worlds game being played right now, with its minute-by-minute stats."""
    events = (
        (_get(LIVE_URL, hl="en-US") or {}).get("data", {}).get("schedule", {}).get("events", [])
    )
    now = datetime.now(UTC).timestamp()
    games = []
    for event in events:
        if event["league"]["slug"] != "worlds" or event["type"] != "match":
            continue
        match = event["match"]
        teams = {t["id"]: t for t in match["teams"]}
        for game in match["games"]:
            if game["state"] != "inProgress":
                continue
            gid = game["id"]
            _history(gid, now)
            current = _window(gid, now - LAG_S)
            if current is None:
                continue
            frame = current["frames"][-1]
            meta = current["gameMetadata"]
            with _lock:
                start = _starts.get(gid, _epoch(current["frames"][0]))
                past = [f for f in _points[gid].values() if _epoch(f) < _epoch(frame)]
            frames = sorted(past, key=_epoch) + [frame]
            stage = event["blockName"]
            games.append(_game(game, teams, stage, match, meta, start, frames, live=True))
    return WorldsLive(games=games)


def _game(
    game: dict,
    teams: dict,
    stage: str,
    match: dict,
    meta: dict,
    start: float,
    frames: list,
    live: bool,
) -> WorldsGame:
    sides = {s["side"]: teams[s["id"]] for s in game["teams"]}
    points = [
        WorldsPoint(
            t=int(_epoch(f) - start),
            blue=_team(sides["blue"], "blue", f["blueTeam"], meta["blueTeamMetadata"]),
            red=_team(sides["red"], "red", f["redTeam"], meta["redTeamMetadata"]),
        )
        for f in frames
    ]
    return WorldsGame(
        id=game["id"],
        stage=stage,
        best_of=match["strategy"]["count"],
        patch=meta["patchVersion"],
        elapsed_s=points[-1].t,
        live=live,
        points=points,
    )


_schedule: dict = {"at": 0.0, "events": []}
_finished: dict[str, WorldsGame] = {}  # a finished game never changes


def _events() -> list[dict]:
    """Worlds matches that have started, newest first (cached for a minute)."""
    with _lock:
        if datetime.now(UTC).timestamp() - _schedule["at"] < 60:
            return _schedule["events"]
    data = _get(API + "getSchedule", hl="en-US", leagueId=WORLDS_ID) or {}
    events = data.get("data", {}).get("schedule", {}).get("events", [])
    started = [e for e in events if e["state"] != "unstarted" and e["type"] == "match"]
    started.sort(key=lambda e: e["startTime"], reverse=True)
    with _lock:
        _schedule.update(at=datetime.now(UTC).timestamp(), events=started)
    return started


def matches() -> WorldsMatches:
    """The Worlds matches played so far, newest first."""
    out = []
    for e in _events():
        m = e["match"]
        teams = [WorldsMatchTeam(code=t["code"], wins=t["result"]["gameWins"]) for t in m["teams"]]
        out.append(
            WorldsMatch(
                id=m["id"],
                start=e["startTime"],
                stage=e["blockName"],
                best_of=m["strategy"]["count"],
                live=e["state"] == "inProgress",
                teams=teams,
            )
        )
    return WorldsMatches(matches=out)


def _finished_game(game: dict, teams: dict, stage: str, match: dict) -> WorldsGame | None:
    gid = game["id"]
    if gid in _finished:
        return _finished[gid]
    first = _window(gid)
    if first is None:
        return None
    start = _epoch(first["frames"][0])
    frames = [first["frames"][0]]
    # one frame a minute, until the game is over. Recent games then run out of frames; older
    # ones keep returning their last frame.
    for k in range(1, 300, 16):
        with ThreadPoolExecutor(8) as pool:
            got = list(pool.map(lambda i: _window(gid, start + i * STEP_S), range(k, k + 16)))
        for d in got:
            if d is None or _epoch(d["frames"][-1]) <= _epoch(frames[-1]):
                break  # out of frames, or the feed is repeating its last one
            frames.append(d["frames"][-1])
            if frames[-1]["gameState"] == "finished":
                break
        else:
            continue
        break
    frames.sort(key=_epoch)
    for _ in range(10):  # the last minute, which the steps above stepped over
        if frames[-1]["gameState"] == "finished":
            break
        d = _window(gid, _epoch(frames[-1]))
        if d is None or _epoch(d["frames"][-1]) <= _epoch(frames[-1]):
            break
        frames.append(d["frames"][-1])
    built = _game(game, teams, stage, match, first["gameMetadata"], start, frames, live=False)
    _finished[gid] = built
    return built


def match_games(match_id: str) -> WorldsLive:
    """Every game played so far in one match, with its minute-by-minute stats."""
    event = next((e for e in _events() if e["match"]["id"] == match_id), None)
    details = (_get(API + "getEventDetails", hl="en-US", id=match_id) or {}).get("data")
    if event is None or details is None:
        return WorldsLive(games=[])
    match = details["event"]["match"]
    teams = {t["id"]: t for t in match["teams"]}
    done = [g for g in match["games"] if g["state"] == "completed"]
    with ThreadPoolExecutor(5) as pool:  # a best-of-five loads its games side by side
        games = list(pool.map(lambda g: _finished_game(g, teams, event["blockName"], match), done))
    return WorldsLive(games=[g for g in games if g is not None])
