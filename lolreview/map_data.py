"""Summoner's Rift geometry in game coordinates: buildings, zones and camps.

Game y points up. Blue base is bottom left, red base is top right. Building and camp positions
are approximate community values, checked later with the minimap's `?debug=1` overlay.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

BOUNDS = (-120, 14870)
_M = 14870
_LO = -120
_HI = _M + 120  # polygons run a little past the map so edge points stay inside


@dataclass(frozen=True)
class Building:
    id: str
    team: str  # "blue" | "red"
    kind: str  # "tower" | "inhibitor" | "nexus"
    x: int
    y: int


_BLUE_TOWERS = {
    "top_outer": (981, 10441),
    "top_inner": (1512, 6699),
    "top_base": (1169, 4287),
    "mid_outer": (5846, 6396),
    "mid_inner": (5048, 4812),
    "mid_base": (3651, 3696),
    "bot_outer": (10504, 1029),
    "bot_inner": (6919, 1483),
    "bot_base": (4281, 1253),
}
_BLUE_INHIBS = {"top": (1171, 3571), "mid": (3203, 3208), "bot": (3452, 1236)}
_BLUE_NEXUS = [(1748, 2270), (2177, 1807)]
_RED_TOWERS = {
    "top_outer": (4318, 13875),
    "top_inner": (7943, 13411),
    "top_base": (10481, 13650),
    "mid_outer": (8955, 8510),
    "mid_inner": (9767, 10113),
    "mid_base": (11134, 11207),
    "bot_outer": (13866, 4505),
    "bot_inner": (13327, 8226),
    "bot_base": (13624, 10572),
}
_RED_INHIBS = {"top": (11261, 13676), "mid": (11598, 11667), "bot": (13604, 11316)}
_RED_NEXUS = [(12611, 13084), (13052, 12612)]


def _build() -> list[Building]:
    out: list[Building] = []
    for team, towers, inhibs, nexus in (
        ("blue", _BLUE_TOWERS, _BLUE_INHIBS, _BLUE_NEXUS),
        ("red", _RED_TOWERS, _RED_INHIBS, _RED_NEXUS),
    ):
        out += [Building(f"{team}_{k}", team, "tower", *xy) for k, xy in towers.items()]
        out += [Building(f"{team}_{k}_inhib", team, "inhibitor", *xy) for k, xy in inhibs.items()]
        out += [Building(f"{team}_nexus_{i}", team, "nexus", *xy) for i, xy in enumerate(nexus, 1)]
    return out


BUILDINGS: dict[str, Building] = {b.id: b for b in _build()}

# ---------------------------------------------------------------- zones


def _mirror(poly: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(_M - x, _M - y) for x, y in poly]


def _swap(poly: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(y, x) for x, y in poly]


_BLUE_BASE = [(_LO, _LO), (4600, _LO), (4600, 1800), (3800, 3800), (1800, 4600), (_LO, 4600)]
_TOP_LANE = [(_LO, 4400), (2400, 4400), (2400, 12400), (10400, 12400), (10400, _HI), (_LO, _HI)]
_MID_LANE = [(_LO, 980), (13890, _HI), (_HI, _HI), (_HI, 13890), (980, _LO), (_LO, _LO)]
_TOP_RIVER = [(6535, 6535), (8335, 8335), (1680, _HI), (_LO, _HI), (_LO, 13190)]


def _square(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    return [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]


_CENTER = (_M / 2, _M / 2)
BARON_PIT = (5007, 10471)  # Void Grubs and Rift Herald spawn here too
DRAGON_PIT = (9866, 4414)
# (name, polygon). The first polygon containing a point wins, so order matters.
ZONES: list[tuple[str, list[tuple[float, float]]]] = [
    ("dragon pit", _square(*DRAGON_PIT, 700)),
    ("baron pit", _square(*BARON_PIT, 700)),
    ("blue base", _BLUE_BASE),
    ("red base", _mirror(_BLUE_BASE)),
    ("top lane", _TOP_LANE),
    ("bot lane", _swap(_TOP_LANE)),
    ("mid lane", _MID_LANE),
    ("top river", _TOP_RIVER),
    ("bot river", _swap(_TOP_RIVER)),
    ("blue jungle (top side)", [(_LO, _LO), (_LO, _HI), _CENTER]),
    ("blue jungle (bot side)", [(_LO, _LO), (_HI, _LO), _CENTER]),
    ("red jungle (top side)", [(_LO, _HI), (_HI, _HI), _CENTER]),
    ("red jungle (bot side)", [(_HI, _LO), (_HI, _HI), _CENTER]),
]


def _inside(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    hit = False
    j = len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def side_of(x: float, y: float) -> str:
    """Which team's half of the map a point is on: the river runs from top left to bottom right."""
    return "blue" if x + y < _M else "red"


def zone_of(x: float, y: float, my_team: str | None = None) -> str:
    """Plain-words place name. `my_team` ("blue" | "red") turns colors into your / enemy."""
    name = "the map"
    for zone, poly in ZONES:
        if _inside(x, y, poly):
            name = zone
            break
    if my_team is None:
        return name
    for color in ("blue", "red"):
        if name.startswith(color + " "):
            name = ("your" if color == my_team else "enemy") + name[len(color) :]
    return name


# ---------------------------------------------------------------- camps


@dataclass(frozen=True)
class Camp:
    id: str
    team: str | None  # side whose jungle it is; None for scuttle crabs
    kind: str
    x: int
    y: int


_BLUE_CAMPS = {
    "blue_buff": (3821, 7901),
    "gromp": (2288, 8448),
    "wolves": (3844, 6460),
    "red_buff": (7762, 4033),
    "raptors": (7054, 5293),
    "krugs": (8394, 2711),
}


def _camps() -> list[Camp]:
    out: list[Camp] = []
    for kind, (x, y) in _BLUE_CAMPS.items():
        out.append(Camp(f"blue_{kind}", "blue", kind, x, y))
        out.append(Camp(f"red_{kind}", "red", kind, _M - x, _M - y))
    out.append(Camp("scuttle_top", None, "scuttle", 4400, 9600))
    out.append(Camp("scuttle_bot", None, "scuttle", 10400, 5300))
    return out


CAMPS: list[Camp] = _camps()

# ---------------------------------------------------------------- buildings by place


def nearest_building(
    x: float, y: float, standing_ids: set[str] | list[str], max_dist: float = 1000
) -> str | None:
    best, best_d = None, max_dist
    for bid in standing_ids:
        b = BUILDINGS.get(bid)
        if b is None:
            continue
        d = math.hypot(b.x - x, b.y - y)
        if d <= best_d:
            best, best_d = bid, d
    return best


def building_name(building_id: str, my_team: str | None = None) -> str:
    """ "red mid outer tower"; with `my_team`, "enemy mid outer tower" / "your top inhibitor"."""
    b = BUILDINGS[building_id]
    color = b.team if my_team is None else ("your" if b.team == my_team else "enemy")
    rest = building_id.split("_", 1)[1]
    if b.kind == "inhibitor":
        lane = rest.removesuffix("_inhib")
        return f"{color} {lane} inhibitor"
    if b.kind == "nexus":
        return f"{color} nexus tower"
    return f"{color} {rest.replace('_', ' ')} tower"
