"""Plain-words titles and place names for moments, built from templates."""

from __future__ import annotations

from lolreview import map_data
from lolreview.schemas import GameEvent

MAX_PARTS = 3
_LOWER_LEADS = ("Took", "Enemy", "Destroyed", "Lost", "Won", "Died", "Traded", "Ace", "Even")

_OBJECTIVE_NAMES = {
    "elder": "Elder Dragon",
    "baron": "Baron",
    "herald": "Rift Herald",
    "atakhan": "Atakhan",
}


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _join(names: list[str]) -> str:
    return " + ".join(names)


def _name(names: dict[int, str], pid: int | None) -> str:
    return names.get(pid, "Someone") if pid is not None else "Someone"


def _cont(text: str) -> str:
    """Lower-case the first word of a follow-on part, unless it starts with a champion name."""
    return text[:1].lower() + text[1:] if text.startswith(_LOWER_LEADS) else text


def kill_title(e: GameEvent, names: dict[int, str], me: int) -> str:
    victim = _name(names, e.victim)
    killers = [e.killer] if e.killer is not None else []
    killers += e.assists or []
    if not killers:
        return "Died" if e.victim == me else f"{victim} died"
    who = _join([_name(names, k) for k in killers])
    if e.victim == me:
        return f"Died to {who}"
    return f"{who} killed {victim}"


def _is_ace(kills: list[GameEvent], side: str) -> bool:
    return len({e.victim for e in kills if e.team == side and e.victim is not None}) >= 5


def kills_title(kills: list[GameEvent], names: dict[int, str], me: int) -> str:
    if len(kills) == 1:
        return kill_title(kills[0], names, me)
    ours = sum(1 for e in kills if e.team == "ally")
    theirs = len(kills) - ours
    if _is_ace(kills, "ally"):
        return "Ace"
    if _is_ace(kills, "enemy"):
        return "Enemy ace"
    word = "fight" if len(kills) >= 3 else "skirmish"
    if ours > theirs:
        return f"Won {word} {ours} for {theirs}"
    if ours < theirs:
        return f"Lost {word} {ours} for {theirs}"
    return f"Even {word} {ours} for {theirs}"


def _objective_title(e: GameEvent, n: int, ordinal_n: int | None) -> str:
    """One kind of non-kill event, `n` times, all by one team."""
    ours = e.team == "ally"
    took = "Took" if ours else "Enemy took"
    if e.kind == "dragon":
        label = f"{e.detail} Dragon" if e.detail else "Dragon"
        suffix = f" ({ordinal(ordinal_n)})" if ordinal_n else ""
        return f"{took} {label}{suffix}"
    if e.kind == "grubs":
        return f"{took} {n} Void Grubs" if n > 1 else f"{took} a Void Grub"
    if e.kind in _OBJECTIVE_NAMES:
        return f"{took} {_OBJECTIVE_NAMES[e.kind]}"
    if e.kind == "plate":
        place = f"{e.detail} " if e.detail else ""
        return f"{took} {n} {place}plates" if n > 1 else f"{took} {place}plate"
    verb = "Destroyed" if ours else "Lost"
    if e.kind == "tower":
        if n > 1:
            return f"{verb} {n} towers"
        return f"{verb} {e.detail} tower" if e.detail else f"{verb} a tower"
    if n > 1:
        return f"{verb} {n} inhibitors"
    return f"{verb} {e.detail} inhibitor" if e.detail else f"{verb} an inhibitor"


def moment_title(
    events: list[GameEvent],
    names: dict[int, str],
    me: int,
    ordinals: list[int | None] | None = None,
) -> str:
    """Title for events in time order. `ordinals[i]` is the n-th dragon for events[i], if known."""
    ordinals = ordinals or [None] * len(events)
    parts: list[tuple[float, str]] = []
    kills = [e for e in events if e.kind == "kill"]
    if kills:
        parts.append((kills[0].t, kills_title(kills, names, me)))
    seen: dict[tuple[str, str], list[int]] = {}
    for i, e in enumerate(events):
        if e.kind != "kill":
            seen.setdefault((e.kind, e.team), []).append(i)
    for idxs in seen.values():
        first = events[idxs[0]]
        n = len(idxs)
        if first.kind in ("dragon", "elder", "baron", "herald", "atakhan"):
            for i in idxs:  # distinct objectives each get their own part
                parts.append((events[i].t, _objective_title(events[i], 1, ordinals[i])))
        else:
            parts.append((first.t, _objective_title(first, n, None)))
    parts.sort(key=lambda p: p[0])
    texts = [p[1] for p in parts]
    if len(texts) > MAX_PARTS:
        extra = len(texts) - MAX_PARTS
        texts = texts[:MAX_PARTS]
        texts[-1] += f", +{extra} more"
    return ", then ".join([texts[0]] + [_cont(t) for t in texts[1:]])


def where(x: float | None, y: float | None, my_team: str, standing: set[str] | None = None) -> str:
    """Zone name, plus the nearest standing building when one is close ("mid lane, near ...")."""
    if x is None or y is None:
        return "unknown"
    zone = map_data.zone_of(x, y, my_team)
    near = map_data.nearest_building(x, y, standing) if standing else None
    if near is None:
        return zone
    return f"{zone}, near {map_data.building_name(near, my_team)}"
