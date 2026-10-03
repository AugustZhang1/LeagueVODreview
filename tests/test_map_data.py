import pytest
from conftest import SYNTHETIC_IDS

from lolreview import map_data
from lolreview.features import _building_id

LO, HI = map_data.BOUNDS


def test_building_counts():
    b = map_data.BUILDINGS.values()
    assert len(map_data.BUILDINGS) == 2 * (9 + 3 + 2)
    for team in ("blue", "red"):
        mine = [x for x in b if x.team == team]
        assert sum(x.kind == "tower" for x in mine) == 9
        assert sum(x.kind == "inhibitor" for x in mine) == 3
        assert sum(x.kind == "nexus" for x in mine) == 2
    assert all(LO <= x.x <= HI and LO <= x.y <= HI for x in b)


@pytest.mark.parametrize(
    "bid,zone",
    [
        ("blue_top_outer", "top lane"),
        ("blue_top_inner", "top lane"),
        ("blue_top_base", "blue base"),
        ("blue_mid_outer", "mid lane"),
        ("blue_mid_inner", "mid lane"),
        ("blue_mid_base", "blue base"),
        ("blue_bot_outer", "bot lane"),
        ("blue_bot_inner", "bot lane"),
        ("blue_bot_base", "blue base"),
        ("blue_top_inhib", "blue base"),
        ("blue_mid_inhib", "blue base"),
        ("blue_bot_inhib", "blue base"),
        ("blue_nexus_1", "blue base"),
        ("blue_nexus_2", "blue base"),
        ("red_top_outer", "top lane"),
        ("red_top_inner", "top lane"),
        ("red_top_base", "red base"),
        ("red_mid_outer", "mid lane"),
        ("red_mid_inner", "mid lane"),
        ("red_mid_base", "red base"),
        ("red_bot_outer", "bot lane"),
        ("red_bot_inner", "bot lane"),
        ("red_bot_base", "red base"),
        ("red_top_inhib", "red base"),
        ("red_mid_inhib", "red base"),
        ("red_bot_inhib", "red base"),
        ("red_nexus_1", "red base"),
        ("red_nexus_2", "red base"),
    ],
)
def test_building_zone(bid, zone):
    b = map_data.BUILDINGS[bid]
    assert map_data.zone_of(b.x, b.y) == zone


def test_corners_and_pits():
    assert map_data.zone_of(LO, LO) == "blue base"
    assert map_data.zone_of(HI, HI) == "red base"
    assert map_data.zone_of(LO, HI) == "top lane"
    assert map_data.zone_of(HI, LO) == "bot lane"
    assert map_data.zone_of(9866, 4414) == "dragon pit"
    assert map_data.zone_of(5007, 10471) == "baron pit"
    assert map_data.zone_of(7400, 7400) == "mid lane"


def test_rivers_and_jungles():
    assert map_data.zone_of(3000, 11500) == "top river"
    assert map_data.zone_of(11500, 3000) == "bot river"
    assert map_data.zone_of(4000, 7500) == "blue jungle (top side)"
    assert map_data.zone_of(7500, 3500) == "blue jungle (bot side)"
    assert map_data.zone_of(7500, 11300) == "red jungle (top side)"
    assert map_data.zone_of(11300, 7300) == "red jungle (bot side)"


def test_zone_with_team():
    assert map_data.zone_of(4000, 7500, "blue") == "your jungle (top side)"
    assert map_data.zone_of(4000, 7500, "red") == "enemy jungle (top side)"
    assert map_data.zone_of(11300, 7300, "blue") == "enemy jungle (bot side)"
    assert map_data.zone_of(HI, HI, "blue") == "enemy base"
    assert map_data.zone_of(7400, 7400, "red") == "mid lane"


def test_every_point_has_a_zone():
    for x in range(LO, HI + 1, 700):
        for y in range(LO, HI + 1, 700):
            assert map_data.zone_of(x, y) != "the map", (x, y)


def test_camps():
    kinds = {c.kind for c in map_data.CAMPS}
    assert {"blue_buff", "red_buff", "gromp", "wolves", "raptors", "krugs", "scuttle"} <= kinds
    assert sum(c.team == "blue" for c in map_data.CAMPS) == 6
    for c in map_data.CAMPS:
        assert LO <= c.x <= HI and LO <= c.y <= HI


def test_nearest_building_and_names():
    ids = set(map_data.BUILDINGS)
    assert map_data.nearest_building(5800, 6400, ids) == "blue_mid_outer"
    assert map_data.nearest_building(7400, 7400, ids) is None
    assert map_data.nearest_building(5800, 6400, ids - {"blue_mid_outer"}) is None
    assert map_data.nearest_building(5800, 6400, ids - {"blue_mid_outer"}, 3000) == "blue_mid_inner"
    assert map_data.building_name("red_mid_outer") == "red mid outer tower"
    assert map_data.building_name("blue_top_inhib") == "blue top inhibitor"
    assert map_data.building_name("red_nexus_2") == "red nexus tower"
    assert map_data.building_name("red_mid_outer", "blue") == "enemy mid outer tower"
    assert map_data.building_name("blue_mid_outer", "blue") == "your mid outer tower"


def test_ids_match_features_scheme(synthetic_games):
    seen = 0
    for _match, timeline in synthetic_games:
        nexus_seen: dict[str, int] = {}
        for f in timeline["info"]["frames"]:
            for e in f["events"]:
                if e["type"] == "BUILDING_KILL":
                    assert _building_id(e, nexus_seen) in map_data.BUILDINGS
                    seen += 1
    assert seen > 0
    assert len(SYNTHETIC_IDS) == 4


def test_side_of():
    assert map_data.side_of(1000, 1000) == "blue"
    assert map_data.side_of(13000, 13000) == "red"
    # the pits mirror each other across the map's center, so they're on opposite sides
    assert map_data.side_of(*map_data.BARON_PIT) == "red"
    assert map_data.side_of(*map_data.DRAGON_PIT) == "blue"
    assert map_data.zone_of(*map_data.BARON_PIT) == "baron pit"
