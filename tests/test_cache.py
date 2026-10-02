from lolreview.cache import Cache


def test_round_trips(tmp_path):
    c = Cache(tmp_path / "c.db")
    assert c.get_match("M") is None
    c.put_match("M", {"a": 1})
    c.put_timeline("M", {"t": [1]})
    c.put_summary("M", "pu", {"k": 3})
    c.put_ddragon("versions", ["1.0"])
    assert c.get_match("M") == {"a": 1}
    assert c.get_timeline("M") == {"t": [1]}
    assert c.get_summary("M", "pu") == {"k": 3}
    assert c.get_summary("M", "other") is None
    assert c.get_ddragon("versions") == ["1.0"]


def test_persists_across_connections(tmp_path):
    Cache(tmp_path / "c.db").put_match("M", {"a": 1})
    assert Cache(tmp_path / "c.db").get_match("M") == {"a": 1}


def test_reviews_keyed_by_model_version(tmp_path):
    c = Cache(tmp_path / "c.db")
    c.put_review("M", 3, "v1", {"x": 1})
    assert c.get_review("M", 3, "v1") == {"x": 1}
    assert c.has_review("M", 3, "v1")
    assert not c.has_review("M", 3, "v2")
    assert not c.has_review("M", 4, "v1")
    assert c.get_review("M", 3, "v2") is None


def test_ranks_expire_and_unranked_is_cached(tmp_path):
    now = [1000.0]
    c = Cache(tmp_path / "c.db", clock=lambda: now[0])
    c.put_rank("na1", "pu", None)
    assert c.get_rank("na1", "pu") == {"entry": None}
    c.put_rank("na1", "pu2", {"tier": "GOLD"})
    now[0] += 3601
    assert c.get_rank("na1", "pu2") is None


def test_match_ids_and_accounts_expire(tmp_path):
    now = [0.0]
    c = Cache(tmp_path / "c.db", clock=lambda: now[0])
    c.put_match_ids("pu", 0, 10, ["a", "b"])
    c.put_account("americas", "Me", "NA1", {"puuid": "pu"})
    assert c.get_match_ids("pu", 0, 10) == ["a", "b"]
    assert c.get_match_ids("pu", 10, 10) is None
    assert c.get_account("americas", "me", "na1") == {"puuid": "pu"}
    now[0] += 400
    assert c.get_match_ids("pu", 0, 10) is None
    assert c.get_account("americas", "me", "na1") == {"puuid": "pu"}
