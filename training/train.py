"""Train the win-chance model (Plan Step 10). One standalone file, meant to run on Kaggle.

    python training/train.py --data DIR --out DIR [--patches 26.18,26.19] [--features-version 1]
                             [--weight none|game] [--isotonic] [--seed 42] [--max-rows N]

With no arguments (Kaggle) it reads the first folder under /kaggle/input and writes to
/kaggle/working. Needs: pandas, numpy, pyarrow, lightgbm, scikit-learn, matplotlib.
"""

from __future__ import annotations

import argparse
import json
import re
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

FEATURE_COLUMNS = [
    "tier", "minute", "gold_diff", "kill_diff", "tower_diff", "level_diff", "cs_diff",
    "grub_diff", "herald_diff", "quest_diff", "inhibs_down_diff", "baron_active",
    "elder_active", "blue_dragons", "red_dragons", "soul_diff", "soul_type",
]  # fmt: skip
CATEGORICAL = ["soul_type"]
MONOTONE = {
    "tier": 0, "minute": 0, "gold_diff": 1, "kill_diff": 1, "tower_diff": 1, "level_diff": 1,
    "cs_diff": 1, "grub_diff": 1, "herald_diff": 1, "quest_diff": 1, "inhibs_down_diff": 1,
    "baron_active": 1, "elder_active": 1, "blue_dragons": 1, "red_dragons": -1, "soul_diff": 1,
    "soul_type": 0,
}  # fmt: skip
SOUL_TYPES = ["none", "Infernal", "Mountain", "Ocean", "Cloud", "Hextech", "Chemtech"]

NUMERIC = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL]
TIER_NAMES = [
    "Iron", "Bronze", "Silver", "Gold", "Platinum", "Emerald", "Diamond", "Master",
    "Grandmaster", "Challenger", "Pro",
]  # fmt: skip
MINUTE_EDGES = [0, 5, 10, 15, 20, 25, 30, 35, 40, np.inf]
MINUTE_LABELS = ["0-5", "5-10", "10-15", "15-20", "20-25", "25-30", "30-35", "35-40", "40+"]
CALIBRATION_MIN_COUNT = 20  # bins with fewer rows are listed but ignored for the max gap


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- data


def load_data(
    data: Path, patches: list[str] | None, features_version: int, max_rows: int | None, seed: int
) -> pd.DataFrame:
    files = sorted(data.rglob("*.parquet"))
    log(f"found {len(files)} parquet files under {data}")
    frames = []
    for f in files:
        m = re.search(
            r"(?:^|[/\\])v(\d+)(?:[/\\])", str(f.relative_to(data)).replace("\\", "/") + "/"
        )
        df = pd.read_parquet(f)
        if "features_version" in df.columns:
            df = df[df["features_version"].astype(int) == features_version]
        elif m and int(m.group(1)) != features_version:
            continue
        if df.empty:
            continue
        df["match_id"] = df["match_id"].astype(str)
        df["patch"] = df["patch"].astype(str)
        if patches:
            df = df[df["patch"].isin(patches)]
        frames.append(df)
    if not frames:
        raise SystemExit("no rows left after the patch / features-version filter")
    df = pd.concat(frames, ignore_index=True)
    for col in FEATURE_COLUMNS:
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


def fit_baseline(train: pd.DataFrame):
    pre = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("cat", OneHotEncoder(categories=[SOUL_TYPES], handle_unknown="ignore"), CATEGORICAL),
    ])  # fmt: skip
    model = make_pipeline(pre, LogisticRegression(max_iter=1000))
    model.fit(train[FEATURE_COLUMNS], train["blue_won"])
    return model


def game_weights(df: pd.DataFrame) -> np.ndarray:
    return (1.0 / df.groupby("match_id")["match_id"].transform("size")).to_numpy()


def fit_lightgbm(train, val, weight: str, seed: int) -> lgb.Booster:
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "monotone_constraints": [MONOTONE[c] for c in FEATURE_COLUMNS],
        "seed": seed,
        "verbose": -1,
    }
    w_tr = game_weights(train) if weight == "game" else None
    w_va = game_weights(val) if weight == "game" else None
    dtrain = lgb.Dataset(train[FEATURE_COLUMNS], train["blue_won"], weight=w_tr,
                         categorical_feature=CATEGORICAL)  # fmt: skip
    dval = lgb.Dataset(val[FEATURE_COLUMNS], val["blue_won"], weight=w_va, reference=dtrain)
    return lgb.train(
        params, dtrain, num_boost_round=3000, valid_sets=[dval], valid_names=["validation"],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)],
    )  # fmt: skip


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


def plot_accuracy_by_minute(models: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for name, style in (("lightgbm", "-"), ("baseline", "--")):
        rows = models[name]["by_minute"]
        ax.plot([r["bucket"] for r in rows], [r["accuracy"] for r in rows], style, marker="o",
                label=name)  # fmt: skip
    ax.set_xlabel("minute")
    ax.set_ylabel("accuracy")
    ax.set_title("Accuracy by minute (test set)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


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
    out += ["", "## Calibration (LightGBM)", "",
            md_table(["bin", "predicted", "actual", "count"],
                     [[r["bin"], r["predicted"], r["actual"], r["count"]]
                      for r in m["calibration"]]),
            "", f"Max calibration gap: {m['max_calibration_gap_pts']:.2f} points.",
            "", "## Feature importance (gain)", "",
            md_table(["feature", "gain"],
                     [[r["feature"], r["gain"]] for r in m["feature_importance"]]),
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
    ap.add_argument("--features-version", type=int, default=1)
    ap.add_argument("--weight", choices=["none", "game"], default="none")
    ap.add_argument("--isotonic", action="store_true")
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
    games = int(df["match_id"].nunique())
    used_patches = sorted(df["patch"].unique())
    log(f"{games} games, {len(df)} rows, patches {used_patches}")

    log("== splitting by match_id (70/10/20)")
    train, val, test = split_by_match(df, args.seed)
    split = {k: int(d["match_id"].nunique()) for k, d in
             (("train", train), ("validation", val), ("test", test))}  # fmt: skip
    log(f"games per split: {split}")

    log("== baseline: logistic regression")
    baseline = fit_baseline(train)
    p_base = baseline.predict_proba(test[FEATURE_COLUMNS])[:, 1]
    base_val_ll = log_loss(val["blue_won"], baseline.predict_proba(val[FEATURE_COLUMNS])[:, 1])
    log(f"baseline validation log loss: {base_val_ll:.4f}")

    log(f"== LightGBM (weight={args.weight})")
    booster = fit_lightgbm(train, val, args.weight, args.seed)
    p_val = booster.predict(val[FEATURE_COLUMNS], num_iteration=booster.best_iteration)
    p_test = booster.predict(test[FEATURE_COLUMNS], num_iteration=booster.best_iteration)
    val_ll = float(log_loss(val["blue_won"], p_val, labels=[0, 1]))
    log(f"LightGBM validation log loss (weight={args.weight}): {val_ll:.4f}")
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

    gains = booster.feature_importance(importance_type="gain")
    importance = sorted(
        ({"feature": f, "gain": float(g)} for f, g in zip(FEATURE_COLUMNS, gains, strict=True)),
        key=lambda r: -r["gain"],
    )
    log("top features: " + ", ".join(f"{r['feature']}={r['gain']:.0f}" for r in importance[:8]))

    metrics = {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "games": games,
        "rows": int(len(df)),
        "patches": used_patches,
        "features_version": args.features_version,
        "features": FEATURE_COLUMNS,
        "split": split,
        "models": models,
        "calibration": calibration,
        "max_calibration_gap_pts": gap,
        "feature_importance": importance,
        "isotonic": bool(args.isotonic),
        "weighting": args.weight,
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    plot_calibration(calibration, out / "calibration.png")
    plot_accuracy_by_minute(models, out / "accuracy_by_minute.png")
    write_report(metrics, val_ll, out / "report.md")
    log(f"== done, wrote model.txt, metrics.json, report.md and plots to {out}")
    return metrics


if __name__ == "__main__":
    main(sys.argv[1:])
