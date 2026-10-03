from conftest import REAL_IDS, SYNTHETIC_IDS
from test_review import champions

from lolreview import schemas
from lolreview.config import load_config
from lolreview.constants import BLUE, RED
from lolreview.features import GameState, PlayerState, TeamState, feature_row
from lolreview.model import PlaceholderModel
from lolreview.review import build_review
from lolreview.windows import _credit, find_windows

MODEL = PlaceholderModel()
CFG = load_config()
NAMES = {1: "Ahri", 2: "Lee Sin", 3: "Zed", 4: "Jinx", 5: "Garen", 6: "Teemo"}
T = 600_000
END = 1_800_000


def make_state(dead=None, t=T, dragon_in=0, baron_in=10**9, down=(), grubs=3, heralds=1):
    """Blue (my team): Ahri 1, Garen 5. Red: Lee Sin 2 jungle, Zed 3 mid, Jinx 4 bot, Teemo 6 top.
    `dead` is {participant: seconds left}."""
    dead = dead or {}
    roles = {1: (BLUE, "MIDDLE"), 5: (BLUE, "TOP"), 2: (RED, "JUNGLE"), 3: (RED, "MIDDLE"),
             4: (RED, "BOTTOM"), 6: (RED, "TOP")}  # fmt: skip
    players = {
        pid: PlayerState(pid, team, role, dead_until_ms=t + int(dead.get(pid, 0) * 1000))
        for pid, (team, role) in roles.items()
    }
    teams = {BLUE: TeamState(grubs=grubs, heralds=heralds), RED: TeamState()}
    return GameState(
        t_ms=t, teams=teams, players=players, buildings_down=set(down), recent_kills=[],
        baron_pit_in_ms=baron_in, dragon_pit_in_ms=dragon_in,
    )  # fmt: skip


def run(states, events=(), cfg=CFG, my_team=BLUE, end=END):
    grid = sorted(states)
    return find_windows(states, grid, end, my_team, "GOLD", MODEL, list(events), NAMES, cfg)


def loose(**kw):
    cfg = load_config()
    cfg["windows"].update(min_value=-1, **kw)
    return cfg


def ally_event(kind, t_s, detail=None):
    return (int(t_s * 1000), schemas.GameEvent(t=t_s, team="ally", kind=kind, detail=detail), None)


def test_jungler_dead_long_enough_opens_window():
    w = run({T: make_state({2: 25})}, cfg=loose())
    assert len(w) == 1
    assert w[0].title == "Enemy Lee Sin dead, Dragon up"
    assert w[0].reason == "Lee Sin dead for 0:25"
    assert (w[0].t_start, w[0].t_end) == (600, 625)


def test_jungler_dead_too_briefly_does_not():
    assert run({T: make_state({2: 15})}, cfg=loose()) == []


def test_two_dead_opens_window_with_longest_first():
    w = run({T: make_state({3: 22, 6: 31})}, cfg=loose())
    assert w[0].title.startswith("2 enemies dead, ")
    assert w[0].reason == "Teemo dead for 0:31, Zed for 0:22"
    assert w[0].t_end == 622  # the second-longest dead player's respawn


def test_two_dead_too_briefly_does_not():
    # the second one is back in 12 s: too short to take anything
    assert run({T: make_state({3: 12, 6: 31})}, cfg=loose()) == []


def test_nothing_takeable_no_window():
    st = make_state({2: 25}, dragon_in=60_000, baron_in=60_000)
    assert run({T: st}, cfg=loose()) == []


def test_baron_pit_monsters():
    assert (
        run({T: make_state({2: 25}, dragon_in=99**6, baron_in=0, grubs=0)}, cfg=loose())[0]
        .options[0]
        .what
        == "Void Grubs"
    )
    st = make_state({2: 25}, dragon_in=99**6, baron_in=0, heralds=0)
    assert run({T: st}, cfg=loose())[0].options[0].what == "Rift Herald"
    st = make_state({2: 25}, dragon_in=99**6, baron_in=0)
    assert run({T: st}, cfg=loose())[0].options[0].what == "Baron"


def test_elder_when_a_soul_is_taken():
    st = make_state({2: 25})
    st.teams[RED].soul = "HEXTECH"
    assert [o.what for o in run({T: st}, cfg=loose())[0].options] == ["Elder Dragon"]


def test_tower_in_dead_laners_lane():
    st = make_state({2: 25, 3: 25}, dragon_in=99**6, down={"red_mid_outer"})
    w = run({T: st}, cfg=loose())
    assert [o.what for o in w[0].options] == ["mid inner tower"]
    assert w[0].title == "2 enemies dead, mid inner tower open"
    st = make_state(
        {2: 25, 3: 25}, dragon_in=99**6, down={f"red_mid_{p}" for p in ("outer", "inner", "base")}
    )
    assert run({T: st}, cfg=loose())[0].options[0].what == "mid inhibitor"


def test_credit_raises_my_chance():
    st = make_state(grubs=0)
    row = feature_row(st, "GOLD")
    for my_team in (BLUE, RED):
        base = MODEL.predict([row])[0]
        for what in ("Dragon", "Elder Dragon", "Baron", "Rift Herald", "Void Grubs",
                     "bot outer tower", "bot inhibitor"):  # fmt: skip
            after = MODEL.predict([_credit(row, what, my_team, st, CFG["timers"])])[0]
            assert (after > base) == (my_team == BLUE), what


def test_used_by_ally_objective_inside_or_just_after():
    st = {T: make_state({2: 25})}
    assert run(st, [ally_event("dragon", 610)], loose())[0].taken == ["Dragon"]
    w = run(st, [ally_event("tower", 634, "bot outer")], loose())[0]
    assert w.used and w.taken == ["bot outer tower"]
    assert not run(st, [ally_event("dragon", 636)], loose())[0].used
    assert not run(st, [ally_event("kill", 610)], loose())[0].used
    enemy = (610_000, schemas.GameEvent(t=610, team="enemy", kind="dragon"), 1)
    assert not run(st, [enemy], loose())[0].used


def test_consecutive_times_merge_and_later_gap_splits():
    states = {
        T: make_state({2: 40}),
        T + 15_000: make_state({2: 25}, t=T + 15_000),
        T + 30_000: make_state(t=T + 30_000),
        T + 45_000: make_state({2: 25}, t=T + 45_000),
    }
    w = run(states, cfg=loose())
    assert [x.id for x in w] == ["w1", "w2"]
    assert (w[0].t_start, w[0].t_end) == (600, 640)
    assert w[1].t_start == 645


def test_min_value_drops_windows_and_end_margin():
    cfg = load_config()
    cfg["windows"]["min_value"] = 0.99
    assert run({T: make_state({2: 25})}, cfg=cfg) == []
    assert run({T: make_state({2: 25})}, cfg=loose(), end=T + 4000) == []
    assert run({T: make_state({2: 25})}, cfg=loose(), end=T + 10_000)[0].t_end == 610


def test_other_team_as_mine():
    st = make_state({1: 25, 5: 25})  # blue's Ahri and Garen dead; red is "mine"
    w = run({T: st}, cfg=loose(), my_team=RED)
    assert w[0].title.startswith("2 enemies dead, ")
    assert w[0].reason == "Ahri dead for 0:25, Garen for 0:25"


def test_build_review_windows(load_game):
    for mid in SYNTHETIC_IDS[:3] + REAL_IDS:
        match, timeline = load_game(mid)
        end = match["info"]["gameDuration"]
        for p in match["info"]["participants"][::5]:
            r = build_review(
                match, timeline, p["participantId"], "GOLD", MODEL, champions(match), "26.19.1"
            )
            ids = [w.id for w in r.windows]
            assert ids == [f"w{i}" for i in range(1, len(ids) + 1)]
            starts = [w.t_start for w in r.windows]
            assert starts == sorted(starts)
            for w in r.windows:
                assert 0 <= w.t_start < w.t_end <= end + 60
                assert w.options and w.value == w.options[0].value >= CFG["windows"]["min_value"]
                vals = [o.value for o in w.options]
                assert vals == sorted(vals, reverse=True)
