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
    kept = m["champion_columns"]["used"]
    assert m["features"] == (train.FEATURE_COLUMNS if kept else train.V2_COLUMNS)
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
    df = train.load_data(data, ["26.18", "26.19"], 0, None, 42)
    tr, va, te = train.split_by_match(df, 42)
    ids = [set(d["match_id"]) for d in (tr, va, te)]
    assert not (ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])
    assert sum(len(i) for i in ids) == df["match_id"].nunique()


def test_lightgbm_learns(run):
    _, _, m = run
    assert m["models"]["lightgbm"]["overall"]["log_loss"] < 0.693


def _random_rows(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({c: rng.integers(-3, 4, n) for c in train.V1_COLUMNS})
    df = df.assign(
        tier=rng.integers(0, 10, n), minute=rng.integers(0, 40, n),
        gold_diff=rng.normal(0, 4000, n), cs_diff=rng.normal(0, 30, n),
        soul_type=pd.Categorical(rng.choice(train.SOUL_TYPES, n), categories=train.SOUL_TYPES),
    )  # fmt: skip
    for c in (c for c in train.FEATURE_COLUMNS if c not in train.V1_COLUMNS):
        df[c] = rng.integers(0, 120, n) if c.endswith("_s") else rng.integers(-3, 4, n)
    return df[train.FEATURE_COLUMNS]


SWEEPS = {"gold_diff": np.linspace(-15000, 15000, 13), "cs_diff": np.linspace(-90, 90, 7),
          "blue_dead_s": np.arange(0, 200, 25), "red_dead_s": np.arange(0, 200, 25)}  # fmt: skip


def assert_monotone(booster, cols: list[str]) -> None:
    base = _random_rows()[cols]
    for col in (c for c in cols if train.MONOTONE[c]):
        prev = None
        for v in SWEEPS.get(col, range(-4, 5)):
            pred = booster.predict(base.assign(**{col: v})) * train.MONOTONE[col]
            if prev is not None:
                assert (pred >= prev - 1e-9).all(), col
            prev = pred


def test_monotone(run):
    import lightgbm as lgb

    _, out, m = run
    assert_monotone(lgb.Booster(model_file=str(out / "model.txt")), m["features"])


def test_every_setting_monotone(tmp_path):
    data = tmp_path / "data"
    synth.make_dataset(data, games=300, seed=4)
    df = train.load_data(data, [], 0, None, 42)
    tr, va, _ = train.split_by_match(df, 42)
    table = train.champion_table(tr)
    tr, va = (train.add_champion_features(d, table) for d in (tr, va))
    for setting in train.PARAM_GRID:
        assert_monotone(train.fit_lightgbm(tr, va, train.FEATURE_COLUMNS, "none", 42, setting),
                        train.FEATURE_COLUMNS)  # fmt: skip


def test_retrain_without_isotonic_removes_old_file(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    synth.make_dataset(data, games=300, seed=5)
    args = ["--data", str(data), "--out", str(out), "--patches", "26.18,26.19"]
    train.main([*args, "--isotonic"])
    assert (out / "isotonic.json").exists()
    metrics = train.main(args)
    assert not (out / "isotonic.json").exists()
    assert metrics["isotonic"] is False


def test_version_picked(tmp_path, monkeypatch):
    data = tmp_path / "data"
    synth.make_dataset(data, games=200, seed=1, version=1)
    synth.make_dataset(data, games=100, seed=2, version=2)

    def version(asked=0):
        df = train.load_data(data, [], asked, None, 42)
        return int(df["features_version"].iloc[0]), df["match_id"].nunique()

    assert version() == (1, 200)  # version 2 has too few games yet: the one with the most
    monkeypatch.setattr(train, "MIN_VERSION_GAMES", 100)
    assert version() == (2, 100)
    assert version(1) == (1, 200)
    v1 = train.load_data(data, [], 1, None, 42)
    assert "alive_diff" not in v1.columns


def test_newest_version_compared_with_older_ones(run):
    _, out, m = run
    assert m["features_version"] == 3
    cc = m["champion_columns"]
    assert cc["used"] == (cc["val_log_loss_with"] < cc["val_log_loss_without"])
    c = m["feature_set_comparison"]
    assert set(c["v1"]) == set(c["v2"]) == set(c["new"]) == {"accuracy", "log_loss", "brier"}
    assert {"v1_log_loss", "v2_log_loss", "log_loss"} <= set(c["by_minute"][0])
    assert [r["bucket"] for r in c["by_minute"]] == [
        r["bucket"] for r in m["models"]["lightgbm"]["by_minute"]
    ]
    names = [r["situation"] for r in c["situations"]]
    assert names and set(names) <= {name for name, _ in train.SITUATIONS}
    assert all(r["rows"] > 0 and r["games"] > 0 for r in c["situations"])
    assert {r["feature"] for r in m["feature_effects"]} <= set(train.EFFECT_FEATURES)
    assert {"champ_wr_diff", "scaling_diff"} <= {r["feature"] for r in m["feature_effects"]}
    assert all(r["size_pts"] >= abs(r["effect_pts"]) for r in m["feature_effects"])
    assert len(m["tuning"]) == len(train.PARAM_GRID)
    kept = [r for r in m["tuning"] if r["kept"]]
    assert len(kept) == 1 and kept[0]["setting"] == m["setting"]
    assert kept[0]["val_log_loss"] == min(r["val_log_loss"] for r in m["tuning"])
    report = (out / "report.md").read_text()
    for heading in (
        "## Features version 3 against older versions",
        "### Situations",
        "## Champions",
        "## What the newer features are worth",
        "## LightGBM settings tried",
    ):
        assert heading in report  # fmt: skip


def test_champion_table(run):
    data, out, m = run
    table = json.loads((out / "champions.json").read_text())
    assert set(table) <= set(synth.CHAMPIONS) and len(table) > 30
    assert all(0 < v["win_rate"] < 1 and v["games"] > 0 for v in table.values())
    ch = m["champions"]
    assert ch["champions"] == len(table)
    ups = [r["per_10_min_pts"] for r in ch["scale_up"]]
    assert ups == sorted(ups, reverse=True)


def test_champion_numbers_find_scaling():
    # Hand-made games: Late wins long games and loses short ones, Early the opposite
    games = []
    for i in range(400):
        long = i % 2 == 0
        late_blue = i % 4 < 2
        blue_won = int(long == late_blue)
        blue, red = ("Late,A", "Early,B") if late_blue else ("Early,A", "Late,B")
        games.append({"match_id": f"g{i}", "blue_champs": blue, "red_champs": red,
                      "blue_won": blue_won, "duration_s": 2400 if long else 1200})  # fmt: skip
    df = pd.DataFrame(games)
    table = train.champion_table(df)
    assert table["Late"]["slope"] > 0 > table["Early"]["slope"]
    assert table["A"]["slope"] == pytest.approx(0, abs=1e-9)
    assert table["Late"]["win_rate"] == pytest.approx(0.5)
    f = train.add_champion_features(df, table)
    late_blue = df["blue_champs"].str.startswith("Late")
    assert (f.loc[late_blue, "scaling_diff"] > 0).all()
    assert (f.loc[~late_blue, "scaling_diff"] < 0).all()


def test_out_of_fold_champion_numbers(run):
    data, _, _ = run
    df = train.load_data(data, [], 0, None, 42)
    tr, _, _ = train.split_by_match(df, 42)
    oof = train.add_champion_features_oof(tr)
    assert oof.index.equals(tr.index)
    assert oof["champ_wr_diff"].notna().all()
    one_game = oof.groupby("match_id")["scaling_diff"].nunique()
    assert (one_game == 1).all()


def test_version_1_training(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    synth.make_dataset(data, games=300, seed=6, version=1)
    m = train.main(["--data", str(data), "--out", str(out), "--no-tune"])
    assert m["features_version"] == 1 and m["features"] == train.V1_COLUMNS
    assert m["feature_set_comparison"] is None and m["feature_effects"] == []
    assert len(m["tuning"]) == 1 and m["setting"] == train.PARAM_GRID[0]
    assert "against version 1" not in (out / "report.md").read_text()
