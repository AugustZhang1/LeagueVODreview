import json
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from lolreview import upload

TOKEN = "KGAT_secret_token_value"
PATCHES = ["15.8", "15.9", "15.10", "15.11"]


def _write(path: Path, ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({"match_id": ids, "x": list(range(len(ids)))}), path)


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    for i, patch in enumerate(PATCHES):
        for plat in ("na1", "kr"):
            _write(
                d / plat / patch / "v1" / "part-00001.parquet",
                [f"{plat}{i}a", f"{plat}{i}a", f"{plat}{i}b"],
            )
    return d


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text(f"KAGGLE_API_TOKEN={TOKEN}\n", encoding="utf-8")
    monkeypatch.setattr(upload, "read_env", lambda path=None: {"KAGGLE_API_TOKEN": TOKEN})
    monkeypatch.setattr(upload.shutil, "which", lambda name, path=None: "/usr/bin/kaggle")
    return p


def _fake_run(calls, status_rc):
    def run(cmd, **kw):
        calls.append((cmd, kw))
        rc = status_rc if cmd[2] == "status" else 0
        return subprocess.CompletedProcess(cmd, rc, stdout=f"ok {TOKEN}", stderr="")

    return run


def test_only_last_patches_and_create(data_dir, env_file, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(upload.subprocess, "run", _fake_run(calls, status_rc=1))
    rec = upload.run_upload(data_dir, "me/lol-winprob")
    assert rec["patches"] == ["15.9", "15.10", "15.11"]
    assert rec["games"] == 6 * 2
    up = data_dir / ".upload"
    assert not (up / "na1" / "15.8").exists()
    staged = up / "kr" / "15.11" / "v1" / "part-00001.parquet"
    assert staged.samefile(data_dir / "kr" / "15.11" / "v1" / "part-00001.parquet")
    assert calls[-1][0][:3] == ["kaggle", "datasets", "create"]
    assert "--dir-mode" in calls[-1][0]
    assert calls[-1][1]["env"]["KAGGLE_API_TOKEN"] == TOKEN
    out = capsys.readouterr()
    assert TOKEN not in out.out + out.err

    meta = json.loads((up / "dataset-metadata.json").read_text())
    assert meta["isPrivate"] is True and meta["id"] == "me/lol-winprob"
    last = json.loads((data_dir / "last_upload.json").read_text())
    assert set(last) == {"uploaded_at", "games", "bytes", "patches"}


def test_version_when_dataset_exists(data_dir, env_file, monkeypatch):
    calls = []
    monkeypatch.setattr(upload.subprocess, "run", _fake_run(calls, status_rc=0))
    upload.run_upload(data_dir, "me/lol-winprob")
    cmd = calls[-1][0]
    assert cmd[:3] == ["kaggle", "datasets", "version"]
    assert cmd[-2:] == ["-m", "12 games"]


def test_dry_run_runs_nothing(data_dir, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("subprocess used")

    monkeypatch.setattr(upload.subprocess, "run", boom)
    rec = upload.run_upload(data_dir, "me/x", dry_run=True)
    assert rec["games"] == 12
    assert not (data_dir / ".upload").exists()
    assert not (data_dir / "last_upload.json").exists()


def test_missing_token(data_dir, monkeypatch):
    monkeypatch.setattr(upload, "read_env", lambda path=None: {})
    with pytest.raises(upload.UploadError, match="KAGGLE_API_TOKEN"):
        upload.run_upload(data_dir, "me/x")


def test_missing_cli(data_dir, monkeypatch):
    monkeypatch.setattr(upload, "read_env", lambda path=None: {"KAGGLE_API_TOKEN": TOKEN})
    monkeypatch.setattr(upload.shutil, "which", lambda name, path=None: None)
    with pytest.raises(upload.UploadError, match="kaggle CLI"):
        upload.run_upload(data_dir, "me/x")


def test_failure_redacts_token(data_dir, env_file, monkeypatch):
    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=f"bad {TOKEN}")

    monkeypatch.setattr(upload.subprocess, "run", run)
    with pytest.raises(upload.UploadError) as e:
        upload.run_upload(data_dir, "me/x")
    assert TOKEN not in str(e.value)
    assert not (data_dir / "last_upload.json").exists()


def test_games_from_metadata(tmp_path):
    p = tmp_path / "a.parquet"
    pq.write_table(pa.table({"x": [1, 2]}).replace_schema_metadata({"games": "7"}), p)
    assert upload.count_games(p) == 7
