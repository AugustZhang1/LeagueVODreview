"""Missed windows: stretches where the enemy was weak and something could have been taken."""

from __future__ import annotations

from lolreview import schemas
from lolreview.constants import BLUE, RED
from lolreview.features import GameState, feature_row
from lolreview.model import WinModel

LANES = {"TOP": "top", "MIDDLE": "mid", "BOTTOM": "bot"}
TAKEN_KINDS = {
    "dragon",
    "elder",
    "baron",
    "herald",
    "grubs",
    "atakhan",
    "tower",
    "inhibitor",
    "plate",
}
END_MARGIN_MS = 5000


def _weak_until(state: GameState, enemy: int, cfg: dict) -> int | None:
    """When the enemy's weakness ends, or None if they aren't weak for long enough. Both ways
    (jungler dead, or `min_dead` dead) need `jungler_dead_s` left: a few seconds is no window."""
    w = cfg["windows"]
    t = state.t_ms
    least = t + w["jungler_dead_s"] * 1000
    dead = [p for p in state.players.values() if p.team == enemy and p.dead_until_ms > t]
    ends = [p.dead_until_ms for p in dead if p.role == "JUNGLE"]
    if len(dead) >= w["min_dead"]:
        ends.append(sorted(p.dead_until_ms for p in dead)[-w["min_dead"]])
    ends = [e for e in ends if e >= least]
    return max(ends) if ends else None


def _monster_options(state: GameState, horizon: int, cfg: dict) -> list[str]:
    t = cfg["timers"]
    teams = state.teams.values()
    out = []
    if state.dragon_pit_in_ms <= horizon:
        out.append("Elder Dragon" if any(x.soul for x in teams) else "Dragon")
    if state.baron_pit_in_ms <= horizon:
        secs = state.t_ms / 1000
        if sum(x.grubs for x in teams) < 3 and secs < t["grubs_despawn_s"]:
            out.append("Void Grubs")
        elif sum(x.heralds for x in teams) == 0 and secs < t["herald_despawn_s"]:
            out.append("Rift Herald")
        else:
            out.append("Baron")
    return out


def _tower_options(state: GameState, enemy: int) -> list[str]:
    color = "red" if enemy == RED else "blue"
    out = []
    for p in state.players.values():
        lane = LANES.get(p.role)
        if p.team != enemy or not lane or p.dead_until_ms <= state.t_ms:
            continue
        for part in ("outer", "inner", "base", "inhib"):
            if f"{color}_{lane}_{part}" not in state.buildings_down:
                out.append(f"{lane} inhibitor" if part == "inhib" else f"{lane} {part} tower")
                break
    return out


def _credit(row: dict, what: str, my_team: int, state: GameState, timers: dict) -> dict:
    """The feature row with `what` taken by my team."""
    row = dict(row)
    s = 1 if my_team == BLUE else -1
    if what == "Dragon":
        key = "blue_dragons" if my_team == BLUE else "red_dragons"
        row[key] += 1
        if row[key] == 4 and row["soul_diff"] == 0:
            row["soul_diff"] = s
        row["dragon_pit_in_s"] = timers["dragon_respawn_s"]
    elif what == "Elder Dragon":
        row["elder_active"] = s
        row["dragon_pit_in_s"] = timers["elder_respawn_s"]
    elif what == "Baron":
        row["baron_active"] = s
        row["baron_pit_in_s"] = timers["baron_respawn_s"]
    elif what == "Rift Herald":
        row["herald_diff"] += s
    elif what == "Void Grubs":
        taken = sum(x.grubs for x in state.teams.values())
        row["grub_diff"] += s * (3 - taken)
    elif what.endswith("inhibitor"):
        row["inhibs_down_diff"] += s
    else:
        row["tower_diff"] += s
    return row


def _clock(ms: int) -> str:
    s = round(ms / 1000)
    return f"{s // 60}:{s % 60:02d}"


def _taken(ev: schemas.GameEvent) -> str:
    if ev.kind == "tower":
        return f"{ev.detail} tower" if ev.detail else "tower"
    if ev.kind == "inhibitor":
        return f"{ev.detail} inhibitor"
    return {
        "dragon": "Dragon", "elder": "Elder Dragon", "baron": "Baron", "herald": "Rift Herald",
        "grubs": "Void Grubs", "atakhan": "Atakhan", "plate": "plate",
    }[ev.kind]  # fmt: skip


def _title_and_reason(
    state: GameState, enemy: int, best: str, names: dict[int, str]
) -> tuple[str, str]:
    dead = sorted(
        (p for p in state.players.values() if p.team == enemy and p.dead_until_ms > state.t_ms),
        key=lambda p: -p.dead_until_ms,
    )
    if len(dead) == 1:
        who = f"Enemy {names[dead[0].participant_id]} dead"
    else:
        who = f"{len(dead)} enemies dead"
    suffix = " open" if best.endswith(("tower", "inhibitor")) else " up"
    parts = [f"{names[p.participant_id]} for {_clock(p.dead_until_ms - state.t_ms)}" for p in dead]
    parts[0] = parts[0].replace(" for ", " dead for ", 1)
    return f"{who}, {best}{suffix}", ", ".join(parts)


def find_windows(
    states: dict[int, GameState],
    grid: list[int],
    end_ms: int,
    my_team: int,
    tier: str,
    model: WinModel,
    events: list[tuple[int, schemas.GameEvent, int | None]],
    names: dict[int, str],
    cfg: dict,
) -> list[schemas.ObjectiveWindow]:
    enemy = RED if my_team == BLUE else BLUE

    # Group consecutive weak grid times that have something to take.
    groups: list[list[tuple[int, int, list[str]]]] = []  # (t, weak until, options)
    prev = None
    for t in grid:
        if t >= end_ms - END_MARGIN_MS:
            break
        state = states[t]
        until = _weak_until(state, enemy, cfg)
        opts = []
        if until is not None:
            opts = _monster_options(state, until - t, cfg) + _tower_options(state, enemy)
        if not opts:
            prev = None
            continue
        if prev is None:
            groups.append([])
        groups[-1].append((t, until, opts))
        prev = t
    if not groups:
        return []

    # One predict call for every (time, option) and the time's uncredited row.
    flat = [(t, what) for g in groups for t, _, opts in g for what in opts]
    times = sorted({t for t, _ in flat})
    base = {t: feature_row(states[t], tier) for t in times}
    rows = [base[t] for t in times]
    rows += [_credit(base[t], w, my_team, states[t], cfg["timers"]) for t, w in flat]
    probs = model.predict(rows)
    mine = [p if my_team == BLUE else 1 - p for p in probs]
    p_without = dict(zip(times, mine[: len(times)], strict=True))
    gain = {(t, w): p - p_without[t] for (t, w), p in zip(flat, mine[len(times) :], strict=True)}

    ally = [
        (ev.t, _taken(ev)) for _, ev, _ in events if ev.team == "ally" and ev.kind in TAKEN_KINDS
    ]
    out = []
    for g in groups:
        t_start = g[0][0]
        t_end = min(max(u for _, u, _ in g), end_ms)
        best: dict[str, float] = {}
        for t, _, opts in g:
            for what in opts:
                best[what] = max(best.get(what, -1.0), gain[(t, what)])
        ranked = sorted(best.items(), key=lambda kv: -kv[1])
        if ranked[0][1] < cfg["windows"]["min_value"]:
            continue
        taken = [
            what
            for t, what in ally
            if t_start / 1000 <= t <= t_end / 1000 + cfg["windows"]["used_after_s"]
        ]
        title, reason = _title_and_reason(states[t_start], enemy, ranked[0][0], names)
        out.append(
            schemas.ObjectiveWindow(
                id=f"w{len(out) + 1}", t_start=t_start / 1000, t_end=t_end / 1000, title=title,
                reason=reason, value=round(ranked[0][1], 4), used=bool(taken), taken=taken,
                options=[schemas.WindowOption(what=w, value=round(v, 4)) for w, v in ranked],
            )
        )  # fmt: skip
    return out
