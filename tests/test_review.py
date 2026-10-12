import math
import time

import pytest
from conftest import REAL_IDS, SYNTHETIC_IDS

from lolreview import describe, schemas
from lolreview.config import load_config
from lolreview.constants import BLUE, RED
from lolreview.features import GameState, PlayerState, TeamState
from lolreview.model import PlaceholderModel
from lolreview.review import (
    Remake,
    UnsupportedQueue,
    _drivers,
    _fight_damage,
    _kill_gold,
    _tip,
    build_review,
)

GOOD = SYNTHETIC_IDS[:3] + REAL_IDS
MODEL = PlaceholderModel()
CFG = load_config()["review"]


def champions(match):
    return {
        p["championId"]: (p["championName"], p["championName"].title())
        for p in match["info"]["participants"]
    }


def review_for(match, timeline, pid, **kw):
    return build_review(match, timeline, pid, "GOLD", MODEL, champions(match), "26.19.1", **kw)


def all_reviews(load_game):
    for mid in GOOD:
        match, timeline = load_game(mid)
        for p in match["info"]["participants"]:
            yield mid, match, timeline, p["participantId"]


def expected_event_count(timeline):
    n = 0
    for f in timeline["info"]["frames"]:
        for e in f["events"]:
            if e["type"] in ("CHAMPION_KILL", "BUILDING_KILL", "TURRET_PLATE_DESTROYED"):
                n += 1
            elif e["type"] == "ELITE_MONSTER_KILL" and e.get("killerTeamId") != 300:
                n += e["monsterType"] in (
                    "DRAGON", "HORDE", "RIFTHERALD", "BARON_NASHOR", "ATAKHAN"
                )  # fmt: skip
    return n


def test_rejects_unsupported(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    match["info"]["queueId"] = 450
    with pytest.raises(UnsupportedQueue):
        review_for(match, timeline, 1)
    assert issubclass(UnsupportedQueue, ValueError)
    match, timeline = load_game(SYNTHETIC_IDS[3])
    with pytest.raises(Remake):
        review_for(match, timeline, 1)


def test_every_game_and_side(load_game):
    for mid, match, timeline, pid in all_reviews(load_game):
        r = review_for(match, timeline, pid)
        r = schemas.Review.model_validate(r.model_dump(by_alias=True))
        me = next(p for p in match["info"]["participants"] if p["participantId"] == pid)
        won = me["win"]

        ts = [c.t for c in r.curve]
        assert ts == sorted(ts) and len(set(ts)) == len(ts)
        assert r.curve[-1].p == (1.0 if won else 0.0)
        assert all(0 <= c.p <= 1 for c in r.curve)
        assert r.match.result == ("win" if won else "loss")
        assert r.match.my_side == ("blue" if me["teamId"] == 100 else "red")

        events = [e for m in r.moments for e in m.events]
        assert len(events) == expected_event_count(timeline), mid
        for m in r.moments:
            assert m.events and m.t_start == m.events[0].t and m.t_end == m.events[-1].t
            assert m.delta == pytest.approx(m.p_after - m.p_before, abs=2e-4)
            assert m.zone and m.title and "·" not in m.title
            if m.delta >= CFG["great"]:
                assert m.grade == "!!"
            elif m.delta >= CFG["good"]:
                assert m.grade == "!"
            elif m.delta <= CFG["blunder"]:
                assert m.grade == "??"
            elif m.delta <= CFG["mistake"]:
                assert m.grade == "?"
            else:
                assert m.grade is None
        for a, b in zip(r.moments, r.moments[1:], strict=False):
            assert b.t_start - a.t_end > CFG["group_window_s"]

        assert len(r.snapshots) == math.ceil(match["info"]["gameDuration"] / 15) + 1
        assert [s.t for s in r.snapshots] == [15.0 * i for i in range(len(r.snapshots))]
        assert len(r.players) == 10
        assert [p.team for p in r.players] == ["ally"] * 5 + ["enemy"] * 5
        assert [p.participant_id for p in r.players][
            r.players.index(next(p for p in r.players if p.is_me))
        ] == pid
        assert sum(p.is_me for p in r.players) == 1

        last = {p.participant_id: p for p in r.snapshots[-1].players}
        for p in match["info"]["participants"]:
            s = last[p["participantId"]]
            assert (s.k, s.d, s.a) == (p["kills"], p["deaths"], p["assists"]), (
                mid,
                p["participantId"],
            )
            held = sorted(p[f"item{i}"] for i in range(6) if p[f"item{i}"])
            assert sorted(i for i in s.items if i) == held, (mid, p["participantId"])
            assert s.trinket == (p["item6"] or None)
            if p["teamPosition"] == "BOTTOM" and p.get("roleBoundItem", 0) > 1300:  # boots
                assert s.quest_item == p["roleBoundItem"], (mid, p["participantId"])

        counts = {g: 0 for g in ("!!", "!", "?", "??")}
        for m in r.moments:
            if m.grade:
                counts[m.grade] += 1
        assert r.summary.team.model_dump(by_alias=True) == counts
        assert r.summary.biggest_id == max(r.moments, key=lambda m: abs(m.delta)).id


def test_red_side_flip(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    blue = review_for(match, timeline, 4)
    red = review_for(match, timeline, 9)
    assert blue.match.my_side == "blue" and red.match.my_side == "red"
    for a, b in zip(blue.curve[:-1], red.curve[:-1], strict=True):
        assert a.t == b.t and a.p + b.p == pytest.approx(1, abs=2e-4)
    assert [m.t_start for m in blue.moments] == [m.t_start for m in red.moments]
    for a, b in zip(blue.moments, red.moments, strict=True):
        assert a.delta == pytest.approx(-b.delta, abs=2e-4)
        assert [e.team for e in a.events] == [
            "enemy" if e.team == "ally" else "ally" for e in b.events
        ]
    sa, sb = blue.snapshots[-1], red.snapshots[-1]
    assert sa.teams.ally == sb.teams.enemy and sa.teams.enemy == sb.teams.ally
    assert {b.id: b.team for b in blue.buildings}["blue_nexus_1"] == "ally"
    assert {b.id: b.team for b in red.buildings}["blue_nexus_1"] == "enemy"
    assert len(blue.buildings) == 28
    assert red.match.result == "loss" and blue.match.result == "win"
    assert {p.participant_id for p in blue.players if p.team == "ally"} == {1, 2, 3, 4, 5}
    assert {p.participant_id for p in red.players if p.team == "ally"} == {6, 7, 8, 9, 10}


def test_match_block(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[1])
    r = review_for(match, timeline, 9, tier_note="Median of the other players")
    m = r.match
    assert m.match_id == "NA1_9000000002" and m.platform == "NA1" and m.patch == "26.19"
    assert m.surrender is True and m.tier_used == "GOLD"
    assert m.tier_note == "Median of the other players"
    assert (m.model.kind, m.model.version, m.patch_in_training) == ("stub", "stub", True)
    assert m.ddragon_version == "26.19.1" and m.started_at.endswith("+00:00")
    me = next(p for p in r.players if p.is_me)
    assert me.riot_id == "Me#NA1" and me.role == "BOTTOM" and me.team == "ally"


def test_champion_mapping_and_fallback(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[2])
    r = review_for(match, timeline, 1)
    wukong = [p for p in match["info"]["participants"] if p["championName"] == "MonkeyKing"]
    champs = champions(match)
    champs[wukong[0]["championId"]] = ("MonkeyKing", "Wukong")
    r = build_review(match, timeline, 1, "GOLD", MODEL, champs, "26.19.1")
    p = next(p for p in r.players if p.participant_id == wukong[0]["participantId"])
    assert (p.champion, p.champion_name) == ("MonkeyKing", "Wukong")
    r = build_review(match, timeline, 1, "GOLD", MODEL, {}, "26.19.1")
    p = next(p for p in r.players if p.participant_id == wukong[0]["participantId"])
    assert (p.champion, p.champion_name) == ("MonkeyKing", "MonkeyKing")


def test_trained_model_patch_flag(load_game):
    class Trained(PlaceholderModel):
        kind = "trained"
        version = "abcd1234"
        patches = ["26.18"]

    match, timeline = load_game(SYNTHETIC_IDS[0])
    r = build_review(match, timeline, 4, "GOLD", Trained(), champions(match), "26.19.1")
    assert r.match.patch_in_training is False and r.match.model.kind == "trained"
    Trained.patches = ["26.19", "26.18"]
    r = build_review(match, timeline, 4, "GOLD", Trained(), champions(match), "26.19.1")
    assert r.match.patch_in_training is True


def test_moment_content(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    r = review_for(match, timeline, 4)
    titles = [m.title for m in r.moments]
    assert any("Dragon (1st)" in t for t in titles)
    assert any(t == "Took Baron" for t in titles)
    mine = [m for m in r.moments if m.involves_me]
    for m in mine:
        assert any(e.killer == 4 or e.victim == 4 or 4 in (e.assists or []) for e in m.events)
    assert r.summary.me.model_dump(by_alias=True) == {
        g: sum(1 for m in mine if m.grade == g) for g in ("!!", "!", "?", "??")
    }
    kinds = {e.kind for m in r.moments for e in m.events}
    assert {"kill", "dragon", "baron", "tower", "inhibitor", "plate", "grubs"} <= kinds


def test_third_game_kinds(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[2])
    r = review_for(match, timeline, 1)
    kinds = {e.kind for m in r.moments for e in m.events}
    assert {"elder", "atakhan"} <= kinds
    last = r.snapshots[-1]
    assert last.teams.ally.towers + last.teams.enemy.towers > 0


def test_snapshot_fields(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    r = review_for(match, timeline, 4)
    assert r.snapshots[0].players[0].respawn_in_s == 0
    assert any(p.respawn_in_s > 0 for s in r.snapshots for p in s.players)
    assert any(s.recent_kills for s in r.snapshots)
    assert all(k.age_s < CFG["recent_kill_s"] for s in r.snapshots for k in s.recent_kills)
    assert any(s.teams.ally.buff or s.teams.enemy.buff for s in r.snapshots)
    assert r.snapshots[-1].buildings_down == sorted(r.snapshots[-1].buildings_down)


def test_objectives_at_two_minutes(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    r = review_for(match, timeline, 4)
    snap = r.snapshots[8]
    assert snap.t == 120
    # first dragon at 5:00, first pit monster (grubs) at 8:00
    assert snap.objectives.dragon_in_s == 180
    assert snap.objectives.dragon_kind == "dragon"
    assert snap.objectives.baron_pit_in_s == 360
    assert snap.objectives.baron_pit_kind == "grubs"
    assert all(s.objectives is not None for s in r.snapshots)


def test_objectives_elder_once_a_soul_is_taken(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[2])
    r = review_for(match, timeline, 1)
    soul_at = next(i for i, s in enumerate(r.snapshots) if s.teams.ally.soul or s.teams.enemy.soul)
    kinds = [s.objectives.dragon_kind for s in r.snapshots]
    assert kinds[:soul_at] == ["dragon"] * soul_at
    assert kinds[soul_at:] == ["elder"] * (len(kinds) - soul_at)


def test_fast(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[2])
    review_for(match, timeline, 1)
    start = time.perf_counter()
    review_for(match, timeline, 1)
    assert time.perf_counter() - start < 1.0


TEAMS = {1: 100, 2: 100, 6: 200, 7: 200}


def hit(pid, phys=0, magic=0, true=0, kind="OTHER"):
    return {
        "participantId": pid,
        "type": kind,
        "physicalDamage": phys,
        "magicDamage": magic,
        "trueDamage": true,
    }


def test_fight_damage_max_per_pair_and_champions_only():
    k1 = {
        "victimId": 6,
        "victimTeamfightDamageReceived": [
            hit(1, 100, 50, 10),
            hit(0, 999, kind="TOWER"),
            hit(2, 5),
        ],
        "victimTeamfightDamageDealt": [hit(1, 30), hit(7, 500)],  # 7 is a teammate of 6
    }
    k2 = {
        "victimId": 7,
        "victimTeamfightDamageReceived": [hit(1, 40), hit(6, 77)],  # 6 is a teammate of 7
        "victimTeamfightDamageDealt": [hit(2, 20), hit(0, 8, kind="MINION")],
    }
    got = {d.participant_id: (d.dealt, d.taken) for d in _fight_damage([k1, k2], TEAMS)}
    # pairs: (1,6)=160 (max of 160 and 30), (2,6)=5, (1,7)=40, (7,2)=20, (6,1)=30
    assert got == {1: (200, 30), 2: (5, 20), 6: (30, 165), 7: (20, 40)}
    assert [d.participant_id for d in _fight_damage([k1, k2], TEAMS)][0] == 1


def test_fight_damage_falls_back_to_plain_lists():
    k = {
        "victimId": 6,
        "victimTeamfightDamageReceived": [],
        "victimDamageReceived": [hit(1, 10)],
        "victimDamageDealt": [hit(2, 3)],
    }
    got = {d.participant_id: (d.dealt, d.taken) for d in _fight_damage([k], TEAMS)}
    assert got == {1: (10, 0), 6: (3, 10), 2: (0, 3)}
    assert _fight_damage([{"victimId": 6}], TEAMS) == []


def test_kill_gold_sign():
    ally_kill = {"victimId": 6, "killerId": 1, "bounty": 300, "shutdownBounty": 50}
    enemy_kill = {"victimId": 1, "killerId": 7, "bounty": 200}
    executed = {"victimId": 2, "killerId": 0, "bounty": 100}  # killer isn't a participant
    assert _kill_gold([ally_kill], TEAMS, 100) == 350
    assert _kill_gold([ally_kill], TEAMS, 200) == -350
    assert _kill_gold([enemy_kill], TEAMS, 100) == -200
    assert _kill_gold([ally_kill, enemy_kill, executed], TEAMS, 100) == 350 - 200 - 100


def test_moment_damage_on_real_game(load_game):
    match, timeline = load_game(REAL_IDS[0])
    r = review_for(match, timeline, 1)
    assert any(m.damage for m in r.moments)
    assert any(m.kill_gold for m in r.moments)


def test_drivers_sign_cap_and_skips():
    before = {"tier": 3, "minute": 10.0, "gold_diff": 0, "baron_active": 0, "kill_diff": 0,
              "cs_diff": 0, "tower_diff": 0}  # fmt: skip
    after = {**before, "tier": 4, "minute": 11.0, "gold_diff": 0.3, "baron_active": -0.9,
             "kill_diff": 0.05, "cs_diff": 0.004, "tower_diff": 0.16}  # fmt: skip
    blue = _drivers(before, after, "blue")
    assert [(d.label, d.change) for d in blue] == [
        ("Baron buff", -0.9), ("Gold lead", 0.3), ("Towers", 0.16),
    ]  # fmt: skip
    red = _drivers(before, after, "red")
    assert [(d.label, d.change) for d in red] == [
        ("Baron buff", 0.9), ("Gold lead", -0.3), ("Towers", -0.16),
    ]  # fmt: skip


def test_driver_labels_follow_my_side():
    assert describe.feature_label("blue_dragons", "blue") == "Your dragons"
    assert describe.feature_label("blue_dragons", "red") == "Enemy dragons"
    assert describe.feature_label("red_dead_s", "red") == "Your team's death timers"
    assert describe.feature_label("gold_diff", "red") == "Gold lead"
    before, after = {"soul_type": 0.0, "gold_diff": 0.0}, {"soul_type": 0.5, "gold_diff": 0.2}
    assert [d.label for d in _drivers(before, after, "blue")] == ["Gold lead"]


def test_drivers_on_moments(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    blue = review_for(match, timeline, 4)
    red = review_for(match, timeline, 9)
    sided = {"Your dragons": "Enemy dragons", "Your team's death timers": "Enemy death timers"}
    sided |= {v: k for k, v in sided.items()}
    labels = set(describe.FEATURE_LABELS.values()) | set(sided)
    assert any(m.drivers for m in blue.moments)
    for m in blue.moments:
        assert len(m.drivers) <= 3
        sizes = [abs(d.change) for d in m.drivers]
        assert sizes == sorted(sizes, reverse=True)
        assert all(s >= 0.01 and d.label in labels for s, d in zip(sizes, m.drivers, strict=True))
        assert describe.FEATURE_LABELS["tier"] not in {d.label for d in m.drivers}
        assert describe.FEATURE_LABELS["minute"] not in {d.label for d in m.drivers}
    for a, b in zip(blue.moments, red.moments, strict=True):
        assert [sided.get(d.label, d.label) for d in a.drivers] == [d.label for d in b.drivers]
        assert [d.change for d in a.drivers] == [-d.change for d in b.drivers]


TIP_NAMES = {1: "Ahri", 2: "Garen", 3: "Lux", 6: "Zed", 7: "Lee Sin", 8: "Jinx"}


def tip_state(levels=None, dead=(), enemy_buff=None):
    """Me (1), Garen (2) and Lux (3) on blue; Zed (6), Lee Sin (7) and Jinx (8) on red, at 10:00."""
    t = 600_000
    levels = levels or {}
    players = {
        pid: PlayerState(pid, BLUE if pid < 6 else RED, "", level=levels.get(pid, 9),
                         dead_until_ms=t + 30_000 if pid in dead else 0)
        for pid in TIP_NAMES
    }  # fmt: skip
    teams = {BLUE: TeamState(), RED: TeamState(buff=enemy_buff)}
    return GameState(t, teams, players, set(), [])


def kill(victim, killer, *assists, team="enemy"):
    return schemas.GameEvent(t=600, team=team, kind="kill", killer=killer, victim=victim,
                             assists=list(assists) or None)  # fmt: skip


def tip(evs, state):
    return _tip(evs, state, 1, BLUE, TIP_NAMES)


def test_tip_rules_in_order():
    baron = ("baron", 600_000 + 95_000)
    assert tip([kill(1, 6)], tip_state(enemy_buff=baron)) == (
        "Enemy had Baron buff for 95 more seconds: "
        "wait it out under your towers instead of fighting."
    )
    assert tip([kill(1, 6, 7)], tip_state()) == (
        "Caught alone by Zed + Lee Sin: stay near your team, or ward ahead before walking in."
    )
    assert tip([kill(2, 6, 7, 8), kill(1, 6)], tip_state()) == (
        "Fought 2v3: back off until your team can join."
    )
    assert tip([kill(1, 6), kill(6, 1, team="ally")], tip_state(dead={2})) == (
        "Your team had 2 alive to their 3: wait for respawns before fighting."
    )
    assert tip([kill(1, 6)], tip_state(levels={6: 11})) == (
        "Zed was 2 levels ahead: avoid fighting them until you catch up."
    )
    took = schemas.GameEvent(t=610, team="enemy", kind="baron")
    assert tip([kill(2, 6), kill(6, 1, team="ally"), took], tip_state()) == (
        "Enemy took Baron: be at the pit with vision before it spawns, "
        "or trade for a tower across the map."
    )


def test_no_tip_when_no_rule_fits():
    assert tip([kill(1, 6)], tip_state(levels={6: 10})) is None  # an even 1v1
    assert tip([kill(6, 1, team="ally")], tip_state()) is None


def test_tips_only_on_my_mistakes(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[1])
    r = review_for(match, timeline, 1)
    assert any(m.tip for m in r.moments)
    for m in r.moments:
        if m.tip:
            assert m.involves_me and m.grade in ("?", "??")
