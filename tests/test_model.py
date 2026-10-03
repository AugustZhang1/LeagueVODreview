import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from lolreview import features
from lolreview.model import FeatureMismatch, PlaceholderModel, load_model, models_changed

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "training" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


train = _load("train")
synth = _load("make_synthetic_dataset")


def test_train_matches_features():
    assert train.FEATURE_COLUMNS == features.FEATURE_COLUMNS
    assert train.V1_COLUMNS == features.V1_COLUMNS
    assert train.COLUMNS_BY_VERSION[features.FEATURES_VERSION] == features.FEATURE_COLUMNS
    assert train.CATEGORICAL == features.CATEGORICAL_COLUMNS
    assert train.MONOTONE == features.MONOTONE
    assert train.SOUL_TYPES == features.SOUL_TYPES


def _row(**kw):
    row = {c: 0 for c in features.FEATURE_COLUMNS}
    row.update(tier=3, minute=15.0, soul_type="none")
    row.update(kw)
    return row


def test_placeholder_monotone_and_bounded():
    m = load_model(Path("does-not-exist"))
    assert isinstance(m, PlaceholderModel)
    assert (m.kind, m.version, m.metrics, m.patches) == ("stub", "stub", None, None)
    gold = [-20000, -10000, -5000, -1000, 0, 1000, 5000, 10000, 20000]
    ps = m.predict([_row(gold_diff=g) for g in gold])
    assert ps == sorted(ps)
    assert all(0 < p < 1 for p in ps)
    assert math.isclose(m.predict([_row()])[0], 0.5)
    for col in ("kill_diff", "tower_diff", "inhibs_down_diff", "baron_active", "soul_diff"):
        lo, hi = m.predict([_row(**{col: -1}), _row(**{col: 1})])
        assert lo < 0.5 < hi


@pytest.mark.parametrize("minute", [5.0, 20.0, 40.0])
@pytest.mark.parametrize("col", [c for c, m in features.MONOTONE.items() if m != 0])
def test_placeholder_monotone_per_feature(col, minute):
    m = PlaceholderModel()
    values = [-2, -1, 0, 1, 2] if col != "baron_active" else [0, 1]
    if col in ("gold_diff", "cs_diff"):
        values = [v * 1500 if col == "gold_diff" else v * 30 for v in values]
    ps = m.predict([_row(minute=minute, **{col: v}) for v in values])
    sign = features.MONOTONE[col]
    assert all(0 < p < 1 for p in ps)
    assert all((b - a) * sign > 0 for a, b in zip(ps, ps[1:], strict=False))


def test_placeholder_objective_sizes():
    m = PlaceholderModel()
    base = m.predict([_row()])[0]

    def gain(**kw):
        return m.predict([_row(**kw)])[0] - base

    assert 0.02 < gain(blue_dragons=1) < 0.06
    assert gain(blue_dragons=1, red_dragons=1) == pytest.approx(0)
    assert gain(baron_active=1) > 2 * gain(blue_dragons=1)
    assert gain(inhibs_down_diff=1) > 2 * gain(blue_dragons=1)


def test_placeholder_gold_matters_more_late():
    m = PlaceholderModel()
    early, late = m.predict([_row(minute=8, gold_diff=3000), _row(minute=32, gold_diff=3000)])
    assert late > early


def test_placeholder_swings_over_a_game():
    m = PlaceholderModel()
    late_lead = m.predict([_row(gold_diff=15000, kill_diff=15, tower_diff=8, inhibs_down_diff=2)])
    assert late_lead[0] > 0.97


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    base = tmp_path_factory.mktemp("model")
    data, out = base / "data", base / "out"
    synth.make_dataset(data, games=300, seed=5)
    train.main(["--data", str(data), "--out", str(out), "--patches", "26.18,26.19", "--isotonic"])
    return data, out


def test_trained_round_trip(trained):
    data, out = trained
    model = load_model(out)
    assert model.kind == "trained"
    assert len(model.version) == 8 and model.version != "stub"
    assert model.patches == ["26.18", "26.19"]
    assert model.trained_at and model.metrics["features"] == features.FEATURE_COLUMNS

    df = pd.concat([pd.read_parquet(p) for p in sorted(data.rglob("*.parquet"))])
    df = df[df["patch"].astype(str).isin(["26.18", "26.19"])].sample(40, random_state=1)
    rows = [{c: (str(r[c]) if c == "soul_type" else r[c]) for c in features.FEATURE_COLUMNS}
            for r in df.to_dict("records")]  # fmt: skip
    frame = df[features.FEATURE_COLUMNS].copy()
    frame["soul_type"] = pd.Categorical(frame["soul_type"].astype(str), categories=train.SOUL_TYPES)
    booster = lgb.Booster(model_file=str(out / "model.txt"))
    expected = booster.predict(frame)
    iso = json.loads((out / "isotonic.json").read_text())
    expected = np.interp(expected, iso["x"], iso["y"])
    np.testing.assert_allclose(model.predict(rows), expected, atol=1e-9)
    assert model.predict([]) == []


def test_feature_mismatch_raises(trained, tmp_path):
    _, out = trained
    text = (out / "model.txt").read_bytes()  # bytes: LightGBM checks tree sizes, so keep newlines
    assert b"Column_0" not in text and b"gold_diff" in text
    (tmp_path / "model.txt").write_bytes(text.replace(b"gold_diff", b"gold_dif2", 1))
    with pytest.raises(FeatureMismatch, match="trained on features"):
        load_model(tmp_path)


def test_version_1_model_reads_version_2_rows(tmp_path, load_game):
    # The app keeps working with an older model until one is trained on the new features
    data, out = tmp_path / "data", tmp_path / "out"
    synth.make_dataset(data, games=300, seed=5, version=1)
    train.main(["--data", str(data), "--out", str(out), "--no-tune"])
    model = load_model(out)
    assert model.columns == features.V1_COLUMNS
    match, timeline = load_game("NA1_5652762926")
    rows = features.extract_rows(match, timeline, "GOLD")
    frame = pd.DataFrame(rows)[features.V1_COLUMNS]
    frame["soul_type"] = pd.Categorical(frame["soul_type"], categories=train.SOUL_TYPES)
    booster = lgb.Booster(model_file=str(out / "model.txt"))
    np.testing.assert_allclose(model.predict(rows), booster.predict(frame), atol=1e-9)


def test_models_changed(trained, tmp_path):
    _, out = trained
    for name in ("model.txt", "metrics.json"):
        (tmp_path / name).write_bytes((out / name).read_bytes())
    model = load_model(tmp_path)
    assert not models_changed(tmp_path, model)
    (tmp_path / "isotonic.json").write_text('{"x": [0, 1], "y": [0, 1]}')
    assert models_changed(tmp_path, model)
    stub = load_model(tmp_path / "nothing")
    assert not models_changed(tmp_path / "nothing", stub)
    assert models_changed(tmp_path, stub)


def test_stray_isotonic_ignored_when_metrics_say_false(trained, tmp_path):
    _, out = trained
    for name in ("model.txt", "isotonic.json"):
        (tmp_path / name).write_bytes((out / name).read_bytes())
    metrics = json.loads((out / "metrics.json").read_text())
    (tmp_path / "metrics.json").write_text(json.dumps({**metrics, "isotonic": False}))
    plain = load_model(tmp_path)
    assert plain.iso is None
    with_iso = load_model(out)
    assert with_iso.iso is not None
    assert plain.version != with_iso.version


def test_version_changes_with_isotonic_file(trained, tmp_path):
    _, out = trained
    for name in ("model.txt", "isotonic.json", "metrics.json"):
        (tmp_path / name).write_bytes((out / name).read_bytes())
    before = load_model(tmp_path).version
    (tmp_path / "isotonic.json").write_text('{"x": [0, 1], "y": [0.1, 0.9]}')
    assert load_model(tmp_path).version != before


def test_rank_models_trained_saved_and_used(tmp_path, monkeypatch):
    data, out = tmp_path / "data", tmp_path / "out"
    synth.make_dataset(data, games=600, seed=8)
    (out / "tiers" / "OLD").mkdir(parents=True)  # from an earlier run: must not survive
    monkeypatch.setattr(train, "MIN_TIER_GAMES", 30)
    m = train.main(["--data", str(data), "--out", str(out), "--patches", "26.18,26.19"])
    assert not (out / "tiers" / "OLD").exists()
    ranks = {r["tier"]: r for r in m["tier_models"]}
    saved = [t for t, r in ranks.items() if r["saved"]]
    assert ranks and all("overall_log_loss" in r for r in ranks.values() if r["train_games"] >= 30)
    assert sorted(p.name for p in (out / "tiers").glob("*")) == sorted(saved)
    assert "## Rank models" in (out / "report.md").read_text()

    overall_only = load_model(out)
    # a copy of the overall model as one rank's model: rows of that rank must get its answers
    shutil.rmtree(out / "tiers", ignore_errors=True)
    (out / "tiers" / "GOLD").mkdir(parents=True)
    (out / "tiers" / "GOLD" / "metrics.json").write_text('{"isotonic": false}')
    shutil.copy(out / "model.txt", out / "tiers" / "GOLD" / "model.txt")
    model = load_model(out)
    assert models_changed(out, overall_only) and model.version != overall_only.version
    gold = model.by_tier[features.TIER_INDEX["GOLD"]]
    gold._predict = lambda rows: [0.123] * len(rows)
    rows = [_row(tier=features.TIER_INDEX["GOLD"]), _row(tier=features.TIER_INDEX["DIAMOND"])]
    p = model.predict(rows)
    assert p[0] == 0.123 and p[1] == overall_only.predict(rows[1:])[0]
