import importlib.util
import sqlite3
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "dataset_report.py"
spec = importlib.util.spec_from_file_location("dataset_report", SCRIPT)
dataset_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dataset_report)


def write(path: Path, match_ids: list[str], tier: int) -> None:
    """A Parquet file with two rows per game."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ids = np.repeat(match_ids, 2)
    table = pa.table({"match_id": ids, "tier": np.full(len(ids), tier, dtype=np.int16)})
    pq.write_table(table, path)


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "data"
    write(root / "na1" / "16.17" / "v3" / "part-00001.parquet", ["NA1_1", "NA1_2"], 9)
    write(root / "na1" / "16.18" / "v3" / "part-00001.parquet", ["NA1_3"], 6)
    # NA1_2 again in another file: a duplicate
    write(root / "na1" / "16.18" / "v3" / "part-00002.parquet", ["NA1_2"], 9)
    write(root / "euw1" / "16.18" / "v2" / "part-00001.parquet", ["EUW1_1"], 6)
    # a copy under the Kaggle run folder is not in the crawler's layout: left out
    write(root / "kaggle_v3" / "run" / "data" / "na1" / "16.17" / "v3" / "p.parquet", ["NA1_1"], 9)
    state = sqlite3.connect(root / "state-na1.sqlite")
    state.execute("CREATE TABLE matches (match_id TEXT, status TEXT)")
    state.executemany("INSERT INTO matches VALUES (?, ?)",
                      [("NA1_1", "done"), ("NA1_2", "done"), ("NA1_9", "pending")])  # fmt: skip
    state.commit()
    state.close()
    return root


def test_rows_and_duplicates(data):
    rows, size = dataset_report.load_rows(data)
    assert rows["file"].nunique() == 4  # the Kaggle copy is left out
    assert len(rows) == 10  # two rows per game
    assert rows["match_id"].nunique() == 4
    assert size > 0
    assert dataset_report.duplicates(rows) == (1, 1)  # NA1_2 is in two files


def test_breakdowns(data):
    rows, _ = dataset_report.load_rows(data)
    by_platform = dataset_report.breakdown(rows, "platform", "Platform")
    assert "| na1 | 3 | 8 |" in by_platform
    assert "| euw1 | 1 | 2 |" in by_platform
    by_version = dataset_report.breakdown(rows, "version", "Version")
    assert "| 2 | 1 | 2 |" in by_version and "| 3 | 3 | 8 |" in by_version
    by_rank = dataset_report.breakdown(rows, "tier", "Rank", dataset_report.rank_name)
    assert "| Challenger | 2 | 6 |" in by_rank
    assert "| Diamond | 2 | 4 |" in by_rank


def test_state_counts(data, tmp_path):
    assert dataset_report.state_counts(data) == {"na1": {"done": 2, "pending": 1}}
    assert dataset_report.state_counts(tmp_path / "empty") == {}


def test_main_prints_sections(data, capsys):
    dataset_report.main(["--data", str(data)])
    out = capsys.readouterr().out
    for heading in ("## By platform", "## By patch", "## By rank", "## By features version"):
        assert heading in out
    assert "Games in more than one file: 1 (1 extra copies)" in out
    assert "## Crawl state" in out and "na1: done 2, pending 1" in out


def test_main_fails_without_files(tmp_path):
    with pytest.raises(SystemExit):
        dataset_report.main(["--data", str(tmp_path)])
