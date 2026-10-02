import copy
import threading
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from lolreview import crawler, features
from lolreview.config import load_config
from lolreview.fake_riot import FakeRiotClient
from lolreview.state import State, state_path


def make_cfg(tiers=("CHALLENGER",), cap=10_000, kept=3):
    cfg = copy.deepcopy(load_config())
    cfg["crawl"].update(
        tiers=list(tiers),
        bottom_tier=tiers[-1],
        games_per_tier_per_pass=cap,
        patches_kept=kept,
    )
    return cfg


def make_crawler(data_dir, client=None, batch_games=20, stop=None, **cfg_kw):
    client = client or FakeRiotClient("na1", apex_size=12)
    return crawler.PlatformCrawler(
        "na1", client, data_dir, stop or threading.Event(), make_cfg(**cfg_kw),
        batch_games=batch_games, idle_sleep_s=0.01,
    )  # fmt: skip


def batch_files(data_dir):
    return sorted(Path(data_dir).rglob("*.parquet"))


def all_rows(files):
    table = pa.concat_tables([pq.read_table(f) for f in files])
    return sorted(table.to_pylist(), key=lambda r: (r["match_id"], r["t"]))


def test_fake_crawl_rows_and_layout(tmp_path):
    client = FakeRiotClient("na1", apex_size=12)
    c = make_crawler(tmp_path, client)
    c._run_pass()
    c.flush()
    st = State(state_path(tmp_path, "na1"))
    done = st.match_ids_with_status("done")
    counts = st.match_counts()
    st.close()
    assert len(done) >= 20 and counts.get("skipped", 0) > 0  # fixture 1 is a remake
    assert "pending" not in counts

    files = batch_files(tmp_path)
    assert len(files) > 1
    for f in files:
        assert f.relative_to(tmp_path).parts[:3] == (
            "na1",
            "26.19",
            f"v{features.FEATURES_VERSION}",
        )
        assert f.name.startswith("part-") and f.suffix == ".parquet"
    assert [f.name for f in files][:2] == ["part-00001.parquet", "part-00002.parquet"]
    meta = pq.ParquetFile(files[0]).schema_arrow.metadata
    assert int(meta[b"games"]) == len(set(r["match_id"] for r in all_rows(files[:1])))
    assert pq.ParquetFile(files[0]).metadata.row_group(0).column(0).compression == "ZSTD"

    expected = []
    for match_id in done:
        match = client.match("americas", match_id)
        expected += features.extract_rows(
            match, client.timeline("americas", match_id), "CHALLENGER"
        )
    want = sorted(
        features.rows_to_table(expected).to_pylist(), key=lambda r: (r["match_id"], r["t"])
    )
    assert all_rows(files) == want
    assert not [p for p in tmp_path.rglob("*.tmp")]


def test_stop_and_restart_no_duplicates(tmp_path):
    class Stopper(FakeRiotClient):
        def __init__(self, *a, stop_after, stop, **kw):
            super().__init__(*a, **kw)
            self.stop_after, self.stop_event, self.calls = stop_after, stop, 0

        def timeline(self, cluster, match_id):
            self.calls += 1
            if self.calls >= self.stop_after:
                self.stop_event.set()
            return super().timeline(cluster, match_id)

    stop = threading.Event()
    first = make_crawler(
        tmp_path, Stopper("na1", apex_size=12, stop_after=45, stop=stop), stop=stop
    )
    first._run_pass()
    unflushed = len(first.buffer)
    first.state.close()  # simulate a crash: the buffer is lost
    assert unflushed > 0

    st = State(state_path(tmp_path, "na1"))
    assert st.match_counts().get("pending", 0) > 0
    st.close()

    second = make_crawler(tmp_path)
    second._run_pass()
    second.flush()
    st = State(state_path(tmp_path, "na1"))
    counts = st.match_counts()
    st.close()
    assert "pending" not in counts

    ids = [r["match_id"] for r in all_rows(batch_files(tmp_path))]
    unique = set(ids)
    assert counts["done"] == len(unique)
    # every row of a game sits in exactly one file
    per_file = [{r["match_id"] for r in all_rows([f])} for f in batch_files(tmp_path)]
    assert sum(len(s) for s in per_file) == len(unique)


def test_deleted_state_db_keeps_batch_files(tmp_path):
    first = make_crawler(tmp_path)
    first._run_pass()
    first.flush()
    first.state.close()
    before = batch_files(tmp_path)
    assert len(before) > 1
    for f in tmp_path.glob("state-na1.sqlite*"):
        f.unlink()

    second = make_crawler(tmp_path)
    second.stop.set()
    second.run()
    assert batch_files(tmp_path) == before
    assert second._next_part(before[0].parent) == len(before) + 1


def test_leftover_tmp_removed_and_recorded_tmp_renamed(tmp_path):
    folder = tmp_path / "na1" / "26.19" / "v1"
    folder.mkdir(parents=True)
    st = State(state_path(tmp_path, "na1"))
    st.record_batches(
        [{"file": "na1/26.19/v1/part-00002.parquet", "patch": "26.19", "version": 1,
          "games": 1, "rows": 1}],
        [],
    )  # fmt: skip
    st.close()
    unrecorded = folder / "part-00003.parquet.tmp"
    recorded = folder / "part-00002.parquet.tmp"
    unrecorded.write_bytes(b"x")
    recorded.write_bytes(b"y")

    c = make_crawler(tmp_path)
    assert c._next_part(folder) == 4
    c.stop.set()
    c.run()
    assert not unrecorded.exists() and not recorded.exists()
    assert (folder / "part-00002.parquet").read_bytes() == b"y"


def test_unrecorded_finished_batch_is_kept(tmp_path):
    stray = tmp_path / "na1" / "26.19" / "v1" / "part-00007.parquet"
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"x")
    c = make_crawler(tmp_path)
    c.stop.set()
    c.run()
    assert stray.read_bytes() == b"x"


def test_failed_commit_leaves_no_files(tmp_path):
    c = make_crawler(tmp_path, batch_games=10_000)
    c._run_pass()
    assert c.buffer and not batch_files(tmp_path)

    def boom(*a, **kw):
        raise RuntimeError("db down")

    c.state.record_batches = boom
    try:
        c.flush()
    except RuntimeError:
        pass
    assert not list(tmp_path.rglob("part-*"))
    assert c.buffer  # still buffered for a retry


def test_foreign_files_survive_start_and_patch_change(tmp_path):
    root = tmp_path / "na1"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "keep.txt").write_text("hi")
    (root / "readme.txt").write_text("hi")
    (root / "1.2.3").mkdir()
    old = root / "26.16"
    old.mkdir()
    (old / "stale.txt").write_text("x")

    client = FakeRiotClient("na1", apex_size=12, patches=("26.19", "26.18", "26.17"))
    c = make_crawler(tmp_path, client)
    c._recover_batches()
    c._drop_old_patch_folders()
    for _ in range(3):
        c._run_pass()
    c.flush()
    assert (root / "notes" / "keep.txt").exists()
    assert (root / "readme.txt").exists()
    assert (root / "1.2.3").is_dir()  # not shaped like a patch
    assert not old.exists()


def test_cap_per_tier_per_pass(tmp_path):
    c = make_crawler(tmp_path, tiers=("CHALLENGER", "GRANDMASTER"), cap=30)
    c._run_pass()
    c.flush()
    st = State(state_path(tmp_path, "na1"))
    rows = st.db.execute("SELECT tier, COUNT(*) AS n FROM matches GROUP BY tier").fetchall()
    st.close()
    assert {r["tier"]: r["n"] for r in rows} == {"CHALLENGER": 30, "GRANDMASTER": 30}


def test_next_pass_visits_new_players_only(tmp_path):
    client = FakeRiotClient("na1", apex_size=12, matches_per_player=5)
    c = make_crawler(tmp_path, client, tiers=("GOLD",), cap=20)
    client.pages = 3
    client.entries_per_page = 10
    c._run_pass()
    first_players = c.state.player_count()
    assert c.state.meta_int("pass_no") == 2
    c._run_pass()
    assert c.state.player_count() > first_players
    assert c.state.meta_int("added:2:GOLD") > 0


def test_remakes_and_old_patches_skipped(tmp_path):
    patches = ("26.19", "26.18", "26.17", "26.16", "26.15")
    client = FakeRiotClient("na1", apex_size=12, patches=patches)
    c = make_crawler(tmp_path, client)
    for _ in range(4):
        c._run_pass()
    c.flush()
    rows = all_rows(batch_files(tmp_path))
    assert {r["patch"] for r in rows} <= {"26.19", "26.18", "26.17"}
    assert all(r["duration_s"] >= 300 for r in rows)
    st = State(state_path(tmp_path, "na1"))
    assert st.match_counts()["skipped"] > 0
    st.close()


def test_rolling_deletion_of_old_patches(tmp_path):
    old = make_crawler(tmp_path, FakeRiotClient("na1", apex_size=12, patches=("26.16",)))
    old._run_pass()
    old.flush()
    assert (tmp_path / "na1" / "26.16").is_dir()
    old.state.close()

    new_client = FakeRiotClient("na1", seed=1, apex_size=12, patches=("26.19", "26.18", "26.17"))
    new = make_crawler(tmp_path, new_client)
    for _ in range(3):
        new._run_pass()
    new.flush()
    folders = {p.name for p in (tmp_path / "na1").iterdir() if p.is_dir()}
    assert folders == {"26.17", "26.18", "26.19"}
    assert all("26.16" not in f for f in new.state.batch_files())
    assert new.state.meta_get("newest_patch") == "26.19"
    assert new.state.meta_int("pass_no") > 1  # new patch restarted from the top


def test_main_fake_run(tmp_path):
    code = crawler.main(
        ["--fake", "--platforms", "na1", "--minutes", "0.1", "--batch-games", "10",
         "--data", str(tmp_path), "--status-port", "0"]
    )  # fmt: skip
    assert code == 0
    assert batch_files(tmp_path)
