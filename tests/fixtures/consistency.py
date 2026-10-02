"""Internal-consistency rules for match + timeline JSON (synthetic or real).

Each check raises AssertionError on a violation. The generator runs all of them; the tests run
them one by one per game.
"""

import tomllib
from collections import Counter
from pathlib import Path

from item_table import ITEMS, TRINKETS, plan_buy

CFG = tomllib.loads((Path(__file__).resolve().parents[2] / "config.toml").read_text())
TIMERS = CFG["timers"]
BASE_RESPAWN = CFG["respawn"]["base_by_level"]

BLUE, RED = 100, 200
SOUL_NAMES = {"Infernal", "Mountain", "Ocean", "Cloud", "Hextech", "Chemtech"}


def level_from_xp(xp: int) -> int:
    level, need = 1, 0
    while level < 18:
        need += 180 + 100 * level
        if xp < need:
            break
        level += 1
    return level


def team_of(pid: int) -> int:
    return BLUE if pid <= 5 else RED


def events(timeline: dict) -> list[dict]:
    return [e for f in timeline["info"]["frames"] for e in f["events"]]


def of_type(timeline: dict, *types: str) -> list[dict]:
    return [e for e in events(timeline) if e["type"] in types]


def participants(match: dict) -> dict[int, dict]:
    return {p["participantId"]: p for p in match["info"]["participants"]}


def check_structure(match: dict, timeline: dict) -> None:
    info = match["info"]
    assert match["metadata"]["matchId"] == f"{info['platformId']}_{info['gameId']}"
    assert match["metadata"]["participants"] == [p["puuid"] for p in info["participants"]]
    assert [p["participantId"] for p in info["participants"]] == list(range(1, 11))
    assert [p["teamId"] for p in info["participants"]] == [BLUE] * 5 + [RED] * 5
    assert [t["teamId"] for t in info["teams"]] == [BLUE, RED]
    assert timeline["info"]["gameId"] == info["gameId"]
    assert timeline["info"]["frameInterval"] == 60000
    assert [p["puuid"] for p in timeline["info"]["participants"]] == [
        p["puuid"] for p in info["participants"]
    ]
    frames = timeline["info"]["frames"]
    stamps = [f["timestamp"] for f in frames]
    assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)
    minutes = [s // 60000 for s in stamps[:-1]]
    assert stamps[:-1] == [m * 60000 for m in range(len(minutes))], "one frame per minute"
    assert stamps[-1] > stamps[-2]
    for f in frames:
        assert sorted(f["participantFrames"], key=int) == [str(i) for i in range(1, 11)]
        for pf in f["participantFrames"].values():
            assert 0 <= pf["position"]["x"] <= 14820 and 0 <= pf["position"]["y"] <= 14820
    evs = events(timeline)
    assert [e["timestamp"] for e in evs] == sorted(e["timestamp"] for e in evs)
    for f in frames:
        prev = stamps[stamps.index(f["timestamp"]) - 1] if f["timestamp"] else -1
        assert all(prev < e["timestamp"] <= f["timestamp"] for e in f["events"])


def check_kda(match: dict, timeline: dict) -> None:
    kills, deaths, assists = Counter(), Counter(), Counter()
    for e in of_type(timeline, "CHAMPION_KILL"):
        kills[e["killerId"]] += 1
        deaths[e["victimId"]] += 1
        for a in e.get("assistingParticipantIds", []):
            assists[a] += 1
    for pid, p in participants(match).items():
        assert (p["kills"], p["deaths"], p["assists"]) == (kills[pid], deaths[pid], assists[pid])


def check_objectives(match: dict, timeline: dict) -> None:
    got: dict[int, Counter] = {BLUE: Counter(), RED: Counter()}
    first: dict[str, int] = {}
    mapping = {
        "DRAGON": "dragon",
        "BARON_NASHOR": "baron",
        "RIFTHERALD": "riftHerald",
        "HORDE": "horde",
        "ATAKHAN": "atakhan",
    }

    def credit(team: int, key: str) -> None:
        got[team][key] += 1
        first.setdefault(key, team)

    for e in events(timeline):
        if e["type"] == "ELITE_MONSTER_KILL":
            credit(e["killerTeamId"], mapping[e["monsterType"]])
        elif e["type"] == "CHAMPION_KILL":
            credit(team_of(e["killerId"]), "champion")
        elif e["type"] == "BUILDING_KILL":
            killers = RED if e["teamId"] == BLUE else BLUE
            credit(killers, "tower" if e["buildingType"] == "TOWER_BUILDING" else "inhibitor")
    for team in match["info"]["teams"]:
        for key, obj in team["objectives"].items():
            assert obj["kills"] == got[team["teamId"]][key], (team["teamId"], key)
            assert obj["first"] == (first.get(key) == team["teamId"]), (team["teamId"], key)
        assert {"baron", "champion", "dragon", "horde", "inhibitor", "riftHerald", "tower"} <= set(
            team["objectives"]
        )
        assert "atakhan" in team["objectives"]


def replay_items(timeline: dict) -> dict[int, list[int]]:
    """Inventories after replaying item events; also checks that combines consume components."""
    inv: dict[int, list[int]] = {i: [] for i in range(1, 11)}
    pending: dict[tuple[int, int], list[int]] = {}
    for e in of_type(timeline, "ITEM_PURCHASED", "ITEM_SOLD", "ITEM_DESTROYED", "ITEM_UNDO"):
        pid = e["participantId"]
        mine = inv[pid]
        key = (pid, e["timestamp"])
        if e["type"] == "ITEM_DESTROYED":
            mine.remove(e["itemId"])
            pending.setdefault(key, []).append(e["itemId"])
        elif e["type"] == "ITEM_SOLD":
            mine.remove(e["itemId"])
        elif e["type"] == "ITEM_UNDO":
            mine.remove(e["beforeId"])
            if e["afterId"]:
                mine.append(e["afterId"])
        else:
            item = e["itemId"]
            destroyed = pending.pop(key, [])
            expected, _ = plan_buy(mine + destroyed, item)
            if item in ITEMS and ITEMS[item][2]:
                assert Counter(destroyed) == Counter(expected), (pid, item, destroyed, expected)
            else:
                assert not destroyed or item in TRINKETS or ITEMS[item][2] == []
            mine.append(item)
    return inv


def check_items(match: dict, timeline: dict) -> None:
    inv = replay_items(timeline)
    for pid, p in participants(match).items():
        slots = [p[f"item{i}"] for i in range(6)]
        held = Counter(i for i in inv[pid] if i not in TRINKETS)
        assert Counter(i for i in slots if i) == held, (pid, slots, inv[pid])
        trinkets = [i for i in inv[pid] if i in TRINKETS]
        assert len(trinkets) <= 1
        assert p["item6"] == (trinkets[0] if trinkets else 0)
        assert sum(1 for i in slots if i) <= 6


def check_gold(match: dict, timeline: dict) -> None:
    frames = timeline["info"]["frames"]
    for a, b in zip(frames, frames[1:], strict=False):
        window = [e for e in b["events"] if a["timestamp"] < e["timestamp"] <= b["timestamp"]]
        for pid in range(1, 11):
            pa, pb = a["participantFrames"][str(pid)], b["participantFrames"][str(pid)]
            gained = pb["totalGold"] - pa["totalGold"]
            assert gained >= 0, (pid, b["timestamp"])
            floor = 0
            for e in window:
                if e["type"] == "CHAMPION_KILL" and e["killerId"] == pid:
                    floor += e["bounty"] + e["shutdownBounty"]
                elif e["type"] in ("ELITE_MONSTER_KILL", "BUILDING_KILL") and e["killerId"] == pid:
                    floor += e["bounty"]
            assert gained >= floor - 1, (pid, b["timestamp"], gained, floor)
            assert pb["currentGold"] >= 0
    for pid, p in participants(match).items():
        last = frames[-1]["participantFrames"][str(pid)]
        assert p["goldEarned"] == last["totalGold"]
        assert p["totalMinionsKilled"] == last["minionsKilled"]
        assert p["neutralMinionsKilled"] == last["jungleMinionsKilled"]
        assert p["champLevel"] == last["level"]


def check_levels(match: dict, timeline: dict) -> None:
    prev_level = {i: 1 for i in range(1, 11)}
    for f in timeline["info"]["frames"]:
        for key, pf in f["participantFrames"].items():
            assert pf["level"] == level_from_xp(pf["xp"]), (key, f["timestamp"])
            assert pf["level"] >= prev_level[int(key)]
            prev_level[int(key)] = pf["level"]
    ups: dict[int, int] = {i: 1 for i in range(1, 11)}
    for e in of_type(timeline, "LEVEL_UP"):
        assert e["level"] == ups[e["participantId"]] + 1
        ups[e["participantId"]] = e["level"]
    final = timeline["info"]["frames"][-1]["participantFrames"]
    assert ups == {int(k): v["level"] for k, v in final.items()}


def check_alive(match: dict, timeline: dict) -> None:
    level = {i: 1 for i in range(1, 11)}
    dead_until = {i: 0 for i in range(1, 11)}
    for e in events(timeline):
        t = e["timestamp"]
        if e["type"] == "LEVEL_UP":
            level[e["participantId"]] = e["level"]
            continue
        actors: list[int] = []
        if e["type"] == "CHAMPION_KILL":
            actors = [e["killerId"], e["victimId"], *e.get("assistingParticipantIds", [])]
        elif e["type"] in ("ELITE_MONSTER_KILL", "BUILDING_KILL"):
            actors = [e["killerId"], *e.get("assistingParticipantIds", [])]
        for a in actors:
            if a:
                assert t >= dead_until[a], (a, t, dead_until[a])
        if e["type"] == "CHAMPION_KILL":
            v = e["victimId"]
            dead_until[v] = t + int(BASE_RESPAWN[level[v] - 1] * 1000)


def check_timers(match: dict, timeline: dict) -> None:
    last: dict[str, int] = {}
    soul_ts = None
    for e in events(timeline):
        if e["type"] == "DRAGON_SOUL_GIVEN":
            soul_ts = e["timestamp"]
        if e["type"] != "ELITE_MONSTER_KILL":
            continue
        t = e["timestamp"]
        mt = e["monsterType"]
        if mt == "DRAGON" and e["monsterSubType"] == "ELDER_DRAGON":
            assert soul_ts is not None and t >= soul_ts + TIMERS["elder_first_s"] * 1000
            kind = "ELDER"
        elif mt == "DRAGON":
            assert t >= TIMERS["dragon_first_s"] * 1000
            kind = "DRAGON"
        else:
            key = {"HORDE": "grubs", "RIFTHERALD": "herald", "BARON_NASHOR": "baron"}.get(mt)
            key = key or "atakhan"
            assert t >= TIMERS[f"{key}_first_s"] * 1000, (mt, t)
            kind = mt
        if kind in ("DRAGON", "ELDER", "BARON_NASHOR", "ATAKHAN", "RIFTHERALD"):
            key = {"DRAGON": "dragon", "ELDER": "elder", "BARON_NASHOR": "baron"}.get(
                kind, kind.lower()
            )
            if kind in last:
                assert t - last[kind] >= TIMERS[f"{key}_respawn_s"] * 1000, (kind, t)
            last[kind] = t
    inhib_down: dict[tuple[int, str], int] = {}
    for e in of_type(timeline, "BUILDING_KILL"):
        if e["buildingType"] == "INHIBITOR_BUILDING":
            key = (e["teamId"], e["laneType"])
            if key in inhib_down:
                assert e["timestamp"] - inhib_down[key] >= TIMERS["inhibitor_respawn_s"] * 1000
            inhib_down[key] = e["timestamp"]


def check_dragons(match: dict, timeline: dict) -> None:
    kills = [e for e in of_type(timeline, "ELITE_MONSTER_KILL") if e["monsterType"] == "DRAGON"]
    per_team: Counter = Counter()
    souls = of_type(timeline, "DRAGON_SOUL_GIVEN")
    log = []
    for e in kills:
        if e["monsterSubType"] == "ELDER_DRAGON":
            continue
        log.append(e["monsterSubType"])
        per_team[e["killerTeamId"]] += 1
    expected_teams = [t for t, n in per_team.items() if n >= 4]
    assert [s["teamId"] for s in souls] == expected_teams[:1]
    for s in souls:
        assert s["name"] in SOUL_NAMES
        third = {
            "FIRE_DRAGON": "Infernal",
            "EARTH_DRAGON": "Mountain",
            "WATER_DRAGON": "Ocean",
            "AIR_DRAGON": "Cloud",
            "HEXTECH_DRAGON": "Hextech",
            "CHEMTECH_DRAGON": "Chemtech",
        }[log[2]]
        assert s["name"] == third


def check_end(match: dict, timeline: dict) -> None:
    info = match["info"]
    evs = events(timeline)
    end = evs[-1]
    assert end["type"] == "GAME_END"
    assert abs(end["timestamp"] - info["gameDuration"] * 1000) < 1000
    assert timeline["info"]["frames"][-1]["timestamp"] == end["timestamp"]
    assert end["realTimestamp"] == info["gameStartTimestamp"] + end["timestamp"]
    assert info["gameEndTimestamp"] >= end["realTimestamp"]
    assert sum(1 for e in evs if e["type"] == "GAME_END") == 1
    parts = info["participants"]
    if info["participants"][0]["gameEndedInEarlySurrender"]:
        assert all(p["gameEndedInEarlySurrender"] for p in parts)
        assert info["gameDuration"] < 300
        return
    winner = end["winningTeam"]
    assert {p["teamId"] for p in parts if p["win"]} == {winner}
    assert [t["teamId"] for t in info["teams"] if t["win"]] == [winner]
    if parts[0]["gameEndedInSurrender"]:
        assert all(p["gameEndedInSurrender"] for p in parts)
        return
    loser = RED if winner == BLUE else BLUE
    lost = [e for e in of_type(timeline, "BUILDING_KILL") if e["teamId"] == loser]
    nexus_turrets = [e for e in lost if e.get("towerType") == "NEXUS_TURRET"]
    assert len(nexus_turrets) == 2
    assert any(e["buildingType"] == "INHIBITOR_BUILDING" for e in lost)
    assert not [
        e
        for e in of_type(timeline, "BUILDING_KILL")
        if e["teamId"] == winner and e.get("towerType") == "NEXUS_TURRET"
    ]


ALL_CHECKS = [
    check_structure,
    check_kda,
    check_objectives,
    check_items,
    check_gold,
    check_levels,
    check_alive,
    check_timers,
    check_dragons,
    check_end,
]


def check_all(match: dict, timeline: dict) -> None:
    for check in ALL_CHECKS:
        check(match, timeline)
