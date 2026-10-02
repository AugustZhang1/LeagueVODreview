import json
from collections import Counter

import consistency
import make_synthetic
import pytest
from conftest import SYNTHETIC, SYNTHETIC_IDS

CHECKS = [pytest.param(c, id=c.__name__) for c in consistency.ALL_CHECKS]


@pytest.mark.parametrize("match_id", SYNTHETIC_IDS)
@pytest.mark.parametrize("check", CHECKS)
def test_consistency(load_game, match_id, check):
    match, timeline = load_game(match_id)
    check(match, timeline)


def events(timeline, *types):
    return consistency.of_type(timeline, *types)


def test_committed_files_match_generator(load_game):
    for g in make_synthetic.GAMES:
        match, timeline = make_synthetic.generate(g)
        assert (match, timeline) == load_game(g["match_id"])
        raw = (SYNTHETIC / f"{g['match_id']}.match.json").read_text()
        assert raw == json.dumps(match, separators=(",", ":")) + "\n"


def test_match_shape(synthetic_games):
    for match, _ in synthetic_games:
        info = match["info"]
        assert info["gameMode"] == "CLASSIC" and info["gameType"] == "MATCHED_GAME"
        assert info["mapId"] == 11 and info["queueId"] == 420 and info["platformId"] == "NA1"
        assert info["gameVersion"].startswith("26.19.")
        assert info["gameEndTimestamp"] > info["gameStartTimestamp"] > info["gameCreation"]
        for p in info["participants"]:
            for key in ("puuid", "riotIdGameName", "riotIdTagline", "championId", "championName"):
                assert p[key] not in (None, "")
            assert all(f"item{i}" in p for i in range(7))
            assert 0 <= p["item6"] <= 3364
        for team in info["teams"]:
            assert len(team["bans"]) == 5
            assert set(team["objectives"]) == {
                "baron", "champion", "dragon", "horde", "inhibitor",
                "riftHerald", "tower", "atakhan",
            }  # fmt: skip


def test_game1(load_game):
    match, timeline = load_game("NA1_9000000001")
    me = match["info"]["participants"][3]
    assert (me["riotIdGameName"], me["riotIdTagline"]) == ("Me", "NA1")
    assert me["teamPosition"] == "MIDDLE" and me["championId"] == 103
    assert match["info"]["gameDuration"] in range(30 * 60, 32 * 60)
    assert [t["win"] for t in match["info"]["teams"]] == [True, False]
    kills = events(timeline, "CHAMPION_SPECIAL_KILL")
    assert sum(e["killType"] == "KILL_FIRST_BLOOD" for e in kills) == 1
    monsters = Counter(e["monsterType"] for e in events(timeline, "ELITE_MONSTER_KILL"))
    assert monsters["DRAGON"] == 4 and monsters["BARON_NASHOR"] == 1
    assert monsters["HORDE"] == 3 and monsters["RIFTHERALD"] == 1
    soul = events(timeline, "DRAGON_SOUL_GIVEN")
    assert len(soul) == 1 and soul[0]["teamId"] == 100
    assert events(timeline, "TURRET_PLATE_DESTROYED")
    assert any(e["buildingType"] == "INHIBITOR_BUILDING" for e in events(timeline, "BUILDING_KILL"))


def test_game2_surrender(load_game):
    match, timeline = load_game("NA1_9000000002")
    parts = match["info"]["participants"]
    assert all(p["gameEndedInSurrender"] for p in parts)
    assert not any(p["gameEndedInEarlySurrender"] for p in parts)
    me = next(p for p in parts if p["riotIdGameName"] == "Me")
    assert (me["teamId"], me["teamPosition"], me["championId"]) == (200, "BOTTOM", 222)
    assert me["win"] and match["info"]["gameDuration"] == 24 * 60 + 30
    assert events(timeline, "GAME_END")[0]["winningTeam"] == 200


def test_game3_elder_and_atakhan(load_game):
    match, timeline = load_game("NA1_9000000003")
    subtypes = [e.get("monsterSubType") for e in events(timeline, "ELITE_MONSTER_KILL")]
    assert "ELDER_DRAGON" in subtypes
    assert any(e["monsterType"] == "ATAKHAN" for e in events(timeline, "ELITE_MONSTER_KILL"))
    names = {p["championName"]: p["championId"] for p in match["info"]["participants"]}
    assert names["MonkeyKing"] == 62 and names["FiddleSticks"] == 9
    inhib = Counter(
        (e["teamId"], e["laneType"])
        for e in events(timeline, "BUILDING_KILL")
        if e["buildingType"] == "INHIBITOR_BUILDING"
    )
    assert max(inhib.values()) >= 2, "an inhibitor is destroyed again after respawning"
    assert match["info"]["gameDuration"] in range(37 * 60, 39 * 60)


def test_game4_remake(load_game):
    match, timeline = load_game("NA1_9000000004")
    assert all(p["gameEndedInEarlySurrender"] for p in match["info"]["participants"])
    assert match["info"]["gameDuration"] == 190
    assert not events(timeline, "CHAMPION_KILL")
    assert len(timeline["info"]["frames"]) == 5
