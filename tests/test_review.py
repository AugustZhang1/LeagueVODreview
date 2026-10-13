import math
import time

import pytest
from conftest import REAL_IDS, SYNTHETIC_IDS

from lolreview import describe, review, schemas
from lolreview.config import load_config
from lolreview.constants import BLUE, RED, ROLES
from lolreview.features import GameState, PlayerState, TeamState
from lolreview.model import PlaceholderModel
from lolreview.review import (
    Remake,
    UnsupportedQueue,
    _drivers,
    _fight_damage,
    _kill_gold,
    _lane_scores,
    _moment_credit,
    _moment_values,
    _points,
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


def test_roles_fill_each_team_once(load_game):
    # Blue's jungler reports no position; then a later player also claims TOP
    for edits in ({2: ""}, {2: "", 3: "TOP"}):
        match, timeline = load_game(SYNTHETIC_IDS[0])
        for p in match["info"]["participants"]:
            if p["participantId"] in edits:
                p["teamPosition"] = p["individualPosition"] = edits[p["participantId"]]
        r = review_for(match, timeline, 4)
        for side in ("ally", "enemy"):
            assert sorted(p.role for p in r.players if p.team == side) == sorted(ROLES)
        assert all(p.lane is not None for p in r.players)


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


def review_and_values(match, timeline, pid, monkeypatch):
    """build_review's review, and the moment values it passed to _moment_values."""
    got = {}
    real = review._moment_values

    def record(*args):
        values, between = real(*args)
        got["values"] = values
        return values, between

    monkeypatch.setattr(review, "_moment_values", record)
    return review_for(match, timeline, pid), got["values"]


def test_moment_credit_shares_sum_to_value(load_game, monkeypatch):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    r, values = review_and_values(match, timeline, 4, monkeypatch)
    side = {p.participant_id: p.team for p in r.players}
    assert len(values) == len(r.moments)
    for i, (m, value) in enumerate(zip(r.moments, values, strict=True)):
        gain = "ally" if value > 0 else "enemy"
        lose = "enemy" if gain == "ally" else "ally"
        gained = sum(c.share for c in m.credit if side[c.participant_id] == gain)
        lost = sum(c.share for c in m.credit if side[c.participant_id] == lose)
        ctx = (i, value, gained, lost)
        assert gained == pytest.approx(abs(value), abs=0.002), ctx
        assert lost == pytest.approx(-abs(value), abs=0.002), ctx
        if value != 0:
            assert m.credit, ctx


def moment_of(events, t_first=590_000, t_last=600_000, p_before=0.5, delta=0.0, damage=()):
    """A Moment with the fields the value and credit functions read; times in ms."""
    return schemas.Moment(
        id="m", t_start=t_first / 1000, t_end=t_last / 1000, p_before=p_before,
        p_after=round(p_before + delta, 4), delta=delta, grade=None, title="", zone="",
        involves_me=False, events=events, damage=list(damage),
    )  # fmt: skip


def test_moment_values_wait_for_the_dead():
    # The victim is dead until 30 s after the fight ends; the next fight starts 60 s after it
    def p_at(t):
        return 0.5 + (t - 600_000) / 1_000_000

    moments = [
        moment_of([kill(6, 1, team="ally")], 590_000, 600_000, p_before=0.45, delta=0.05),
        moment_of([kill(1, 6, team="enemy")], 660_000, 700_000, p_before=0.56, delta=-0.1),
    ]
    dead = PlayerState(6, RED, "MIDDLE", dead_until_ms=630_000)
    states = {600_001: GameState(600_001, {}, {6: dead}, set(), [])}
    values, between = _moment_values(moments, states, p_at, 1.0)
    # Measured once the victim is back (630 s), not the instant the fight ends (600 s)
    assert values == pytest.approx([p_at(630_000) - 0.45, -0.1], abs=1e-4)
    # Between: what moved from the first fight's end to the next fight's start, then to the result
    assert between == pytest.approx(
        (p_at(659_999) - 0.45 - values[0]) + (1.0 - 0.56 - values[1]), abs=1e-4
    )


def test_moment_credit_signs_follow_the_value():
    team_of = {pid: BLUE if pid <= 5 else RED for pid in range(1, 11)}  # I'm on blue
    # Blue kills red 6: blue gains, so my side gets +0.2 and red gets -0.2
    up = _moment_credit(moment_of([kill(6, 1, team="ally")]), 0.2, team_of, BLUE)
    assert {c.participant_id: c.share for c in up} == pytest.approx({1: 0.2, 6: -0.2}, abs=1e-4)
    # Red kills blue 1 and red gains (-0.1): the signs flip
    down = _moment_credit(moment_of([kill(1, 6, team="enemy")]), -0.1, team_of, BLUE)
    assert {c.participant_id: c.share for c in down} == pytest.approx({6: 0.1, 1: -0.1}, abs=1e-4)


def test_moment_credit_gaining_death_has_no_taken_weight():
    team_of = {pid: BLUE if pid <= 5 else RED for pid in range(1, 11)}
    # Blue gains (+0.2): blue 1 kills red 7, and red 6 kills blue 2 (who had taken 200 damage)
    damage = [
        schemas.FightDamage(participant_id=1, dealt=300, taken=0),
        schemas.FightDamage(participant_id=2, dealt=0, taken=200),
        schemas.FightDamage(participant_id=3, dealt=100, taken=100),
    ]
    moment = moment_of([kill(7, 1, team="ally"), kill(2, 6, team="enemy")], damage=damage)
    credit = _moment_credit(moment, 0.2, team_of, BLUE)
    # Dealt 300/400 and taken 100/100 (2's taken is dropped: they died), part = {1}:
    # 1 = 0.5*0.75 + 0.25, 3 = 0.5*0.25 + 0.25, red 7 loses its one death
    shares = {c.participant_id: c.share for c in credit}
    assert shares == pytest.approx({1: 0.125, 3: 0.075, 7: -0.2}, abs=1e-4)


def test_moment_credit_losing_side_one_share_per_death():
    team_of = {pid: BLUE if pid <= 5 else RED for pid in range(1, 11)}
    # Blue gains (+0.2); red 7 dies twice and red 8 once: 2/3 and 1/3 of the loss
    moment = moment_of([kill(7, 1, team="ally"), kill(7, 2, team="ally"), kill(8, 3, team="ally")])
    credit = _moment_credit(moment, 0.2, team_of, BLUE)
    losing = {c.participant_id: c.share for c in credit if c.participant_id > 5}
    assert losing == pytest.approx({7: -0.2 * 2 / 3, 8: -0.2 / 3}, abs=1e-4)


def test_impact_and_between_fights_sum(load_game):
    for mid in GOOD:
        match, timeline = load_game(mid)
        for pid in (1, 6):  # one from each side
            r = review_for(match, timeline, pid)
            my_impact = sum(p.impact for p in r.players if p.team == "ally")
            result = 1.0 if r.match.result == "win" else 0.0
            expected = result - r.moments[0].p_before
            assert my_impact + r.between_fights == pytest.approx(expected, abs=0.01)


def test_perspective_invariance(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    blue = review_for(match, timeline, 4)
    red = review_for(match, timeline, 9)
    blue_by_id = {p.participant_id: p for p in blue.players}
    red_by_id = {p.participant_id: p for p in red.players}
    for pid in blue_by_id:
        bp = blue_by_id[pid]
        rp = red_by_id[pid]
        assert bp.score == rp.score
        assert bp.impact == pytest.approx(rp.impact, abs=1e-4)
        if bp.lane is not None:
            assert bp.lane == pytest.approx(rp.lane, abs=1e-4)
        else:
            assert rp.lane is None
        assert bp.badge == rp.badge


def lane_inputs():
    """One player per role on each side at 14:00 (blue is me), with similar stats."""
    pstates = {}
    players = []
    for i, role in enumerate(ROLES, start=1):
        pstates[i] = PlayerState(i, BLUE, role, gold=4000 + i * 100, cs=100 + i * 10, level=9)
        pstates[i + 5] = PlayerState(i + 5, RED, role, gold=3900 + i * 100, cs=95 + i * 10, level=9)
        for pid, side in ((i, "ally"), (i + 5, "enemy")):
            players.append(
                schemas.Player(
                    participant_id=pid, riot_id=f"P{pid}", champion="Ch", champion_name="Ch",
                    role=role, team=side, is_me=(pid == 1),
                )
            )  # fmt: skip
    return pstates, players


def lane_state(pstates, t=840_000):
    """The state at t, with the team sums states_at fills in (the lane's feature row reads them)."""
    teams = {}
    for tid in (BLUE, RED):
        mine = [p for p in pstates.values() if p.team == tid]
        teams[tid] = TeamState(
            gold=sum(p.gold for p in mine),
            level_sum=sum(p.level for p in mine),
            cs_sum=sum(p.cs for p in mine),
        )
    return GameState(t, teams, pstates, set(), [])


def test_lane_zero_sum_and_support_ignores_cs(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    r = review_for(match, timeline, 4)
    by_role: dict[str, list[schemas.Player]] = {}
    for p in r.players:
        by_role.setdefault(p.role, []).append(p)
    for pair in by_role.values():
        if len(pair) == 2 and pair[0].lane is not None and pair[1].lane is not None:
            assert pair[0].lane == pytest.approx(-pair[1].lane, abs=1e-4)
            assert pair[0].lane_gold == -pair[1].lane_gold
            assert pair[0].lane_cs == -pair[1].lane_cs
            assert pair[0].lane_level == -pair[1].lane_level

    # Unit-test _lane_scores with synthetic state: altering support CS doesn't change lane
    cfg = load_config()
    t = 840_000
    pstates, test_players = lane_inputs()
    scores1 = _lane_scores({t: lane_state(pstates)}, test_players, "GOLD", MODEL, cfg, 1_800_000)
    support_blue_id = 5  # UTILITY
    support_red_id = 10
    assert scores1[support_blue_id]["lane"] == pytest.approx(
        -scores1[support_red_id]["lane"], abs=1e-4
    )

    # Change only support CS. The base row's cs_diff moves too, so the lane shifts slightly.
    pstates2 = dict(pstates)
    pstates2[support_blue_id] = PlayerState(
        support_blue_id, BLUE, "UTILITY", gold=4500, cs=200, level=9
    )
    pstates2[support_red_id] = PlayerState(
        support_red_id, RED, "UTILITY", gold=4400, cs=10, level=9
    )
    scores2 = _lane_scores({t: lane_state(pstates2)}, test_players, "GOLD", MODEL, cfg, 1_800_000)
    assert scores2[support_blue_id]["lane_cs"] != scores1[support_blue_id]["lane_cs"]
    assert scores2[support_blue_id]["lane"] == pytest.approx(
        scores1[support_blue_id]["lane"], abs=1e-3
    )


def test_lane_sign_follows_the_gold_lead():
    pstates, players = lane_inputs()
    pstates[2] = PlayerState(2, BLUE, "JUNGLE", gold=4700, cs=120, level=9)  # 600 gold up
    scores = _lane_scores(
        {840_000: lane_state(pstates)}, players, "GOLD", MODEL, load_config(), 1_800_000
    )
    assert scores[2]["lane"] > 0 and scores[7]["lane"] < 0


def test_no_lane_unless_the_game_reached_14_minutes():
    pstates, players = lane_inputs()
    for end_ms in (600_000, 840_000):
        scores = _lane_scores(
            {840_000: lane_state(pstates)}, players, "GOLD", MODEL, load_config(), end_ms
        )
        assert len(scores) == 10
        assert all(
            v == {"lane": None, "lane_gold": None, "lane_cs": None, "lane_level": None}
            for v in scores.values()
        )


def test_points_share_the_places_of_a_tie():
    # Each tied 2 has one value below and one equal: 10 * (1 + (2 - 1) / 2) / 3 = 5
    assert _points([1, 2, 2, 3]) == [0, 5, 5, 10]


def test_scores_range_and_badges(load_game):
    for mid in GOOD:
        match, timeline = load_game(mid)
        r = review_for(match, timeline, 1)
        for p in r.players:
            assert p.score is not None and 0.0 <= p.score <= 10.0
            assert p.score_parts is not None
            for val in (
                p.score_parts.gold_min,
                p.score_parts.vs_lane,
                p.score_parts.kp,
                p.score_parts.impact,
                p.score_parts.fights,
            ):
                assert 0.0 <= val <= 10.0
        winners = [
            p
            for p in r.players
            if (p.team == "ally" and r.match.result == "win")
            or (p.team == "enemy" and r.match.result == "loss")
        ]
        losers = [p for p in r.players if p not in winners]
        assert [p.badge for p in winners].count("mvp") == 1
        assert [p.badge for p in winners].count("ace") == 0
        assert [p.badge for p in losers].count("mvp") == 0
        assert [p.badge for p in losers].count("ace") == 1
        mvp = min(winners, key=lambda p: (-p.score, p.participant_id))
        ace = min(losers, key=lambda p: (-p.score, p.participant_id))
        assert mvp.badge == "mvp", (mid, mvp.participant_id)
        assert ace.badge == "ace", (mid, ace.participant_id)


def test_death_on_gaining_side_non_negative_share(load_game):
    match, timeline = load_game(SYNTHETIC_IDS[0])
    r = review_for(match, timeline, 4)
    # Moment 3 has ally team kill 2 enemies and take Dragon while Ahri (pid 4) dies
    m3 = r.moments[2]
    assert any(e.victim == 4 for e in m3.events if e.kind == "kill")
    ahri_credit = next((c for c in m3.credit if c.participant_id == 4), None)
    assert ahri_credit is not None
    assert ahri_credit.share >= 0
