from lolreview import describe
from lolreview.schemas import GameEvent

NAMES = {1: "Ahri", 2: "Vi", 3: "Lux", 6: "Zed", 7: "Lee Sin", 8: "Darius", 9: "Jinx", 10: "Thresh"}


def kill(killer, victim, assists=None, team="ally", t=100.0):
    return GameEvent(t=t, team=team, kind="kill", killer=killer, victim=victim, assists=assists)


def obj(kind, team="ally", detail=None, t=200.0):
    return GameEvent(t=t, team=team, kind=kind, detail=detail)


def title(events, me=1, ordinals=None):
    return describe.moment_title(events, NAMES, me, ordinals)


def test_single_kill():
    assert title([kill(1, 6)], me=3) == "Ahri killed Zed"
    assert title([kill(1, 6, [2])], me=3) == "Ahri + Vi killed Zed"
    assert title([kill(7, 6, team="enemy")], me=3) == "Lee Sin killed Zed"


def test_enemy_kills_ally():
    assert title([kill(7, 1, [8], team="enemy")]) == "Died to Lee Sin + Darius"
    assert title([kill(7, 1, None, team="enemy")]) == "Died to Lee Sin"
    assert title([kill(7, 3, [8], team="enemy")]) == "Lee Sin + Darius killed Lux"
    assert title([kill(None, 1, team="enemy")]) == "Died"
    assert title([kill(None, 3, team="enemy")]) == "Lux died"


def test_fights():
    won = [kill(1, 6), kill(2, 7), kill(3, 8), kill(7, 1, team="enemy")]
    assert title(won) == "Won fight 3 for 1"
    lost = [
        kill(7, 1, team="enemy"),
        kill(8, 2, team="enemy"),
        kill(9, 3, team="enemy"),
        kill(1, 6),
    ]
    assert title(lost) == "Lost fight 1 for 3"
    assert title([kill(1, 6), kill(7, 1, team="enemy")]) == "Even skirmish 1 for 1"
    assert title([kill(1, 6), kill(2, 7)]) == "Won skirmish 2 for 0"
    assert title([kill(7, 1, team="enemy"), kill(8, 2, team="enemy")]) == "Lost skirmish 0 for 2"


def test_ace():
    ace = [kill(1, v, team="ally") for v in (6, 7, 8, 9, 10)]
    assert title(ace) == "Ace"
    theirs = [kill(7, v, team="enemy") for v in (1, 2, 3, 4, 5)]
    assert title(theirs) == "Enemy ace"


def test_objectives():
    assert title([obj("dragon", detail="Infernal")], ordinals=[3]) == "Took Infernal Dragon (3rd)"
    assert title([obj("dragon", "enemy", "Ocean")], ordinals=[1]) == "Enemy took Ocean Dragon (1st)"
    assert title([obj("dragon", detail="Cloud")], ordinals=[2]) == "Took Cloud Dragon (2nd)"
    assert title([obj("dragon", detail="Cloud")], ordinals=[11]) == "Took Cloud Dragon (11th)"
    assert title([obj("elder")]) == "Took Elder Dragon"
    assert title([obj("baron", "enemy")]) == "Enemy took Baron"
    assert title([obj("herald")]) == "Took Rift Herald"
    assert title([obj("atakhan", "enemy")]) == "Enemy took Atakhan"
    assert title([obj("grubs")]) == "Took a Void Grub"
    assert title([obj("grubs"), obj("grubs", t=201)]) == "Took 2 Void Grubs"


def test_buildings_and_plates():
    assert title([obj("tower", detail="mid outer")]) == "Destroyed mid outer tower"
    assert title([obj("tower", "enemy", "top inner")]) == "Lost top inner tower"
    assert title([obj("inhibitor", "enemy", "top")]) == "Lost top inhibitor"
    assert title([obj("inhibitor", detail="bot")]) == "Destroyed bot inhibitor"
    assert title([obj("tower", detail="nexus")]) == "Destroyed nexus tower"
    assert title([obj("plate", detail="top")]) == "Took top plate"
    assert title([obj("plate", "enemy", "bot"), obj("plate", "enemy", "bot")]) == (
        "Enemy took 2 bot plates"
    )
    assert title([obj("tower", detail="a b"), obj("tower", detail="c d")]) == "Destroyed 2 towers"


def test_combinations():
    fight = [kill(1, 6, t=100), kill(2, 7, t=101), kill(3, 8, t=102)]
    dragon = obj("dragon", detail="Ocean", t=130)
    assert title(fight + [dragon], ordinals=[None] * 3 + [2]) == (
        "Won fight 3 for 0, then took Ocean Dragon (2nd)"
    )
    assert title([obj("baron", "enemy", t=90)] + fight, ordinals=None) == (
        "Enemy took Baron, then won fight 3 for 0"
    )
    assert title([obj("baron", t=90), kill(1, 6, t=95)]) == "Took Baron, then Ahri killed Zed"
    many = fight + [
        obj("baron", t=120),
        obj("tower", detail="a b", t=125),
        obj("inhibitor", detail="c", t=126),
    ]
    assert title(many).endswith(", +1 more")


def test_no_middle_dots():
    events = [kill(1, 6, [2]), obj("dragon", detail="Hextech", t=130)]
    assert "·" not in title(events)


def test_where():
    assert describe.where(None, None, "blue") == "unknown"
    assert describe.where(7400, 7400, "blue") == "mid lane"
    assert describe.where(5800, 6400, "blue", {"blue_mid_outer"}) == (
        "mid lane, near your mid outer tower"
    )
    assert describe.where(5800, 6400, "red", {"blue_mid_outer"}) == (
        "mid lane, near enemy mid outer tower"
    )
    assert describe.where(5800, 6400, "red", set()) == "mid lane"
