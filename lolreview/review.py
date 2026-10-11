"""Builds the Review JSON for one player of one game: win-chance curve, moments and snapshots."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from lolreview import describe, map_data, schemas
from lolreview.config import load_config
from lolreview.constants import BLUE, DRAGON_TYPES, ELDER, RED, ROLES
from lolreview.features import (
    GameState,
    _building_id,
    feature_row,
    patch_of,
    skip_reason,
    states_at,
)
from lolreview.model import WinModel
from lolreview.windows import baron_pit_monster, find_windows

MONSTER_KINDS = {
    "HORDE": "grubs",
    "RIFTHERALD": "herald",
    "BARON_NASHOR": "baron",
    "ATAKHAN": "atakhan",
}
REVIEW_EVENT_TYPES = (
    "CHAMPION_KILL",
    "ELITE_MONSTER_KILL",
    "BUILDING_KILL",
    "TURRET_PLATE_DESTROYED",
)


class ReviewError(ValueError):
    """A game that can't be reviewed."""


class UnsupportedQueue(ReviewError):
    pass


class Remake(ReviewError):
    pass


def _side(team_id: int, my_team: int) -> str:
    return "ally" if team_id == my_team else "enemy"


def _other(team_id: int) -> int:
    return RED if team_id == BLUE else BLUE


def _collect_events(
    timeline: dict, team_of: dict[int, int], my_team: int
) -> tuple[list[tuple[int, schemas.GameEvent, int | None]], int]:
    """Review events as (t_ms, event, dragon ordinal), in time order, plus the game end in ms."""
    raw = []
    end_ms = 0
    for f in timeline["info"]["frames"]:
        end_ms = max(end_ms, f["timestamp"])
        for e in f["events"]:
            if e["type"] == "GAME_END":
                end_ms = max(end_ms, e["timestamp"])
            elif e["type"] in REVIEW_EVENT_TYPES:
                raw.append(e)
    raw.sort(key=lambda e: e["timestamp"])
    nexus_seen: dict[str, int] = {}
    dragons = {BLUE: 0, RED: 0}
    out = []
    for e in raw:
        t = e["timestamp"]
        pos = e.get("position") or {}
        common = {"t": t / 1000, "x": pos.get("x"), "y": pos.get("y")}
        killer = e.get("killerId") if e.get("killerId") in team_of else None
        assists = [a for a in e.get("assistingParticipantIds", []) if a in team_of] or None
        ordinal = None
        kind = e["type"]
        if kind == "CHAMPION_KILL":
            victim_team = team_of.get(e["victimId"])
            team = team_of[killer] if killer else _other(victim_team or RED)
            ev = schemas.GameEvent(
                team=_side(team, my_team),
                kind="kill",
                killer=killer,
                victim=e["victimId"],
                assists=assists,
                **common,
            )
        elif kind == "ELITE_MONSTER_KILL":
            mt = e["monsterType"]
            team = e.get("killerTeamId") or team_of.get(killer) or BLUE
            if team not in (BLUE, RED):
                continue  # killerTeamId 300: the monster despawned (Herald before Baron spawns)
            detail = None
            if mt == "DRAGON":
                sub = e.get("monsterSubType")
                mk = "elder" if sub == ELDER else "dragon"
                detail = DRAGON_TYPES.get(sub)
                if mk == "dragon":
                    dragons[team] += 1
                    ordinal = dragons[team]
            elif mt in MONSTER_KINDS:
                mk = MONSTER_KINDS[mt]
            else:
                continue
            ev = schemas.GameEvent(
                team=_side(team, my_team), kind=mk, killer=killer, assists=assists,
                detail=detail, **common,
            )  # fmt: skip
        elif kind == "BUILDING_KILL":
            team = _other(e["teamId"])
            bid = _building_id(e, nexus_seen)
            rest = bid.split("_", 1)[1]
            if e["buildingType"] == "INHIBITOR_BUILDING":
                mk, detail = "inhibitor", rest.removesuffix("_inhib")
            elif rest.startswith("nexus"):
                mk, detail = "tower", "nexus"
            else:
                mk, detail = "tower", rest.replace("_", " ")
            ev = schemas.GameEvent(
                team=_side(team, my_team), kind=mk, killer=killer, assists=assists,
                detail=detail, **common,
            )  # fmt: skip
        else:
            team = _other(e["teamId"])
            lane = {"TOP_LANE": "top", "MID_LANE": "mid", "BOT_LANE": "bot"}.get(e.get("laneType"))
            ev = schemas.GameEvent(
                team=_side(team, my_team), kind="plate", killer=killer, detail=lane, **common
            )
        out.append((t, ev, ordinal))
    return out, end_ms


def _kill_pairs(kill: dict, team_of: dict[int, int]) -> dict[tuple[int, int], int]:
    """Champion-on-champion damage in one kill record, as {(source, target): total}."""
    victim = kill["victimId"]
    pairs: dict[tuple[int, int], int] = {}
    received = kill.get("victimTeamfightDamageReceived") or kill.get("victimDamageReceived") or []
    dealt = kill.get("victimTeamfightDamageDealt") or kill.get("victimDamageDealt") or []
    for entries, is_received in ((received, True), (dealt, False)):
        for d in entries:
            other = d.get("participantId")
            src, dst = (other, victim) if is_received else (victim, other)
            if src not in team_of or dst not in team_of or team_of[src] == team_of[dst]:
                continue
            total = d.get("physicalDamage", 0) + d.get("magicDamage", 0) + d.get("trueDamage", 0)
            pairs[(src, dst)] = pairs.get((src, dst), 0) + total
    return pairs


def _fight_damage(kills: list[dict], team_of: dict[int, int]) -> list[schemas.FightDamage]:
    best: dict[tuple[int, int], int] = {}
    for k in kills:
        for pair, total in _kill_pairs(k, team_of).items():
            best[pair] = max(best.get(pair, 0), total)
    dealt: dict[int, int] = {}
    taken: dict[int, int] = {}
    for (src, dst), total in best.items():
        dealt[src] = dealt.get(src, 0) + total
        taken[dst] = taken.get(dst, 0) + total
    out = [
        schemas.FightDamage(participant_id=p, dealt=dealt.get(p, 0), taken=taken.get(p, 0))
        for p in dealt.keys() | taken.keys()
    ]
    out = [d for d in out if d.dealt > 0 or d.taken > 0]
    return sorted(out, key=lambda d: (-d.dealt, d.participant_id))


def _kill_gold(kills: list[dict], team_of: dict[int, int], my_team: int) -> int:
    total = 0
    for k in kills:
        killer = k.get("killerId")
        if killer in team_of:
            team = team_of[killer]
        else:
            team = _other(team_of.get(k["victimId"]) or RED)
        gold = k.get("bounty", 0) + k.get("shutdownBounty", 0)
        total += gold if team == my_team else -gold
    return total


def _group(events: list, window_ms: int) -> list[list]:
    groups: list[list] = []
    for item in events:
        if groups and item[0] - groups[-1][-1][0] <= window_ms:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def _grade(delta: float, cfg: dict) -> str | None:
    r = cfg["review"]
    if delta >= r["great"]:
        return "!!"
    if delta >= r["good"]:
        return "!"
    if delta <= r["blunder"]:
        return "??"
    if delta <= r["mistake"]:
        return "?"
    return None


def _snapshot(
    t_ms: int, state: GameState, order: list[int], my_team: int, cfg: dict
) -> schemas.Snapshot:
    players = []
    for pid in order:
        p = state.players[pid]
        players.append(
            schemas.PlayerState(
                participant_id=pid, x=p.x, y=p.y, pos_age_s=max(0, t_ms - p.pos_t_ms) / 1000,
                level=p.level, k=p.k, d=p.d, a=p.a, cs=p.cs, gold=int(p.gold),
                items=list(p.items), trinket=p.trinket, quest_item=p.quest_item,
                respawn_in_s=max(0, p.dead_until_ms - t_ms) / 1000,
            )
        )  # fmt: skip

    def team(tid: int) -> schemas.TeamState:
        ts = state.teams[tid]
        buff = None
        if ts.buff:
            buff = schemas.Buff(kind=ts.buff[0], ends_in_s=max(0, ts.buff[1] - t_ms) / 1000)
        return schemas.TeamState(
            kills=ts.kills, gold=int(ts.gold), towers=ts.towers, dragons=list(ts.dragons),
            soul=ts.soul, grubs=ts.grubs, heralds=ts.heralds, barons=ts.barons, buff=buff,
        )  # fmt: skip

    recent = [
        schemas.RecentKill(x=x, y=y, team=_side(tid, my_team), age_s=max(0, t_ms - kt) / 1000)
        for kt, x, y, tid in state.recent_kills
    ]
    objectives = schemas.Objectives(
        dragon_in_s=state.dragon_pit_in_ms / 1000,
        dragon_kind="elder" if any(x.soul for x in state.teams.values()) else "dragon",
        baron_pit_in_s=state.baron_pit_in_ms / 1000,
        baron_pit_kind=baron_pit_monster(state, cfg),
    )
    return schemas.Snapshot(
        t=t_ms / 1000,
        players=players,
        teams=schemas.SnapshotTeams(ally=team(my_team), enemy=team(_other(my_team))),
        buildings_down=sorted(state.buildings_down),
        recent_kills=recent,
        objectives=objectives,
    )


def _players(
    info: dict, champions: dict[int, tuple[str, str]], my_pid: int, my_team: int
) -> list[schemas.Player]:
    out = []
    for team in (my_team, _other(my_team)):
        mates = [p for p in info["participants"] if p["teamId"] == team]
        taken: set[str] = set()
        roles: dict[int, str] = {}
        for p in mates:
            role = p.get("teamPosition") or p.get("individualPosition")
            if role in ROLES and role not in taken:
                roles[p["participantId"]] = role
                taken.add(role)
        free = [r for r in ROLES if r not in taken]
        for p in mates:
            roles.setdefault(p["participantId"], free.pop(0) if free else "MIDDLE")
        for p in sorted(mates, key=lambda p: ROLES.index(roles[p["participantId"]])):
            pid = p["participantId"]
            ddragon, display = champions.get(p["championId"], (p["championName"],) * 2)
            game_name = p.get("riotIdGameName") or p.get("summonerName") or "Unknown"
            tag = p.get("riotIdTagline")
            out.append(
                schemas.Player(
                    participant_id=pid,
                    riot_id=f"{game_name}#{tag}" if tag else game_name,
                    champion=ddragon,
                    champion_name=display,
                    role=roles[pid],
                    team=_side(team, my_team),
                    is_me=pid == my_pid,
                )  # fmt: skip
            )
    return out


def build_review(
    match: dict,
    timeline: dict,
    participant_id: int,
    tier: str,
    model: WinModel,
    champions: dict[int, tuple[str, str]],
    ddragon_version: str,
    tier_note: str | None = None,
    cfg: dict | None = None,
) -> schemas.Review:
    cfg = cfg or load_config()
    reason = skip_reason(match)
    if reason == "not_ranked_solo":
        raise UnsupportedQueue("only ranked solo games can be reviewed")
    if reason == "remake":
        raise Remake("remakes can't be reviewed")

    info = match["info"]
    me = next((p for p in info["participants"] if p["participantId"] == participant_id), None)
    if me is None:
        raise ReviewError(f"participant {participant_id} is not in this match")
    my_team = me["teamId"]
    my_color = "blue" if my_team == BLUE else "red"
    team_of = {p["participantId"]: p["teamId"] for p in info["participants"]}
    names = {
        p["participantId"]: champions.get(p["championId"], (p["championName"],) * 2)[1]
        for p in info["participants"]
    }
    won = bool(me["win"])

    events, end_ms = _collect_events(timeline, team_of, my_team)
    step_ms = int(cfg["review"]["step_s"] * 1000)
    window_ms = int(cfg["review"]["group_window_s"] * 1000)
    grid = [k * step_ms for k in range(math.ceil(info["gameDuration"] * 1000 / step_ms) + 1)]
    around = {max(0, t + d) for t, _, _ in events for d in (-1, 1)}
    times = sorted(set(grid) | around)
    states = dict(zip(times, states_at(match, timeline, times), strict=True))
    probs_blue = model.predict([feature_row(states[t], tier) for t in times])
    p = {t: (pb if my_team == BLUE else 1 - pb) for t, pb in zip(times, probs_blue, strict=True)}

    curve_times = sorted({t for t in grid if t < end_ms} | {t for t in around if t < end_ms})
    curve = [schemas.CurvePoint(t=t / 1000, p=round(p[t], 4)) for t in curve_times]
    curve.append(schemas.CurvePoint(t=end_ms / 1000, p=1.0 if won else 0.0))

    def p_at(t: int) -> float:
        return (1.0 if won else 0.0) if t > end_ms else p[t]

    kills = sorted(
        (
            e
            for f in timeline["info"]["frames"]
            for e in f["events"]
            if e["type"] == "CHAMPION_KILL"
        ),
        key=lambda e: e["timestamp"],
    )
    moments = []
    for i, group in enumerate(_group(events, window_ms), 1):
        t_first, t_last = group[0][0], group[-1][0]
        p_before = round(p_at(max(0, t_first - 1)), 4)
        p_after = round(p_at(t_last + 1), 4)
        delta = round(p_after - p_before, 4)
        evs = [ev for _, ev, _ in group]
        first = evs[0]
        standing = set(map_data.BUILDINGS) - states[max(0, t_first - 1)].buildings_down
        zone = describe.where(first.x, first.y, my_color, standing)
        involves_me = any(
            ev.killer == participant_id
            or ev.victim == participant_id
            or participant_id in (ev.assists or [])
            for ev in evs
        )
        m_kills = [k for k in kills if t_first <= k["timestamp"] <= t_last]
        moments.append(
            schemas.Moment(
                id=f"m{i}",
                t_start=t_first / 1000,
                t_end=t_last / 1000,
                p_before=p_before,
                p_after=p_after,
                delta=delta,
                grade=_grade(delta, cfg),
                title=describe.moment_title(evs, names, participant_id, [o for _, _, o in group]),
                zone=zone,
                involves_me=involves_me,
                events=evs,
                damage=_fight_damage(m_kills, team_of),
                kill_gold=_kill_gold(m_kills, team_of, my_team),
            )  # fmt: skip
        )

    players = _players(info, champions, participant_id, my_team)
    order = [pl.participant_id for pl in players]
    snapshots = [_snapshot(t, states[t], order, my_team, cfg) for t in grid]

    def counts(ms: list[schemas.Moment]) -> schemas.GradeCounts:
        n = {g: sum(1 for m in ms if m.grade == g) for g in ("!!", "!", "?", "??")}
        return schemas.GradeCounts(**{"!!": n["!!"], "!": n["!"], "?": n["?"], "??": n["??"]})

    biggest = max(moments, key=lambda m: abs(m.delta), default=None)
    summary = schemas.Summary(
        me=counts([m for m in moments if m.involves_me]),
        team=counts(moments),
        biggest_id=biggest.id if biggest else "",
    )

    windows = find_windows(states, grid, end_ms, my_team, tier, model, events, names, cfg)

    patches = model.patches
    started = info.get("gameStartTimestamp") or info.get("gameCreation") or 0
    review_match = schemas.ReviewMatch(
        match_id=match["metadata"]["matchId"],
        platform=info["platformId"],
        patch=patch_of(match),
        ddragon_version=ddragon_version,
        started_at=datetime.fromtimestamp(started / 1000, UTC).isoformat(timespec="seconds"),
        duration_s=info["gameDuration"],
        result="win" if won else "loss",
        surrender=any(p.get("gameEndedInSurrender") for p in info["participants"]),
        my_side=my_color,
        tier_used=tier,
        tier_note=tier_note,
        model=schemas.ReviewModel(kind=model.kind, version=model.version),
        patch_in_training=model.kind == "stub" or patch_of(match) in (patches or []),
    )
    buildings = [
        schemas.Building(
            id=b.id, team="ally" if b.team == my_color else "enemy", kind=b.kind, x=b.x, y=b.y
        )
        for b in map_data.BUILDINGS.values()
    ]
    return schemas.Review(
        match=review_match, players=players, buildings=buildings, curve=curve,
        moments=moments, snapshots=snapshots, summary=summary, windows=windows,
    )  # fmt: skip
