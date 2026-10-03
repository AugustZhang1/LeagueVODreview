"""Train the win-chance model (Plan Steps 10 and 18). One standalone file, meant to run on Kaggle.

    python training/train.py --data DIR --out DIR [--patches 26.18,26.19] [--features-version N]
                             [--weight none|game] [--isotonic] [--no-tune] [--seed 42]
                             [--max-rows N]

With no arguments (Kaggle) it reads the first folder under /kaggle/input and writes to
/kaggle/working. Needs: pandas, numpy, pyarrow, lightgbm, scikit-learn, matplotlib.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss  # noqa: E402
from sklearn.model_selection import GroupShuffleSplit  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

V1_COLUMNS = [
    "tier", "minute", "gold_diff", "kill_diff", "tower_diff", "level_diff", "cs_diff",
    "grub_diff", "herald_diff", "quest_diff", "inhibs_down_diff", "baron_active",
    "elder_active", "blue_dragons", "red_dragons", "soul_diff", "soul_type",
]  # fmt: skip
FEATURE_COLUMNS = V1_COLUMNS + [
    "alive_diff", "blue_dead_s", "red_dead_s", "baron_pit_in_s", "dragon_pit_in_s",
    "baron_setup_diff", "dragon_setup_diff", "grouped_diff", "split_diff", "enemy_jungle_diff",
    "wards_placed_diff", "wards_killed_diff",
]  # fmt: skip
COLUMNS_BY_VERSION = {1: V1_COLUMNS, 2: FEATURE_COLUMNS}
CATEGORICAL = ["soul_type"]
MONOTONE = {
    "tier": 0, "minute": 0, "gold_diff": 1, "kill_diff": 1, "tower_diff": 1, "level_diff": 1,
    "cs_diff": 1, "grub_diff": 1, "herald_diff": 1, "quest_diff": 1, "inhibs_down_diff": 1,
    "baron_active": 1, "elder_active": 1, "blue_dragons": 1, "red_dragons": -1, "soul_diff": 1,
    "soul_type": 0, "alive_diff": 1, "blue_dead_s": -1, "red_dead_s": 1, "baron_pit_in_s": 0,
    "dragon_pit_in_s": 0, "baron_setup_diff": 0, "dragon_setup_diff": 0, "grouped_diff": 0,
    "split_diff": 0, "enemy_jungle_diff": 0, "wards_placed_diff": 0, "wards_killed_diff": 0,
}  # fmt: skip
SOUL_TYPES = ["none", "Infernal", "Mountain", "Ocean", "Cloud", "Hextech", "Chemtech"]

TIER_NAMES = [
    "Iron", "Bronze", "Silver", "Gold", "Platinum", "Emerald", "Diamond", "Master",
    "Grandmaster", "Challenger", "Pro",
]  # fmt: skip
MINUTE_EDGES = [0, 5, 10, 15, 20, 25, 30, 35, 40, np.inf]
MINUTE_LABELS = ["0-5", "5-10", "10-15", "15-20", "20-25", "25-30", "30-35", "35-40", "40+"]
CALIBRATION_MIN_COUNT = 20  # bins with fewer rows are listed but ignored for the max gap
MIN_TIER_GAMES = 1000  # training games a rank needs before it gets its own model
MIN_VERSION_GAMES = 10_000  # games a newer features version needs before it is used by default

# LightGBM settings, each tried with early stopping; the best validation log loss is kept. The
# first is the original setting. A game's rows share one label, so a bigger min_data_in_leaf stops
# a leaf from learning a few games by heart; "intermediate" monotone constraints are less strict
# than "basic" and still monotone.
PARAM_GRID = [
    {"num_leaves": 31, "min_data_in_leaf": 20},
    {"num_leaves": 31, "min_data_in_leaf": 500, "monotone_constraints_method": "intermediate"},
    {"num_leaves": 63, "min_data_in_leaf": 1000, "monotone_constraints_method": "intermediate",
     "feature_fraction": 0.8},
    {"num_leaves": 127, "min_data_in_leaf": 2000, "monotone_constraints_method": "intermediate",
     "feature_fraction": 0.8},
]  # fmt: skip

# Version 2: test rows where the new features should matter, to compare with version 1 on
SITUATIONS = [
    ("Baron pit up or within 90 s, one team has more players near it",
     lambda d: d["baron_setup_diff"] != 0),
    ("Dragon pit up or within 90 s, one team has more players near it",
     lambda d: d["dragon_setup_diff"] != 0),
    ("Baron up (20 min on)", lambda d: (d["baron_pit_in_s"] == 0) & (d["minute"] >= 20)),
    ("A team is split pushing", lambda d: d["split_diff"] != 0),
    ("Someone is dead", lambda d: d["blue_dead_s"] + d["red_dead_s"] > 0),
]  # fmt: skip
# Version 2 position and vision features whose effect on the win chance the report shows
EFFECT_FEATURES = [
    "baron_setup_diff", "dragon_setup_diff", "split_diff", "grouped_diff", "enemy_jungle_diff",
    "wards_placed_diff", "wards_killed_diff",
]  # fmt: skip


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- data


def file_version(data: Path, f: Path) -> int:
    """The features version from a `v<N>` folder in the path; 1 for files without one."""
    m = re.search(r"(?:^|/)v(\d+)/", f.relative_to(data).as_posix() + "/")
    return int(m.group(1)) if m else 1


def pick_version(games: dict[int, int]) -> int:
    """The newest known features version with enough games, else the one with the most."""
    known = {v: n for v, n in games.items() if v in COLUMNS_BY_VERSION}
    if not known:
        raise SystemExit(f"no features version this script knows in the data: {sorted(games)}")
    ready = [v for v, n in known.items() if n >= MIN_VERSION_GAMES]
    return max(ready) if ready else max(known, key=lambda v: (known[v], v))


def load_data(
    data: Path, patches: list[str] | None, features_version: int, max_rows: int | None, seed: int
) -> pd.DataFrame:
    """Rows of one features version (0: `pick_version`), with a `features_version` column."""
    files = sorted(data.rglob("*.parquet"))
    log(f"found {len(files)} parquet files under {data}")
    by_version: dict[int, list[pd.DataFrame]] = {}
    for f in files:
        df = pd.read_parquet(f)
        if "features_version" in df.columns:
            parts = dict(list(df.groupby(df["features_version"].astype(int))))
        else:
            parts = {file_version(data, f): df}
        for version, part in parts.items():
            part = part.assign(match_id=part["match_id"].astype(str),
                               patch=part["patch"].astype(str))  # fmt: skip
            if patches:
                part = part[part["patch"].isin(patches)]
            if not part.empty:
                by_version.setdefault(int(version), []).append(part)
    if not by_version:
        raise SystemExit("no rows left after the patch filter")
    games = {v: int(pd.concat([p["match_id"] for p in ps]).nunique())
             for v, ps in sorted(by_version.items())}  # fmt: skip
    log(f"games per features version: {games}")
    version = features_version or pick_version(games)
    if version not in by_version or version not in COLUMNS_BY_VERSION:
        raise SystemExit(f"no rows of features version {version} this script can train on")
    log(f"using features version {version}")
    df = pd.concat(by_version[version], ignore_index=True)
    df["features_version"] = version
    for col in COLUMNS_BY_VERSION[version]:
        if col not in df.columns:
            log(f"column {col} missing, filling with 0")
            df[col] = "none" if col == "soul_type" else 0
    df["soul_type"] = pd.Categorical(df["soul_type"].astype(str), categories=SOUL_TYPES)
    df["blue_won"] = df["blue_won"].astype(int)
    if max_rows and len(df) > max_rows:
        rng = np.random.default_rng(seed)
        ids = df["match_id"].unique()
        rng.shuffle(ids)
        sizes = df.groupby("match_id").size().reindex(ids).to_numpy()
        keep = ids[np.cumsum(sizes) <= max_rows]
        df = df[df["match_id"].isin(set(keep))].reset_index(drop=True)
        log(f"--max-rows: kept {len(keep)} games")
    return df


def split_by_match(df: pd.DataFrame, seed: int):
    """70 / 10 / 20 train / validation / test, grouped by match_id."""
    groups = df["match_id"].to_numpy()
    outer = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    rest, test = next(outer.split(df, groups=groups))
    inner = GroupShuffleSplit(n_splits=1, test_size=0.125, random_state=seed)
    tr, va = next(inner.split(df.iloc[rest], groups=groups[rest]))
    train_idx, val_idx = rest[tr], rest[va]
    sets = [set(groups[i]) for i in (train_idx, val_idx, test)]
    assert not (sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2]), "match in two splits"
    return df.iloc[train_idx], df.iloc[val_idx], df.iloc[test]


# ---------------------------------------------------------------- metrics


def scores(y: np.ndarray, p: np.ndarray) -> dict:
    return {
        "accuracy": float(accuracy_score(y, p >= 0.5)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier": float(brier_score_loss(y, p)),
    }


def by_minute(df: pd.DataFrame, p: np.ndarray) -> list[dict]:
    bucket = pd.cut(df["minute"].to_numpy(), MINUTE_EDGES, labels=MINUTE_LABELS, right=False)
    out = []
    for label in MINUTE_LABELS:
        mask = np.asarray(bucket == label)
        if mask.any():
            out.append({"bucket": label, **scores(df["blue_won"].to_numpy()[mask], p[mask]),
                        "rows": int(mask.sum())})  # fmt: skip
    return out


def by_tier(df: pd.DataFrame, p: np.ndarray) -> list[dict]:
    out = []
    tiers = df["tier"].to_numpy().astype(int)
    for t in sorted(set(tiers)):
        mask = tiers == t
        s = scores(df["blue_won"].to_numpy()[mask], p[mask])
        out.append({
            "tier": TIER_NAMES[t] if 0 <= t < len(TIER_NAMES) else str(t),
            "tier_index": int(t),
            "games": int(df.loc[mask, "match_id"].nunique()),
            "accuracy": s["accuracy"],
            "log_loss": s["log_loss"],
        })  # fmt: skip
    return out


def evaluate(df: pd.DataFrame, p: np.ndarray) -> dict:
    return {
        "overall": scores(df["blue_won"].to_numpy(), p),
        "by_minute": by_minute(df, p),
        "by_tier": by_tier(df, p),
    }


def calibration_table(y: np.ndarray, p: np.ndarray) -> tuple[list[dict], float]:
    idx = np.minimum((p * 10).astype(int), 9)
    table = []
    gap = 0.0
    for b in range(10):
        mask = idx == b
        if not mask.any():
            continue
        pred, act = float(p[mask].mean()), float(y[mask].mean())
        table.append({"bin": b, "predicted": pred, "actual": act, "count": int(mask.sum())})
        if mask.sum() >= CALIBRATION_MIN_COUNT:
            gap = max(gap, abs(pred - act) * 100)
    return table, float(gap)


# ---------------------------------------------------------------- models


def fit_baseline(train: pd.DataFrame, cols: list[str]):
    numeric = [c for c in cols if c not in CATEGORICAL]
    pre = ColumnTransformer([
        ("num", StandardScaler(), numeric),
        ("cat", OneHotEncoder(categories=[SOUL_TYPES], handle_unknown="ignore"), CATEGORICAL),
    ])  # fmt: skip
    model = make_pipeline(pre, LogisticRegression(max_iter=1000))
    model.fit(train[cols], train["blue_won"])
    return model


def game_weights(df: pd.DataFrame) -> np.ndarray:
    return (1.0 / df.groupby("match_id")["match_id"].transform("size")).to_numpy()


def fit_lightgbm(train, val, cols: list[str], weight: str, seed: int, setting: dict) -> lgb.Booster:
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": 0.05,
        "monotone_constraints": [MONOTONE[c] for c in cols],
        "seed": seed,
        "verbose": -1,
        **setting,
    }
    w_tr = game_weights(train) if weight == "game" else None
    w_va = game_weights(val) if weight == "game" else None
    dtrain = lgb.Dataset(train[cols], train["blue_won"], weight=w_tr,
                         categorical_feature=CATEGORICAL)  # fmt: skip
    dval = lgb.Dataset(val[cols], val["blue_won"], weight=w_va, reference=dtrain)
    return lgb.train(
        params, dtrain, num_boost_round=3000, valid_sets=[dval], valid_names=["validation"],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)],
    )  # fmt: skip


def predict(booster: lgb.Booster, df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return booster.predict(df[cols], num_iteration=booster.best_iteration)


def tune_lightgbm(train, val, cols: list[str], grid: list[dict], weight: str, seed: int):
    """Fit each setting; return the booster and setting with the best validation log loss, and
    one row per setting tried."""
    best = None
    tried = []
    for setting in grid:
        log(f"== LightGBM {setting} (weight={weight})")
        booster = fit_lightgbm(train, val, cols, weight, seed, setting)
        ll = float(log_loss(val["blue_won"], predict(booster, val, cols), labels=[0, 1]))
        tried.append({"setting": setting, "val_log_loss": ll, "rounds": booster.best_iteration})
        log(f"validation log loss {ll:.4f} after {booster.best_iteration} rounds")
        if best is None or ll < best[0]:
            best = (ll, booster, setting)
    for row in tried:
        row["kept"] = row["setting"] is best[2]
    return best[1], best[2], tried


def compare_feature_sets(train, val, test, p_test: np.ndarray, weight: str, seed: int,
                         setting: dict) -> dict:  # fmt: skip
    """Version 1's features with the same games and setting: what the newer features add.
    `p_test` is the newer model's test prediction, before any isotonic calibration."""
    log("== the same LightGBM on version 1 features, for comparison")
    old = fit_lightgbm(train, val, V1_COLUMNS, weight, seed, setting)
    p_old = predict(old, test, V1_COLUMNS)
    y = test["blue_won"].to_numpy()
    minutes = [
        {"bucket": o["bucket"], "rows": o["rows"], "v1_log_loss": o["log_loss"],
         "log_loss": n["log_loss"], "v1_accuracy": o["accuracy"], "accuracy": n["accuracy"]}
        for o, n in zip(by_minute(test, p_old), by_minute(test, p_test), strict=True)
    ]  # fmt: skip
    situations = []
    for name, rule in SITUATIONS:
        mask = rule(test).to_numpy()
        if mask.any():
            situations.append({
                "situation": name, "rows": int(mask.sum()),
                "games": int(test.loc[mask, "match_id"].nunique()),
                "v1_log_loss": float(log_loss(y[mask], p_old[mask], labels=[0, 1])),
                "log_loss": float(log_loss(y[mask], p_test[mask], labels=[0, 1])),
            })  # fmt: skip
    result = {"v1": scores(y, p_old), "new": scores(y, p_test), "by_minute": minutes,
              "situations": situations}  # fmt: skip
    log(f"version 1 features: {result['v1']}")
    log(f"newer features:     {result['new']}")
    return result


def feature_effects(booster: lgb.Booster, test: pd.DataFrame, cols: list[str],
                    max_rows: int = 200_000) -> list[dict]:  # fmt: skip
    """For each position or vision feature, on test rows where it isn't 0: the win chance with its
    real value minus the win chance with it set to 0, signed so that positive means it helps the
    team with more of it (more players at the pit, more split pushers, more wards)."""
    rows = test if len(test) <= max_rows else test.sample(max_rows, random_state=0)
    out = []
    for f in (f for f in EFFECT_FEATURES if f in cols):
        sub = rows.loc[(rows[f] != 0).to_numpy(), cols]
        if sub.empty:
            continue
        diff = predict(booster, sub, cols) - predict(booster, sub.assign(**{f: 0}), cols)
        signed = diff * np.sign(sub[f].to_numpy())
        out.append({"feature": f, "rows": len(sub), "effect_pts": float(signed.mean() * 100),
                    "size_pts": float(np.abs(diff).mean() * 100)})  # fmt: skip
    return out


def fit_isotonic(y: np.ndarray, p: np.ndarray) -> IsotonicRegression:
    return IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(p, y)


def apply_isotonic(x: list[float], y: list[float], p: np.ndarray) -> np.ndarray:
    return np.interp(p, x, y)


# ---------------------------------------------------------------- outputs


def plot_calibration(table: list[dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="perfect")
    ax.plot([r["predicted"] for r in table], [r["actual"] for r in table], "o-", label="LightGBM")
    ax.set_xlabel("predicted win chance")
    ax.set_ylabel("actual win rate")
    ax.set_title("Calibration (test set)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_accuracy_by_minute(models: dict, path: Path, comparison: dict | None = None) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for name, style in (("lightgbm", "-"), ("baseline", "--")):
        rows = models[name]["by_minute"]
        ax.plot([r["bucket"] for r in rows], [r["accuracy"] for r in rows], style, marker="o",
                label=name)  # fmt: skip
    if comparison:
        rows = comparison["by_minute"]
        ax.plot([r["bucket"] for r in rows], [r["v1_accuracy"] for r in rows], ":", marker="o",
                label="lightgbm, version 1 features")  # fmt: skip
    ax.set_xlabel("minute")
    ax.set_ylabel("accuracy")
    ax.set_title("Accuracy by minute (test set)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def fit_tier_models(train, val, test, p_test: np.ndarray, args, out: Path, cols: list[str],
                    setting: dict) -> list[dict]:  # fmt: skip
    """One model per rank with enough games. A rank's model is saved to tiers/<RANK>/ only when
    it beats the overall model on that rank's test games, so the app can always prefer it."""
    tiers_dir = out / "tiers"
    shutil.rmtree(tiers_dir, ignore_errors=True)  # never leave rank models from an earlier run
    results = []
    for t in sorted(set(train["tier"].astype(int))):
        name = (TIER_NAMES[t] if 0 <= t < len(TIER_NAMES) else str(t)).upper()
        tr, va, te = (d[d["tier"] == t] for d in (train, val, test))
        n = int(tr["match_id"].nunique())
        row = {"tier": name, "train_games": n, "saved": False}
        if n < MIN_TIER_GAMES or va.empty or te.empty:
            results.append(row)
            continue
        log(f"== {name}: own model on {n} games")
        booster = fit_lightgbm(tr, va, cols, args.weight, args.seed, setting)
        p_own = predict(booster, te, cols)
        y = te["blue_won"]
        own = scores(y.to_numpy(), p_own)
        overall = scores(y.to_numpy(), p_test[(test["tier"] == t).to_numpy()])
        row.update(log_loss=own["log_loss"], overall_log_loss=overall["log_loss"],
                   accuracy=own["accuracy"], overall_accuracy=overall["accuracy"])  # fmt: skip
        if own["log_loss"] < overall["log_loss"]:
            d = tiers_dir / name
            d.mkdir(parents=True)
            booster.save_model(str(d / "model.txt"), num_iteration=booster.best_iteration)
            info = {"trained_at": datetime.now(UTC).isoformat(timespec="seconds"), "tier": name,
                    "games": n, "patches": sorted(tr["patch"].unique()), "isotonic": False,
                    "test": own}  # fmt: skip
            (d / "metrics.json").write_text(json.dumps(info, indent=2))
            row["saved"] = True
        log(f"{name}: log loss {own['log_loss']:.4f} own vs {overall['log_loss']:.4f} overall"
            f" -> {'saved' if row['saved'] else 'overall is better'}")  # fmt: skip
        results.append(row)
    return results


def md_table(headers: list[str], rows: list[list]) -> str:
    def fmt(v):
        return f"{v:.4f}" if isinstance(v, float) else str(v)

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(fmt(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


def write_report(m: dict, val_ll: float, path: Path) -> None:
    out = [
        "# Training report",
        "",
        f"Trained {m['trained_at']} on {m['games']} games ({m['rows']} rows), patches "
        f"{', '.join(m['patches'])}, features version {m['features_version']}.",
        f"Split (games): {m['split']}. Weighting: {m['weighting']}. Isotonic: {m['isotonic']}.",
        f"LightGBM validation log loss: {val_ll:.4f}.",
        "",
        "## Overall (test set)",
        "",
        md_table(["model", "accuracy", "log loss", "brier"],
                 [[n, *m["models"][n]["overall"].values()] for n in ("lightgbm", "baseline")]),
    ]  # fmt: skip
    for n in ("lightgbm", "baseline"):
        mm = m["models"][n]
        out += ["", f"## {n}: by minute", "",
                md_table(["minute", "accuracy", "log loss", "brier", "rows"],
                         [[r["bucket"], r["accuracy"], r["log_loss"], r["brier"], r["rows"]]
                          for r in mm["by_minute"]])]  # fmt: skip
        out += ["", f"## {n}: by tier", "",
                md_table(["tier", "games", "accuracy", "log loss"],
                         [[r["tier"], r["games"], r["accuracy"], r["log_loss"]]
                          for r in mm["by_tier"]])]  # fmt: skip
    out += ["", f"## Rank models (own model needs {MIN_TIER_GAMES} training games; saved if it"
            " beats the overall model on that rank's test games)", "",
            md_table(["rank", "train games", "own log loss", "overall log loss", "saved"],
                     [[r["tier"], r["train_games"], r.get("log_loss", "-"),
                       r.get("overall_log_loss", "-"), "yes" if r["saved"] else "no"]
                      for r in m["tier_models"]])]  # fmt: skip
    out += ["", "## Calibration (LightGBM)", "",
            md_table(["bin", "predicted", "actual", "count"],
                     [[r["bin"], r["predicted"], r["actual"], r["count"]]
                      for r in m["calibration"]]),
            "", f"Max calibration gap: {m['max_calibration_gap_pts']:.2f} points.",
            "", "## Feature importance (gain)", "",
            md_table(["feature", "gain"],
                     [[r["feature"], r["gain"]] for r in m["feature_importance"]])]  # fmt: skip
    c = m.get("feature_set_comparison")
    if c:
        out += ["", f"## Features version {m['features_version']} against version 1", "",
                "Same games, split and LightGBM setting, both without isotonic calibration. Lower"
                " log loss is better.", "",
                md_table(["features", "accuracy", "log loss", "brier"],
                         [["version 1", *c["v1"].values()],
                          [f"version {m['features_version']}", *c["new"].values()]]),
                "", "### By minute", "",
                md_table(["minute", "v1 log loss", "log loss", "rows"],
                         [[r["bucket"], r["v1_log_loss"], r["log_loss"], r["rows"]]
                          for r in c["by_minute"]]),
                "", "### Situations", "",
                md_table(["situation", "rows", "games", "v1 log loss", "log loss"],
                         [[r["situation"], r["rows"], r["games"], r["v1_log_loss"], r["log_loss"]]
                          for r in c["situations"]])]  # fmt: skip
    if m.get("feature_effects"):
        out += ["", "## What positions and vision are worth", "",
                "Test rows where the feature isn't 0: the LightGBM win chance with the real value"
                " minus the win chance with it set to 0, for the team with more of it (more"
                " players near the pit, more split pushers, a bigger group, more wards). It shows"
                " what the model learned, not what causes wins.", "",
                md_table(["feature", "rows", "average change (pts)", "average size (pts)"],
                         [[r["feature"], r["rows"], f"{r['effect_pts']:+.2f}",
                           f"{r['size_pts']:.2f}"] for r in m["feature_effects"]])]  # fmt: skip
    out += ["", "## LightGBM settings tried", "",
            md_table(["setting", "validation log loss", "rounds", "kept"],
                     [[json.dumps(r["setting"]), r["val_log_loss"], r["rounds"],
                       "yes" if r["kept"] else "no"] for r in m["tuning"]]),
            ""]  # fmt: skip
    path.write_text("\n".join(out))


# ---------------------------------------------------------------- main


def default_data_dir() -> Path:
    root = Path("/kaggle/input")
    dirs = sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []
    if not dirs:
        raise SystemExit("no --data given and nothing under /kaggle/input")
    return dirs[0]


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Train the win-chance model.")
    ap.add_argument("--data", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--patches", default="", help="comma separated, e.g. 26.18,26.19 (default: all)"
    )
    ap.add_argument(
        "--features-version", type=int, default=0,
        help=f"default: the newest with {MIN_VERSION_GAMES} games, else the one with the most",
    )  # fmt: skip
    ap.add_argument("--weight", choices=["none", "game"], default="none")
    ap.add_argument("--isotonic", action="store_true")
    ap.add_argument("--no-tune", action="store_true", help="only the first LightGBM setting")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-rows", type=int)
    # Kaggle runs the file inside a notebook kernel that may add its own flags
    args, _ = ap.parse_known_args(argv)
    data = args.data or default_data_dir()
    out = args.out or Path("/kaggle/working")
    out.mkdir(parents=True, exist_ok=True)
    patches = [p.strip() for p in args.patches.split(",") if p.strip()]

    log(f"== loading {data}")
    df = load_data(data, patches, args.features_version, args.max_rows, args.seed)
    version = int(df["features_version"].iloc[0])
    cols = COLUMNS_BY_VERSION[version]
    games = int(df["match_id"].nunique())
    used_patches = sorted(df["patch"].unique())
    log(f"{games} games, {len(df)} rows, patches {used_patches}, features version {version}")

    log("== splitting by match_id (70/10/20)")
    train, val, test = split_by_match(df, args.seed)
    split = {k: int(d["match_id"].nunique()) for k, d in
             (("train", train), ("validation", val), ("test", test))}  # fmt: skip
    log(f"games per split: {split}")

    log("== baseline: logistic regression")
    baseline = fit_baseline(train, cols)
    p_base = baseline.predict_proba(test[cols])[:, 1]
    base_val_ll = log_loss(val["blue_won"], baseline.predict_proba(val[cols])[:, 1])
    log(f"baseline validation log loss: {base_val_ll:.4f}")

    grid = PARAM_GRID[:1] if args.no_tune else PARAM_GRID
    booster, setting, tuning = tune_lightgbm(train, val, cols, grid, args.weight, args.seed)
    p_val = predict(booster, val, cols)
    p_test = predict(booster, test, cols)
    p_test_raw = p_test
    val_ll = float(log_loss(val["blue_won"], p_val, labels=[0, 1]))
    log(f"LightGBM validation log loss (weight={args.weight}, {setting}): {val_ll:.4f}")
    booster.save_model(str(out / "model.txt"), num_iteration=booster.best_iteration)

    iso_path = out / "isotonic.json"
    if not args.isotonic:
        iso_path.unlink(missing_ok=True)  # never leave a calibration from an earlier run
    else:
        log("== isotonic calibration on validation predictions")
        iso = fit_isotonic(val["blue_won"].to_numpy(), p_val)
        xs, ys = iso.X_thresholds_.tolist(), iso.y_thresholds_.tolist()
        iso_path.write_text(json.dumps({"x": xs, "y": ys}))
        p_test = apply_isotonic(xs, ys, p_test)

    log("== evaluating on the test set")
    models = {"lightgbm": evaluate(test, p_test), "baseline": evaluate(test, p_base)}
    for n, mm in models.items():
        log(f"{n}: {mm['overall']}")
    calibration, gap = calibration_table(test["blue_won"].to_numpy(), p_test)
    log(f"max calibration gap: {gap:.2f} points")

    tier_models = fit_tier_models(train, val, test, p_test, args, out, cols, setting)

    comparison, effects = None, []
    if version > 1:
        comparison = compare_feature_sets(train, val, test, p_test_raw, args.weight, args.seed,
                                          setting)  # fmt: skip
        effects = feature_effects(booster, test, cols)
        for r in effects:
            log(
                f"{r['feature']}: {r['effect_pts']:+.2f} pts, size {r['size_pts']:.2f}, "
                f"on {r['rows']} rows"
            )

    gains = booster.feature_importance(importance_type="gain")
    importance = sorted(
        ({"feature": f, "gain": float(g)} for f, g in zip(cols, gains, strict=True)),
        key=lambda r: -r["gain"],
    )
    log("top features: " + ", ".join(f"{r['feature']}={r['gain']:.0f}" for r in importance[:8]))

    metrics = {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "games": games,
        "rows": int(len(df)),
        "patches": used_patches,
        "features_version": version,
        "features": cols,
        "split": split,
        "models": models,
        "calibration": calibration,
        "max_calibration_gap_pts": gap,
        "feature_importance": importance,
        "isotonic": bool(args.isotonic),
        "weighting": args.weight,
        "setting": setting,
        "tuning": tuning,
        "feature_set_comparison": comparison,
        "feature_effects": effects,
        "tier_models": tier_models,
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    plot_calibration(calibration, out / "calibration.png")
    plot_accuracy_by_minute(models, out / "accuracy_by_minute.png", comparison)
    write_report(metrics, val_ll, out / "report.md")
    log(f"== done, wrote model.txt, metrics.json, report.md and plots to {out}")
    return metrics


if __name__ == "__main__":
    main(sys.argv[1:])
