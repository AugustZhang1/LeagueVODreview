import pytest

from lolreview.state import ERRORS_KEPT, State, state_path


@pytest.fixture
def st(tmp_path):
    s = State(state_path(tmp_path, "na1"))
    yield s
    s.close()


def test_path_and_wal(tmp_path, st):
    assert state_path(tmp_path, "na1").name == "state-na1.sqlite"
    assert st.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_meta_roundtrip(st):
    assert st.meta_get("x") is None
    st.meta_set("x", 3)
    st.meta_set("x", 4)
    assert st.meta_int("x") == 4
    st.meta_set("added:1:GOLD", 5)
    assert st.meta_prefix("added:1:") == {"GOLD": "5"}


def test_add_matches_dedupes_and_limits(st):
    assert st.add_matches(["a", "b", "c"], "GOLD", 1.0) == 3
    assert st.add_matches(["b", "c", "d", "e", "f"], "GOLD", 2.0, limit=2) == 2
    assert st.match_counts() == {"pending": 5}
    assert [m for m, _ in st.pending(10)] == ["a", "b", "c", "d", "e"]
    assert [m for m, _ in st.pending(10, exclude={"a", "b"})] == ["c", "d", "e"]


def test_players(st):
    st.mark_player("p", "GOLD", "II", 100.0, 1)
    assert st.player_crawled_since("p", 50.0)
    assert not st.player_crawled_since("p", 150.0)
    assert not st.player_crawled_since("q", 0.0)


def test_record_batches_is_one_transaction(st):
    st.add_matches(["a", "b"], "GOLD", 1.0)
    good = {"file": "na1/26.19/v1/part-00001.parquet", "patch": "26.19", "version": 1,
            "games": 2, "rows": 10}  # fmt: skip
    with pytest.raises(KeyError):
        st.record_batches([good, {"file": "bad"}], ["a", "b"])
    assert st.match_counts() == {"pending": 2}
    assert st.batch_files() == set()
    st.record_batches([good], ["a"], ["b"])
    assert st.match_counts() == {"done": 1, "skipped": 1}
    assert st.batch_files() == {good["file"]}
    assert st.totals()["games"] == 2
    st.delete_patch_batches("26.19")
    assert st.batch_files() == set()


def test_counters_and_errors(st):
    st.add_counts(100, 5, 1, 0)
    st.add_counts(100, 3, 0, 2)
    st.add_counts(50, 9, 9, 9)
    assert st.counts_since(100) == {"requests": 8, "http_429": 1, "http_5xx": 2}
    for i in range(ERRORS_KEPT + 10):
        st.add_error(f"e{i}", float(i))
    errs = st.recent_errors(100)
    assert len(errs) == ERRORS_KEPT
    assert errs[0][1] == f"e{ERRORS_KEPT + 9}"
