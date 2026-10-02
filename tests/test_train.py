import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "training" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


train = _load("train")
synth = _load("make_synthetic_dataset")


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    base = tmp_path_factory.mktemp("train")
    data, out = base / "data", base / "out"
    synth.make_dataset(data, games=1200, seed=3)
    metrics = train.main(
        ["--data", str(data), "--out", str(out), "--patches", "26.18,26.19", "--isotonic"]
    )
    return data, out, metrics


def test_outputs_exist(run):
    _, out, _ = run
    for name in ["model.txt", "metrics.json", "calibration.png", "accuracy_by_minute.png",
                 "report.md", "isotonic.json"]:  # fmt: skip
        assert (out / name).stat().st_size > 0, name


def test_metrics_keys(run):
    _, out, _ = run
    m = json.loads((out / "metrics.json").read_text())
    for key in ["trained_at", "games", "rows", "patches", "features_version", "features", "split",
                "models", "calibration", "max_calibration_gap_pts", "feature_importance",
                "isotonic", "weighting"]:  # fmt: skip
        assert key in m, key
    assert m["features"] == train.FEATURE_COLUMNS
    assert m["patches"] == ["26.18", "26.19"]
    assert m["isotonic"] is True and m["weighting"] == "none"
    assert set(m["split"]) == {"train", "validation", "test"}
    for name in ("lightgbm", "baseline"):
        mm = m["models"][name]
        assert set(mm["overall"]) == {"accuracy", "log_loss", "brier"}
        assert {"bucket", "accuracy", "log_loss", "brier", "rows"} <= set(mm["by_minute"][0])
        assert {"tier", "tier_index", "games", "accuracy", "log_loss"} <= set(mm["by_tier"][0])
    assert {"bin", "predicted", "actual", "count"} <= set(m["calibration"][0])
    gains = [r["gain"] for r in m["feature_importance"]]
    assert gains == sorted(gains, reverse=True)


def test_no_match_in_two_splits(run):
    data, _, _ = run
    df = train.load_data(data, ["26.18", "26.19"], 1, None, 42)
    tr, va, te = train.split_by_match(df, 42)
    ids = [set(d["match_id"]) for d in (tr, va, te)]
    assert not (ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])
    assert sum(len(i) for i in ids) == df["match_id"].nunique()


def test_lightgbm_learns(run):
    _, _, m = run
    assert m["models"]["lightgbm"]["overall"]["log_loss"] < 0.693


def test_gold_diff_monotone(run):
    import lightgbm as lgb

    _, out, _ = run
    booster = lgb.Booster(model_file=str(out / "model.txt"))
    rng = np.random.default_rng(0)
    base = pd.DataFrame(
        {
            "tier": rng.integers(0, 10, 200),
            "minute": rng.integers(0, 40, 200),
            "gold_diff": 0.0,
            "kill_diff": rng.integers(-10, 10, 200),
            "tower_diff": rng.integers(-5, 5, 200),
            "level_diff": rng.normal(0, 2, 200),
            "cs_diff": rng.normal(0, 30, 200),
            "grub_diff": rng.integers(-3, 3, 200),
            "herald_diff": rng.integers(-1, 2, 200),
            "atakhan_diff": rng.integers(-1, 2, 200),
            "inhibs_down_diff": rng.integers(-2, 3, 200),
            "baron_active": rng.integers(-1, 2, 200),
            "elder_active": rng.integers(-1, 2, 200),
            "blue_dragons": rng.integers(0, 4, 200),
            "red_dragons": rng.integers(0, 4, 200),
            "soul_diff": rng.integers(-1, 2, 200),
            "soul_type": pd.Categorical(
                rng.choice(train.SOUL_TYPES, 200), categories=train.SOUL_TYPES
            ),
        }
    )
    prev = None
    for gold in np.linspace(-15000, 15000, 31):
        pred = booster.predict(base.assign(gold_diff=gold)[train.FEATURE_COLUMNS])
        if prev is not None:
            assert (pred >= prev - 1e-9).all()
        prev = pred


def test_retrain_without_isotonic_removes_old_file(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    synth.make_dataset(data, games=300, seed=5)
    args = ["--data", str(data), "--out", str(out), "--patches", "26.18,26.19"]
    train.main([*args, "--isotonic"])
    assert (out / "isotonic.json").exists()
    metrics = train.main(args)
    assert not (out / "isotonic.json").exists()
    assert metrics["isotonic"] is False
