import copy
from collections import Counter

import pytest
from conftest import REAL_IDS

from lolreview import features as F
from lolreview.constants import BLUE, RED

GAME_IDS = [f"NA1_900000000{i}" for i in range(1, 4)] + REAL_IDS
OBJ_KEYS = {"tower": "towers", "baron": "barons", "horde": "grubs", "riftHerald": "heralds"}


@pytest.fixture(scope="module", params=GAME_IDS)
def game(request, load_game):
    return load_game(request.param)


def all_events(timeline):
    return [e for f in timeline["info"]["frames"] for e in f["events"]]


def end_ms(timeline):
    return timeline["info"]["frames"][-1]["timestamp"]


def cut(timeline, t):
    frames = [
        {**f, "events": [e for e in f["events"] if e["timestamp"] <= t]}
        for f in timeline["info"]["frames"]
        if f["timestamp"] <= t
    ]
    return {**timeline, "info": {**timeline["info"], "frames": frames}}


def test_final_objectives_match_teams(game):
    match, timeline = game
    state = F.state_at(match, timeline, end_ms(timeline))
    for team in match["info"]["teams"]:
        ts = state.teams[team["teamId"]]
        obj = team["objectives"]
        assert ts.kills == obj["champion"]["kills"]
        for key, attr in OBJ_KEYS.items():
            assert getattr(ts, attr) == obj[key]["kills"], (team["teamId"], key)
        assert len(ts.dragons) + ts.elders == obj["dragon"]["kills"]
        assert ts.atakhans == obj.get("atakhan", {}).get("kills", 0)


def test_team_gold_at_minute_frames(game):
    match, timeline = game
    frames = timeline["info"]["frames"]
    states = F.states_at(match, timeline, [f["timestamp"] for f in frames])
    for f, state in zip(frames, states, strict=True):
        for team in (BLUE, RED):
            ids = range(1, 6) if team == BLUE else range(6, 11)
            total = sum(f["participantFrames"][str(i)]["totalGold"] for i in ids)
            assert state.teams[team].gold == total


def test_no_future_leak(game):
    match, timeline = game
    full = {r["t"]: r for r in F.extract_rows(match, timeline, "GOLD")}
    end = end_ms(timeline)
    for t in (90_000, 421_000, end // 2, end * 3 // 4, end):
        part = F.extract_rows(match, cut(timeline, t), "GOLD")
        assert part
        for row in part:
            if row["t"] <= t:
                assert row == full[row["t"]], (t, row["t"])


def test_states_at_equals_state_at(game):
    match, timeline = game
    end = end_ms(timeline)
    times = [end, 0, 61_000, end // 3, 61_000, 15_000 + end // 2]
    many = F.states_at(match, timeline, times)
    for t, state in zip(times, many, strict=True):
        assert state == F.state_at(match, timeline, t)


def test_final_kda_and_items(game):
    match, timeline = game
    state = F.state_at(match, timeline, end_ms(timeline))
    for p in match["info"]["participants"]:
        ps = state.players[p["participantId"]]
        assert (ps.k, ps.d, ps.a) == (p["kills"], p["deaths"], p["assists"])
        held = Counter(i for i in ps.items if i)
        assert held == Counter(p[f"item{i}"] for i in range(6) if p[f"item{i}"])
        assert (ps.trinket or 0) == p["item6"]
        assert ps.level == p["champLevel"]


def test_nobody_kills_while_dead(game):
    # Real games have kills up to ~3 s after the killer died (damage over time) and assists up to
    # ~18 s after (the assist window), so only killers are checked, from 5 s after their death.
    match, timeline = game
    walker = F._Walker(match, F.load_config())
    died: dict[int, int] = {}
    for f in timeline["info"]["frames"]:
        for e in f["events"]:
            a, t = e.get("killerId"), e["timestamp"]
            if e["type"] in ("CHAMPION_KILL", "ELITE_MONSTER_KILL", "BUILDING_KILL") and a:
                if t - died.get(a, -(10**9)) > 5000:
                    assert walker.players[a].dead_until_ms <= t, (a, t)
            if e["type"] == "CHAMPION_KILL":
                died[e["victimId"]] = t
            walker.apply_event(e)
        walker.apply_frame(f)


def test_respawn_rises_with_level_and_time():
    cfg = F.load_config()
    assert F.respawn_seconds(3, 100, cfg) < F.respawn_seconds(11, 100, cfg)
    times = [60, 900, 1500, 2400, 3000, 4000]
    vals = [F.respawn_seconds(14, t, cfg) for t in times]
    assert vals == sorted(vals) and vals[0] < vals[-1]
    assert F.respawn_seconds(18, 10_000, cfg) == pytest.approx(52.5 * 1.5)


def test_victim_dead_and_position_set(load_game):
    match, timeline = load_game("NA1_9000000001")
    kill = next(e for e in all_events(timeline) if e["type"] == "CHAMPION_KILL")
    state = F.state_at(match, timeline, kill["timestamp"])
    v = state.players[kill["victimId"]]
    assert v.dead_until_ms > kill["timestamp"]
    assert (v.x, v.y, v.pos_t_ms) == (
        kill["position"]["x"],
        kill["position"]["y"],
        kill["timestamp"],
    )
    k = state.players[kill["killerId"]]
    assert (k.x, k.y) == (v.x, v.y)
    assert any(rk[0] == kill["timestamp"] for rk in state.recent_kills)
    later = F.state_at(match, timeline, kill["timestamp"] + 11_000)
    assert all(rk[0] != kill["timestamp"] for rk in later.recent_kills)


def test_skip_reasons(load_game):
    match, _ = load_game("NA1_9000000001")
    assert F.skip_reason(match) is None
    other = copy.deepcopy(match)
    other["info"]["queueId"] = 450
    assert F.skip_reason(other) == "not_ranked_solo"
    remake, remake_tl = load_game("NA1_9000000004")
    assert F.skip_reason(remake) == "remake"
    assert F.extract_rows(remake, remake_tl, "GOLD") == []
    assert F.extract_rows(other, _, "GOLD") == []


def test_patch_of(load_game):
    match, _ = load_game("NA1_9000000001")
    assert F.patch_of(match) == "26.19"


def test_soul_from_event_and_from_counting(load_game):
    match, timeline = load_game("NA1_9000000001")
    end = end_ms(timeline)
    soul_evt = next(e for e in all_events(timeline) if e["type"] == "DRAGON_SOUL_GIVEN")
    state = F.state_at(match, timeline, end)
    assert state.teams[soul_evt["teamId"]].soul == soul_evt["name"]
    assert state.map_soul_type == soul_evt["name"]
    assert F.state_at(match, timeline, soul_evt["timestamp"] - 1).teams[
        soul_evt["teamId"]
    ].soul in (
        None,
        soul_evt["name"],
    )

    stripped = copy.deepcopy(timeline)
    for f in stripped["info"]["frames"]:
        f["events"] = [e for e in f["events"] if e["type"] != "DRAGON_SOUL_GIVEN"]
    counted = F.state_at(match, stripped, end)
    assert counted.teams[soul_evt["teamId"]].soul == soul_evt["name"]
    other = RED if soul_evt["teamId"] == BLUE else BLUE
    assert counted.teams[other].soul is None
    row = F.feature_row(counted, "GOLD")
    assert row["soul_diff"] == (1 if soul_evt["teamId"] == BLUE else -1)
    assert row["soul_type"] == soul_evt["name"]
    pre = F.state_at(match, stripped, 0)
    assert pre.map_soul_type == "none"


def test_buff_expiry(load_game):
    match, timeline = load_game("NA1_9000000003")
    baron = next(
        e
        for e in all_events(timeline)
        if e["type"] == "ELITE_MONSTER_KILL" and e["monsterType"] == "BARON_NASHOR"
    )
    team = baron["killerTeamId"]
    dur = int(F.load_config()["timers"]["baron_buff_s"] * 1000)
    sign = 1 if team == BLUE else -1
    t = baron["timestamp"]
    during = F.state_at(match, timeline, t + dur - 1)
    after = F.state_at(match, timeline, t + dur)
    assert during.teams[team].buff == ("baron", t + dur)
    assert F.feature_row(during, "GOLD")["baron_active"] == sign
    assert after.teams[team].buff is None
    assert F.feature_row(after, "GOLD")["baron_active"] == 0

    elder = next(
        e
        for e in all_events(timeline)
        if e["type"] == "ELITE_MONSTER_KILL" and e.get("monsterSubType") == "ELDER_DRAGON"
    )
    s = F.state_at(match, timeline, elder["timestamp"])
    assert F.feature_row(s, "GOLD")["elder_active"] == (1 if elder["killerTeamId"] == BLUE else -1)


def test_inhibitor_respawn(load_game):
    match, timeline = load_game("NA1_9000000003")
    kill = next(
        e
        for e in all_events(timeline)
        if e["type"] == "BUILDING_KILL" and e["buildingType"] == "INHIBITOR_BUILDING"
    )
    owner = "blue" if kill["teamId"] == BLUE else "red"
    bid = f"{owner}_{F.LANES[kill['laneType']]}_inhib"
    back = int(F.load_config()["timers"]["inhibitor_respawn_s"] * 1000)
    t = kill["timestamp"]
    down = F.state_at(match, timeline, t)
    assert bid in down.buildings_down
    assert down.teams[kill["teamId"]].inhibs_down >= 1
    up = F.state_at(match, timeline, t + back)
    assert bid not in up.buildings_down
    row = F.feature_row(down, "GOLD")
    assert (
        row["inhibs_down_diff"]
        == (-1 if owner == "blue" else 1) * down.teams[kill["teamId"]].inhibs_down
    )


def test_building_ids_valid(game):
    match, timeline = game
    import re

    pattern = re.compile(r"^(blue|red)_((top|mid|bot)_(outer|inner|base|inhib)|nexus_[12])$")
    state = F.state_at(match, timeline, end_ms(timeline))
    destroyed = [e for e in all_events(timeline) if e["type"] == "BUILDING_KILL"]
    assert destroyed
    towers = [e for e in destroyed if e["buildingType"] == "TOWER_BUILDING"]
    assert len(state.buildings_down) >= len(towers)
    assert all(pattern.match(b) for b in state.buildings_down), state.buildings_down
    assert len({b for b in state.buildings_down if "nexus" in b}) == sum(
        1 for e in towers if e["towerType"] == "NEXUS_TURRET"
    )


def test_extract_rows_shape(game):
    match, timeline = game
    rows = F.extract_rows(match, timeline, "PLATINUM")
    ts = [r["t"] for r in rows]
    assert ts == sorted(set(ts))
    for f in timeline["info"]["frames"]:
        assert f["timestamp"] in ts
    assert set(rows[0]) == set(F.FEATURE_COLUMNS + F.EXTRA_COLUMNS)
    assert rows[0]["tier"] == 4
    assert rows[0]["match_id"] == match["metadata"]["matchId"]
    blue_won = next(t for t in match["info"]["teams"] if t["teamId"] == BLUE)["win"]
    assert all(r["blue_won"] == int(blue_won) for r in rows)
    kill = next(e for e in all_events(timeline) if e["type"] == "CHAMPION_KILL")
    assert kill["timestamp"] + 1 in ts
    assert F.feature_row(F.state_at(match, timeline, 0), 7)["tier"] == 7


def test_monotone_covers_columns():
    assert list(F.MONOTONE) == F.FEATURE_COLUMNS
    assert F.MONOTONE["red_dragons"] == -1 and F.MONOTONE["tier"] == 0


def test_items_rebuild_events():
    match = {
        "info": {"participants": [{"participantId": 1, "teamId": BLUE, "teamPosition": "TOP"}]}
    }
    evs = [
        {"type": "ITEM_PURCHASED", "itemId": 3340, "participantId": 1, "timestamp": 1},
        {"type": "ITEM_PURCHASED", "itemId": 1001, "participantId": 1, "timestamp": 2},
        {"type": "ITEM_PURCHASED", "itemId": 1042, "participantId": 1, "timestamp": 3},
        {"type": "ITEM_DESTROYED", "itemId": 1001, "participantId": 1, "timestamp": 4},
        {"type": "ITEM_DESTROYED", "itemId": 1042, "participantId": 1, "timestamp": 4},
        {"type": "ITEM_PURCHASED", "itemId": 3006, "participantId": 1, "timestamp": 4},
        {"type": "ITEM_SOLD", "itemId": 3340, "participantId": 1, "timestamp": 5},
        {
            "type": "ITEM_UNDO",
            "beforeId": 3006,
            "afterId": 1001,
            "participantId": 1,
            "timestamp": 6,
        },
    ]
    timeline = {"info": {"frames": [{"timestamp": 0, "participantFrames": {}, "events": evs}]}}
    s = F.state_at(match, timeline, 3)
    assert [i for i in s.players[1].items if i] == [1001, 1042] and s.players[1].trinket == 3340
    s = F.state_at(match, timeline, 5)
    assert [i for i in s.players[1].items if i] == [3006] and s.players[1].trinket is None
    s = F.state_at(match, timeline, 6)
    assert [i for i in s.players[1].items if i] == [1001]


def test_rows_to_table(game):
    pa = pytest.importorskip("pyarrow")
    match, timeline = game
    rows = F.extract_rows(match, timeline, "GOLD")
    table = F.rows_to_table(rows)
    assert table.num_rows == len(rows)
    assert table.column_names == F.FEATURE_COLUMNS + F.EXTRA_COLUMNS
    schema = table.schema
    assert schema.field("gold_diff").type == pa.float32()
    assert schema.field("minute").type == pa.float32()
    assert schema.field("kill_diff").type == pa.int16()
    assert schema.field("tier").type == pa.int16()
    for name in ("soul_type", "platform", "patch"):
        assert pa.types.is_dictionary(schema.field(name).type)
    assert table.column("soul_type").to_pylist() == [r["soul_type"] for r in rows]
    assert table.column("patch").to_pylist() == [r["patch"] for r in rows]
