from conftest import SYNTHETIC_IDS

from lolreview.model import PlaceholderModel
from lolreview.patterns import patterns_of
from lolreview.review import build_review
from lolreview.schemas import Patterns

ZERO = {"!!": 0, "!": 0, "?": 0, "??": 0}
ME = {"participant_id": 1, "role": "MIDDLE", "team": "ally", "is_me": True}
FOE = {"participant_id": 6, "role": "MIDDLE", "team": "enemy", "is_me": False}


def review(
    result="win",
    moments=(),
    windows=(),
    curve=(0.5, 1.0),
    players=(),
    snapshots=(),
    duration_s=1865,
    me=ZERO,
):
    return {
        "match": {"result": result, "duration_s": duration_s},
        "players": list(players),
        "curve": [{"t": 60.0 * i, "p": p} for i, p in enumerate(curve)],
        "moments": list(moments),
        "windows": list(windows),
        "snapshots": list(snapshots),
        "summary": {"me": me, "team": ZERO, "biggest_id": ""},
    }


def moment(t, delta, zone="river", grade="?", drivers=(), me=True):
    return {
        "t_start": t,
        "t_end": t + 10,
        "delta": delta,
        "grade": grade,
        "zone": zone,
        "involves_me": me,
        "drivers": [{"label": label, "change": change} for label, change in drivers],
    }


def window(used, value):
    return {"used": used, "value": value}


def snap(t, my_gold, my_cs, their_gold, their_cs):
    return {
        "t": t,
        "players": [
            {"participant_id": 1, "gold": my_gold, "cs": my_cs},
            {"participant_id": 6, "gold": their_gold, "cs": their_cs},
        ],
    }


def test_empty_input():
    got = patterns_of([])
    assert got["games"] == 0 and got["wins"] == 0
    assert [r["label"] for r in got["by_phase"]] == [
        "Early game (0-14 min)",
        "Mid game (14-25 min)",
        "Late game (25+ min)",
    ]
    assert all(r["mistakes"] == 0 and r["lost"] == 0 for r in got["by_phase"])
    assert got["by_zone"] == [] and got["by_driver"] == []
    assert got["lane_gold_10"] is None and got["lane_cs_10"] is None
    assert Patterns.model_validate(got).games == 0


def test_phase_boundaries_and_what_counts_as_a_mistake():
    moments = [
        moment(839, -0.02),
        moment(840, -0.03),
        moment(1499, -0.01),
        moment(1500, -0.05),
        moment(100, -0.5, grade="!"),  # not a mistake
        moment(100, -0.5, me=False),  # not mine
    ]
    got = patterns_of([review(moments=moments)])
    assert [r["mistakes"] for r in got["by_phase"]] == [1, 2, 1]
    assert got["by_phase"][1]["lost"] == -0.04


def test_zones_sorted_most_lost_first_then_label_capped_at_five():
    deltas = {"river": -0.1, "top": -0.3, "bot": -0.3, "mid": -0.05, "jungle": -0.2, "base": -0.01}
    moments = [moment(100, d, zone=z) for z, d in deltas.items()]
    got = patterns_of([review(moments=moments)])
    assert [r["label"] for r in got["by_zone"]] == ["bot", "top", "jungle", "river", "mid"]


def test_games_count_distinct_games():
    reviews = [
        review(moments=[moment(100, -0.1), moment(200, -0.1)]),
        review(moments=[moment(100, -0.1)]),
    ]
    row = patterns_of(reviews)["by_zone"][0]
    assert (row["label"], row["mistakes"], row["games"]) == ("river", 3, 2)


def test_zone_drops_the_nearby_building():
    moments = [
        moment(100, -0.1, zone="mid lane, near your mid outer tower"),
        moment(200, -0.1, zone="mid lane"),
    ]
    rows = patterns_of([review(moments=moments)])["by_zone"]
    assert [(r["label"], r["mistakes"]) for r in rows] == [("mid lane", 2)]


def test_driver_is_the_most_negative_and_none_negative_is_skipped():
    moments = [
        moment(100, -0.1, drivers=[("Gold lead", -0.3), ("Baron buff", -0.5), ("Towers", 0.2)]),
        moment(200, -0.05, drivers=[("Gold lead", 0.1)]),
        moment(300, -0.2, drivers=[("Gold lead", -0.1)]),
        moment(400, -0.1, drivers=[("Baron buff", -0.2)]),
    ]
    got = patterns_of([review(moments=moments)])
    assert [(r["label"], r["mistakes"], r["games"], r["lost"]) for r in got["by_driver"]] == [
        ("Baron buff", 2, 1, -0.2),
        ("Gold lead", 1, 1, -0.2),
    ]


def test_windows_counts_and_missed_value():
    windows = [window(False, 0.1), window(False, 0.05), window(True, 0.3)]
    got = patterns_of([review(windows=windows)])
    assert (got["windows_missed"], got["windows_used"], got["missed_value"]) == (2, 1, 0.15)


def test_comeback_and_thrown_lead_ignore_the_result_point():
    got = patterns_of(
        [
            review(result="win", curve=(0.5, 0.1, 1.0)),  # comeback
            review(result="win", curve=(0.5, 0.2, 1.0)),  # 0.2 is not below 0.2
            review(result="win", curve=(0.5, 0.1)),  # the 0.1 is the last point: the result
            review(result="loss", curve=(0.5, 0.85, 0.0)),  # thrown lead
            review(result="loss", curve=(0.5, 0.8, 0.0)),  # 0.8 is not above 0.8
        ]
    )
    assert (got["comebacks"], got["thrown"]) == (1, 1)


def test_wins_and_grades_summed():
    me = {"!!": 1, "!": 0, "?": 2, "??": 1}
    got = patterns_of([review(result="win", me=me), review(result="loss", me=me)])
    assert (got["games"], got["wins"]) == (2, 1)
    assert got["grades"] == {"!!": 2, "!": 0, "?": 4, "??": 2}


def test_lane_at_ten_uses_snapshot_at_or_before_600():
    snaps = [snap(585, 5000, 80, 4800, 78), snap(615, 9000, 200, 1, 1)]
    got = patterns_of([review(players=[ME, FOE], snapshots=snaps)])
    assert (got["lane_gold_10"], got["lane_cs_10"]) == (200, 2)


def test_lane_average_over_games_and_skips():
    game = [snap(600, 5000, 80, 4800, 78)]  # +200 gold, +2 CS
    other = [snap(600, 5400, 84, 5000, 80)]  # +400 gold, +4 CS
    got = patterns_of(
        [
            review(players=[ME, FOE], snapshots=game),
            review(players=[ME, FOE], snapshots=other),
            review(players=[ME, FOE], snapshots=game, duration_s=599),  # too short
            review(players=[ME], snapshots=game),  # no opponent
        ]
    )
    assert (got["lane_gold_10"], got["lane_cs_10"]) == (300, 3)


def test_lane_none_when_no_game_counts():
    got = patterns_of([review(players=[ME, FOE], snapshots=[snap(615, 1, 1, 1, 1)])])
    assert got["lane_gold_10"] is None and got["lane_cs_10"] is None


def test_real_review_validates(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    champions = {
        p["championId"]: (p["championName"], p["championName"])
        for p in match["info"]["participants"]
    }
    built = build_review(match, timeline, 4, "GOLD", PlaceholderModel(), champions, "26.19.1")
    data = built.model_dump(mode="json", by_alias=True)
    got = Patterns.model_validate(patterns_of([data]))
    assert got.games == 1
    assert got.grades.model_dump(by_alias=True) == data["summary"]["me"]
