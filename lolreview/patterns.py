"""Patterns across reviewed games: where and why the player loses win chance.

Works on cached Review JSON dicts only, so it never calls Riot or builds a review.
"""

import math
from collections import Counter

PHASES = [
    ("Early game (0-14 min)", 840),
    ("Mid game (14-25 min)", 1500),
    ("Late game (25+ min)", math.inf),
]
MISTAKES = ("?", "??")
TOP = 5  # rows in the zone and driver tables
LANE_AT_S = 600  # the lane snapshot is taken at 10:00


def _add(tally: dict, label: str, game: int, delta: float) -> None:
    row = tally.setdefault(label, [0, set(), 0.0])  # mistakes, games, lost
    row[0] += 1
    row[1].add(game)
    row[2] += delta


def _rows(tally: dict) -> list[dict]:
    return [
        {"label": label, "mistakes": n, "games": len(games), "lost": round(lost, 3)}
        for label, (n, games, lost) in tally.items()
    ]


def _worst(tally: dict) -> list[dict]:
    return sorted(_rows(tally), key=lambda r: (r["lost"], r["label"]))[:TOP]


def _phase(t: float) -> str:
    return next(label for label, end in PHASES if t < end)


def _top_driver(moment: dict) -> str | None:
    negative = [d for d in moment.get("drivers", []) if d["change"] < 0]
    return min(negative, key=lambda d: d["change"])["label"] if negative else None


def _comeback(review: dict) -> str | None:
    """Same rule as comebackOf in ReviewHeader.tsx: the last curve point is the result."""
    points = review["curve"][:-1]
    if not points:
        return None
    if review["match"]["result"] == "win" and min(p["p"] for p in points) < 0.2:
        return "comeback"
    if review["match"]["result"] == "loss" and max(p["p"] for p in points) > 0.8:
        return "thrown"
    return None


def _lane_at_10(review: dict) -> tuple[int, int] | None:
    """My gold and CS minus my lane opponent's at 10:00, paired like laneDiff.ts."""
    players = review["players"]
    me = next((p for p in players if p["is_me"]), None)
    if me is None or review["match"]["duration_s"] < LANE_AT_S:
        return None
    opponent = next(
        (p for p in players if p["role"] == me["role"] and p["team"] != me["team"]), None
    )
    if opponent is None:
        return None
    point = None
    for snap in review["snapshots"]:
        if snap["t"] > LANE_AT_S:
            break
        by_id = {p["participant_id"]: p for p in snap["players"]}
        if me["participant_id"] in by_id and opponent["participant_id"] in by_id:
            mine, theirs = by_id[me["participant_id"]], by_id[opponent["participant_id"]]
            point = (mine["gold"] - theirs["gold"], mine["cs"] - theirs["cs"])
    return point


def _average(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def patterns_of(reviews: list[dict]) -> dict:
    """Summarise cached reviews (grade keys "!!", "!", "?", "??") as a Patterns dict."""
    grades = {"!!": 0, "!": 0, "?": 0, "??": 0}
    phases = {label: [0, set(), 0.0] for label, _ in PHASES}
    zones: dict = {}
    drivers: dict = {}
    kinds: Counter = Counter()
    windows_missed = windows_used = 0
    missed_value = 0.0
    lane_gold, lane_cs = [], []
    for game, review in enumerate(reviews):
        for grade in grades:
            grades[grade] += review["summary"]["me"][grade]
        kinds[_comeback(review)] += 1
        for m in review["moments"]:
            if not m["involves_me"] or m["grade"] not in MISTAKES:
                continue
            _add(phases, _phase(m["t_start"]), game, m["delta"])
            _add(zones, m["zone"].split(", near ")[0], game, m["delta"])  # the area, not the tower
            top = _top_driver(m)
            if top is not None:
                _add(drivers, top, game, m["delta"])
        for w in review.get("windows", []):
            if w["used"]:
                windows_used += 1
            else:
                windows_missed += 1
                missed_value += w["value"]
        lane = _lane_at_10(review)
        if lane is not None:
            lane_gold.append(lane[0])
            lane_cs.append(lane[1])
    return {
        "games": len(reviews),
        "wins": sum(r["match"]["result"] == "win" for r in reviews),
        "grades": grades,
        "by_phase": _rows(phases),
        "by_zone": _worst(zones),
        "by_driver": _worst(drivers),
        "windows_missed": windows_missed,
        "windows_used": windows_used,
        "missed_value": round(missed_value, 3),
        "comebacks": kinds["comeback"],
        "thrown": kinds["thrown"],
        "lane_gold_10": _average(lane_gold),
        "lane_cs_10": _average(lane_cs),
    }
