import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, folder: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / folder / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


synth = _load("make_synthetic_dataset", "training")
drift_eval = _load("drift_eval", "scripts")
train = drift_eval.T


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    root = tmp_path_factory.mktemp("drift") / "data"
    # 2,400 games: 800 per patch, 300 per rank (the synthetic ranks run from Silver to Challenger)
    synth.make_dataset(root, games=2400, seed=5)
    # a copy under a Kaggle run folder, which the loader must leave out
    synth.make_dataset(root / "kaggle_v3" / "run" / "data", games=60, seed=5)
    return root


def test_load_all_skips_kaggle_copies(data):
    df = drift_eval.load_all(data, 3, None, 42)
    assert df["match_id"].nunique() == 2400
    assert set(df["patch"]) == {"26.17", "26.18", "26.19"}


def test_max_rows_keeps_whole_games(data):
    df = drift_eval.load_all(data, 3, 20000, 42)
    assert len(df) <= 20000
    sizes = df.groupby("match_id").size()
    full = drift_eval.load_all(data, 3, None, 42).groupby("match_id").size()
    assert (sizes == full[sizes.index]).all()


def test_main_runs_both_experiments(data, tmp_path, capsys):
    out = tmp_path / "drift.json"
    result = drift_eval.main(["--data", str(data), "--out", str(out)])
    df = drift_eval.load_all(data, 3, None, 42)

    assert result["columns"] == train.V2_COLUMNS  # the champion columns are left out
    assert json.loads(out.read_text())["experiments"] == result["experiments"]
    assert "Difference (second minus first)" in capsys.readouterr().out

    patch = result["experiments"]["unseen_patch"]
    seen, unseen = patch["tests"]
    assert unseen["name"] == "Unseen patch (26.19)"
    assert unseen["games"] == df.loc[df["patch"] == "26.19", "match_id"].nunique()
    assert 0 < seen["games"] < 1600  # 20% of the two older patches
    assert seen["log_loss"] < 0.693

    rank = result["experiments"]["unseen_rank"]
    held, diamond = rank["tests"]
    top = df.loc[df["tier"].astype(int).isin([7, 8, 9]), "match_id"].nunique()
    assert 0 < held["games"] < top
    assert diamond["games"] == df.loc[df["tier"].astype(int) == 6, "match_id"].nunique()
    for test in (seen, unseen, held, diamond):
        assert {"games", "rows", "accuracy", "log_loss", "brier", "calibration_gap_pts"} <= set(
            test
        )


def test_small_groups_are_skipped(data, monkeypatch, capsys):
    monkeypatch.setattr(drift_eval, "MIN_GAMES", 10**6)
    result = drift_eval.main(["--data", str(data)])
    for name in ("unseen_patch", "unseen_rank"):
        assert "skipped" in result["experiments"][name]
    out = capsys.readouterr().out
    assert "Diamond has" in out and "(need 1000000 each)" in out
