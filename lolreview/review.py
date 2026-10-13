"""Builds the Review JSON for one player of one game: win-chance curve, moments and snapshots."""

from __future__ import annotations

import bisect
import math
from datetime import UTC, datetime
from typing import Literal

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
from lolreview.windows import _taken, baron_pit_monster, find_windows

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
# The rank and the clock aren't things a team did; soul_type is a category code, not an amount
DRIVER_SKIP = ("tier", "minute", "soul_type")
DRIVER_MIN = 0.01  # log-odds; smaller moves aren't worth a line
DRIVERS_SHOWN = 3
TIP_LEVEL_GAP = 2
OBJECTIVE_KINDS = ("dragon", "elder", "baron", "herald", "grubs", "atakhan")


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


def _drivers(
    before: dict[str, float], after: dict[str, float], my_color: str
) -> list[schemas.Driver]:
    """The features that moved the most across a moment, signed so positive helped your team."""
    sign = 1 if my_color == "blue" else -1
    changes = {
        name: round(sign * (after[name] - before[name]), 3)
        for name in before
        if name not in DRIVER_SKIP
    }
    big = sorted(
        ((name, c) for name, c in changes.items() if abs(c) >= DRIVER_MIN),
        key=lambda nc: -abs(nc[1]),
    )
    return [
        schemas.Driver(label=describe.feature_label(name, my_color), change=c)
        for name, c in big[:DRIVERS_SHOWN]
    ]


def _tip(
    evs: list[schemas.GameEvent], state: GameState, me: int, my_team: int, names: dict[int, str]
) -> str | None:
    """A better play for one of my mistakes, from the state just before it. The first rule that
    matches wins; no tip when none does."""
    t = state.t_ms
    enemy = _other(my_team)
    team_of = {pid: p.team for pid, p in state.players.items()}
    kills = [e for e in evs if e.kind == "kill"]
    in_fight = {
        pid for e in kills for pid in (e.killer, e.victim, *(e.assists or [])) if pid in team_of
    }
    allies = {pid for pid in in_fight if team_of[pid] == my_team}
    enemies = in_fight - allies
    my_death = next((e for e in kills if e.victim == me), None)
    alive = {
        tid: sum(1 for p in state.players.values() if p.team == tid and p.dead_until_ms <= t)
        for tid in (my_team, enemy)
    }
    buff = state.teams[enemy].buff
    if buff and not state.teams[my_team].buff:
        secs = round((buff[1] - t) / 1000)
        return (
            f"Enemy had {buff[0].title()} buff for {secs} more seconds: "
            "wait it out under your towers instead of fighting."
        )
    if my_death and allies == {me} and len(enemies) >= 2:
        who = " + ".join(names.get(pid, "Someone") for pid in sorted(enemies))
        return f"Caught alone by {who}: stay near your team, or ward ahead before walking in."
    if len(enemies) > len(allies) >= 1:
        return f"Fought {len(allies)}v{len(enemies)}: back off until your team can join."
    if kills and alive[my_team] < alive[enemy]:
        return (
            f"Your team had {alive[my_team]} alive to their {alive[enemy]}: "
            "wait for respawns before fighting."
        )
    if my_death and my_death.killer in state.players:
        gap = state.players[my_death.killer].level - state.players[me].level
        if gap >= TIP_LEVEL_GAP:
            return (
                f"{names.get(my_death.killer, 'Your killer')} was {gap} levels ahead: "
                "avoid fighting them until you catch up."
            )
    taken = next((e for e in evs if e.team == "enemy" and e.kind in OBJECTIVE_KINDS), None)
    if taken:
        return (
            f"Enemy took {_taken(taken)}: be at the pit with vision before it spawns, "
            "or trade for a tower across the map."
        )
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
            if p["participantId"] not in roles:
                roles[p["participantId"]] = free.pop(0) if free else "MIDDLE"
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


def _moment_values(
    moments: list[schemas.Moment],
    states: dict[int, GameState],
    p_at,
    result: float,
) -> tuple[list[float], float]:
    """Each moment's win chance once its dead are back (no later than the next moment), and what
    moved between moments, which is the team's. Together they add up to the game's result."""
    values: list[float] = []
    between: float = 0.0
    n = len(moments)
    for i, moment in enumerate(moments):
        t_last = int(round(moment.t_end * 1000))
        p_before = moment.p_before

        if i == n - 1:
            value = moment.delta
        else:
            next_first = int(round(moments[i + 1].t_start * 1000))
            victims = [e.victim for e in moment.events if e.kind == "kill" and e.victim is not None]
            state_after = states.get(t_last + 1)
            if victims and state_after:
                back = max(
                    (
                        state_after.players[v].dead_until_ms
                        for v in victims
                        if v in state_after.players
                    ),
                    default=t_last + 1,
                )
            else:
                back = t_last + 1

            end = min(next_first - 1, max(t_last + 1, back))
            if end > t_last + 1:
                value = round(p_at(end) - p_before, 4)
            else:
                value = moment.delta
            between += p_at(next_first - 1) - p_before - value

        values.append(value)
    if moments:  # whatever moved after the last moment, to the result
        between += result - moments[-1].p_before - values[-1]
    return values, between


def _moment_credit(
    moment: schemas.Moment,
    value: float,
    team_of: dict[int, int],
    my_team: int,
) -> list[schemas.PlayerCredit]:
    if abs(value) < 1e-9:
        return []

    val = abs(value)
    gain_team = my_team if value > 0 else _other(my_team)
    lose_team = _other(gain_team)

    gaining_pids = [pid for pid, tid in team_of.items() if tid == gain_team]
    losing_pids = [pid for pid, tid in team_of.items() if tid == lose_team]

    died = {e.victim for e in moment.events if e.kind == "kill" and e.victim is not None}
    damage_by_pid = {d.participant_id: d for d in moment.damage}
    dealt = {p: damage_by_pid[p].dealt if p in damage_by_pid else 0 for p in gaining_pids}
    taken = {
        p: (damage_by_pid[p].taken if p in damage_by_pid else 0) if p not in died else 0
        for p in gaining_pids
    }

    gain_side = "ally" if gain_team == my_team else "enemy"
    part = set()
    for e in moment.events:
        if e.team == gain_side:
            if e.killer is not None and e.killer in gaining_pids:
                part.add(e.killer)
            for a in e.assists or []:
                if a in gaining_pids:
                    part.add(a)

    has_kill = any(e.kind == "kill" for e in moment.events)
    sum_dealt = sum(dealt.values())
    sum_taken = sum(taken.values())

    weights_gain: dict[int, float] = {}
    if has_kill and (sum_dealt > 0 or len(part) > 0):
        active_factors = []
        if sum_dealt > 0:
            active_factors.append(("dealt", 0.5))
        if sum_taken > 0:
            active_factors.append(("taken", 0.25))
        if len(part) > 0:
            active_factors.append(("part", 0.25))

        total_factor = sum(f for _, f in active_factors)
        norm_factors = {name: f / total_factor for name, f in active_factors}

        for p in gaining_pids:
            w = 0.0
            if "dealt" in norm_factors:
                w += norm_factors["dealt"] * (dealt[p] / sum_dealt)
            if "taken" in norm_factors:
                w += norm_factors["taken"] * (taken[p] / sum_taken)
            if "part" in norm_factors:
                w += norm_factors["part"] * (1.0 / len(part) if p in part else 0.0)
            weights_gain[p] = w
    elif len(part) > 0:
        for p in gaining_pids:
            weights_gain[p] = 1.0 / len(part) if p in part else 0.0
    else:
        for p in gaining_pids:
            weights_gain[p] = 1.0 / len(gaining_pids) if gaining_pids else 0.0

    death_counts = {p: 0 for p in losing_pids}
    for e in moment.events:
        if e.kind == "kill" and e.victim in death_counts:
            death_counts[e.victim] += 1
    total_deaths = sum(death_counts.values())

    weights_lose: dict[int, float] = {}
    if total_deaths > 0:
        for p in losing_pids:
            weights_lose[p] = death_counts[p] / total_deaths
    else:
        for p in losing_pids:
            weights_lose[p] = 1.0 / len(losing_pids) if losing_pids else 0.0

    credits: list[schemas.PlayerCredit] = []
    for p in gaining_pids:
        raw_share = weights_gain[p] * val
        share = round(raw_share, 4)
        if share != 0:
            credits.append(schemas.PlayerCredit(participant_id=p, share=share))

    for p in losing_pids:
        raw_share = -weights_lose[p] * val
        share = round(raw_share, 4)
        if share != 0:
            credits.append(schemas.PlayerCredit(participant_id=p, share=share))

    credits.sort(key=lambda c: c.participant_id)
    return credits


def _lane_scores(
    states: dict[int, GameState],
    players: list[schemas.Player],
    tier: str,
    model: WinModel,
    cfg: dict,
    end_ms: int,
) -> dict[int, dict[str, float | int | None]]:
    empty_lane = {"lane": None, "lane_gold": None, "lane_cs": None, "lane_level": None}
    res: dict[int, dict[str, float | int | None]] = {
        p.participant_id: dict(empty_lane) for p in players
    }

    lane_at_s = cfg.get("scores", {}).get("lane_at_s", 840)
    t = int(lane_at_s * 1000)
    if t >= end_ms or t not in states:
        return res

    state_t = states[t]
    role_pairs: dict[str, tuple[schemas.Player, schemas.Player]] = {}
    for role in ROLES:
        blue_p = [
            p
            for p in players
            if p.role == role
            and p.participant_id in state_t.players
            and state_t.players[p.participant_id].team == BLUE
        ]
        red_p = [
            p
            for p in players
            if p.role == role
            and p.participant_id in state_t.players
            and state_t.players[p.participant_id].team == RED
        ]
        if len(blue_p) == 1 and len(red_p) == 1:
            role_pairs[role] = (blue_p[0], red_p[0])

    if not role_pairs:
        return res

    base_row = feature_row(state_t, tier)
    rows: list[dict] = []
    pairs_order: list[tuple[str, int, int, float, float, float]] = []

    for role, (bp, rp) in role_pairs.items():
        b_st = state_t.players[bp.participant_id]
        r_st = state_t.players[rp.participant_id]
        lead_gold = b_st.gold - r_st.gold
        lead_cs = b_st.cs - r_st.cs
        lead_level = b_st.level - r_st.level

        row = dict(base_row)
        row["gold_diff"] -= lead_gold
        row["level_diff"] -= lead_level
        if role != "UTILITY":
            row["cs_diff"] -= lead_cs

        rows.append(row)
        pairs_order.append(
            (role, bp.participant_id, rp.participant_id, lead_gold, lead_cs, lead_level)
        )

    probs = model.predict([base_row, *rows])
    base_prob = probs[0]
    for k, (_, b_pid, r_pid, lg, lcs, llvl) in enumerate(pairs_order, start=1):
        lane_blue = base_prob - probs[k]
        res[b_pid] = {
            "lane": round(lane_blue, 4),
            "lane_gold": int(round(lg)),
            "lane_cs": int(round(lcs)),
            "lane_level": int(round(llvl)),
        }
        res[r_pid] = {
            "lane": round(-lane_blue, 4),
            "lane_gold": int(round(-lg)),
            "lane_cs": int(round(-lcs)),
            "lane_level": int(round(-llvl)),
        }

    return res


def _points(values: list[float]) -> list[float]:
    n = len(values)
    if n <= 1:
        return [5.0] * n
    res: list[float] = []
    for v in values:
        below = sum(1 for x in values if x < v)
        equal = sum(1 for x in values if x == v)
        pts = 10.0 * (below + (equal - 1) / 2.0) / (n - 1)
        res.append(pts)
    return res


def _scores(
    players: list[schemas.Player],
    info: dict,
    moments: list[schemas.Moment],
    cfg: dict,
) -> dict[int, tuple[float, schemas.ScoreParts, Literal["mvp", "ace"] | None]]:
    scores_cfg = cfg.get("scores", {})
    minutes = info["gameDuration"] / 60.0
    participant_by_id = {p["participantId"]: p for p in info["participants"]}

    team_kills: dict[int, int] = {BLUE: 0, RED: 0}
    for p in info["participants"]:
        team_kills[p["teamId"]] = team_kills.get(p["teamId"], 0) + p["kills"]

    kill_moments = [m for m in moments if any(e.kind == "kill" for e in m.events)]
    dealt_sums: dict[int, int] = {p.participant_id: 0 for p in players}
    taken_sums: dict[int, int] = {p.participant_id: 0 for p in players}

    for m in kill_moments:
        victims = {e.victim for e in m.events if e.kind == "kill" and e.victim is not None}
        for d in m.damage:
            pid = d.participant_id
            if pid in dealt_sums:
                dealt_sums[pid] += d.dealt
                if pid not in victims:
                    taken_sums[pid] += d.taken

    team_fd: dict[int, int] = {BLUE: 0, RED: 0}
    team_ft: dict[int, int] = {BLUE: 0, RED: 0}
    for p in players:
        tid = participant_by_id[p.participant_id]["teamId"]
        team_fd[tid] = team_fd.get(tid, 0) + dealt_sums[p.participant_id]
        team_ft[tid] = team_ft.get(tid, 0) + taken_sums[p.participant_id]

    gold_min_vals: dict[int, float] = {}
    kp_vals: dict[int, float] = {}
    fights_vals: dict[int, float] = {}
    impact_vals: dict[int, float] = {}
    lane_gold_vals: dict[int, float] = {}
    gpm_diff_vals: dict[int, float] = {}

    for p in players:
        pid = p.participant_id
        p_info = participant_by_id[pid]
        role = p.role
        tid = p_info["teamId"]

        norm_gold = scores_cfg["gold_min"][role]
        gold_min_vals[pid] = (p_info["goldEarned"] / minutes) / norm_gold

        norm_kp = scores_cfg["kp"][role]
        kp_frac = (p_info["kills"] + p_info["assists"]) / max(1, team_kills.get(tid, 1))
        kp_vals[pid] = kp_frac / norm_kp

        norm_fights = scores_cfg["fight_share"][role]
        share = 0.5 * dealt_sums[pid] / max(1, team_fd.get(tid, 1)) + 0.5 * taken_sums[pid] / max(
            1, team_ft.get(tid, 1)
        )
        fights_vals[pid] = share / norm_fights

        impact_vals[pid] = p.impact

        lane_gold_vals[pid] = float(p.lane_gold if p.lane_gold is not None else 0)
        enemy = next(
            (
                other
                for other in players
                if participant_by_id[other.participant_id]["teamId"] != tid and other.role == p.role
            ),
            None,
        )
        if enemy is not None:
            enemy_info = participant_by_id[enemy.participant_id]
            gpm_diff_vals[pid] = (p_info["goldEarned"] - enemy_info["goldEarned"]) / minutes
        else:
            gpm_diff_vals[pid] = 0.0

    pids = [p.participant_id for p in players]
    pts_gold_min = _points([gold_min_vals[pid] for pid in pids])
    pts_kp = _points([kp_vals[pid] for pid in pids])
    pts_fights = _points([fights_vals[pid] for pid in pids])
    pts_impact = _points([impact_vals[pid] for pid in pids])
    pts_lane_gold = _points([lane_gold_vals[pid] for pid in pids])
    pts_gpm_diff = _points([gpm_diff_vals[pid] for pid in pids])

    pts_vs_lane = [(lg + gd) / 2.0 for lg, gd in zip(pts_lane_gold, pts_gpm_diff, strict=True)]

    w_gpm = scores_cfg["weight_gold_min"]
    w_vs_lane = scores_cfg["weight_vs_lane"]
    w_kp = scores_cfg["weight_kp"]
    w_impact = scores_cfg["weight_impact"]
    w_fights = scores_cfg["weight_fights"]

    calculated_scores: dict[int, tuple[float, schemas.ScoreParts]] = {}
    for idx, pid in enumerate(pids):
        parts = schemas.ScoreParts(
            gold_min=round(pts_gold_min[idx], 1),
            vs_lane=round(pts_vs_lane[idx], 1),
            kp=round(pts_kp[idx], 1),
            impact=round(pts_impact[idx], 1),
            fights=round(pts_fights[idx], 1),
        )
        score_val = (
            w_gpm * parts.gold_min
            + w_vs_lane * parts.vs_lane
            + w_kp * parts.kp
            + w_impact * parts.impact
            + w_fights * parts.fights
        )
        score = round(score_val, 1)
        score = max(0.0, min(10.0, score))
        calculated_scores[pid] = (score, parts)

    winning_pids = [pid for pid in pids if participant_by_id[pid]["win"]]
    losing_pids = [pid for pid in pids if not participant_by_id[pid]["win"]]

    mvp_pid = max(winning_pids, key=lambda pid: (calculated_scores[pid][0], -pid))
    ace_pid = max(losing_pids, key=lambda pid: (calculated_scores[pid][0], -pid))

    out: dict[int, tuple[float, schemas.ScoreParts, Literal["mvp", "ace"] | None]] = {}
    for pid in pids:
        sc, parts = calculated_scores[pid]
        badge = "mvp" if pid == mvp_pid else ("ace" if pid == ace_pid else None)
        out[pid] = (sc, parts, badge)

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
    rows_at = {t: feature_row(states[t], tier) for t in times}
    probs_blue = model.predict([rows_at[t] for t in times])
    p = {t: (pb if my_team == BLUE else 1 - pb) for t, pb in zip(times, probs_blue, strict=True)}

    curve_times = sorted({t for t in grid if t < end_ms} | {t for t in around if t < end_ms})
    curve = [schemas.CurvePoint(t=t / 1000, p=round(p[t], 4)) for t in curve_times]
    curve.append(schemas.CurvePoint(t=end_ms / 1000, p=1.0 if won else 0.0))

    def p_at(t: int) -> float:
        if t > end_ms:
            return 1.0 if won else 0.0
        idx = bisect.bisect_right(times, t) - 1
        return p[times[max(0, idx)]]

    kills = sorted(
        (
            e
            for f in timeline["info"]["frames"]
            for e in f["events"]
            if e["type"] == "CHAMPION_KILL"
        ),
        key=lambda e: e["timestamp"],
    )
    groups = _group(events, window_ms)
    # The model's push on blue just before and just after each moment, for its drivers
    ends = [(max(0, g[0][0] - 1), g[-1][0] + 1) for g in groups]
    pushes = model.contributions([rows_at[t] for pair in ends for t in pair])
    moments = []
    for i, group in enumerate(groups, 1):
        t_first, t_last = group[0][0], group[-1][0]
        p_before = round(p_at(max(0, t_first - 1)), 4)
        p_after = round(p_at(t_last + 1), 4)
        drivers = _drivers(pushes[2 * i - 2], pushes[2 * i - 1], my_color)
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
        grade = _grade(delta, cfg)
        tip = None
        if involves_me and grade in ("?", "??"):
            tip = _tip(evs, states[max(0, t_first - 1)], participant_id, my_team, names)
        moments.append(
            schemas.Moment(
                id=f"m{i}",
                t_start=t_first / 1000,
                t_end=t_last / 1000,
                p_before=p_before,
                p_after=p_after,
                delta=delta,
                grade=grade,
                title=describe.moment_title(evs, names, participant_id, [o for _, _, o in group]),
                zone=zone,
                involves_me=involves_me,
                events=evs,
                damage=_fight_damage(m_kills, team_of),
                kill_gold=_kill_gold(m_kills, team_of, my_team),
                drivers=drivers,
                tip=tip,
            )  # fmt: skip
        )

    values, between = _moment_values(moments, states, p_at, 1.0 if won else 0.0)
    for m, val in zip(moments, values, strict=True):
        m.credit = _moment_credit(m, val, team_of, my_team)

    players = _players(info, champions, participant_id, my_team)
    lane_data = _lane_scores(states, players, tier, model, cfg, end_ms)
    impact_by_pid = {
        p.participant_id: round(
            sum(c.share for m in moments for c in m.credit if c.participant_id == p.participant_id),
            4,
        )
        for p in players
    }
    players = [
        p.model_copy(
            update={
                "impact": impact_by_pid[p.participant_id],
                "lane": lane_data[p.participant_id]["lane"],
                "lane_gold": lane_data[p.participant_id]["lane_gold"],
                "lane_cs": lane_data[p.participant_id]["lane_cs"],
                "lane_level": lane_data[p.participant_id]["lane_level"],
            }
        )
        for p in players
    ]
    scores_by_pid = _scores(players, info, moments, cfg)
    players = [
        p.model_copy(
            update={
                "score": scores_by_pid[p.participant_id][0],
                "score_parts": scores_by_pid[p.participant_id][1],
                "badge": scores_by_pid[p.participant_id][2],
            }
        )
        for p in players
    ]

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
    between_fights = round(between, 4)
    if between_fights == 0.0:
        between_fights = 0.0

    return schemas.Review(
        match=review_match, players=players, buildings=buildings, curve=curve,
        moments=moments, snapshots=snapshots, summary=summary, windows=windows,
        between_fights=between_fights,
    )  # fmt: skip
