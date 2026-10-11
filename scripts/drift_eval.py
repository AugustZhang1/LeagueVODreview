"""Score the model on a newer patch and on another rank than it was trained on.

    python scripts/drift_eval.py --data data [--features-version 3] [--seed 42] [--max-rows N]
                                 [--out drift.json]

Two experiments, each one LightGBM fit with the first setting of the grid (no tuning):
- Unseen patch: train on every patch but the newest; test on held-out games of the older patches
  and on the newest patch.
- Unseen rank: train on Master, Grandmaster and Challenger games; test on held-out games of those
  ranks and on Diamond games.

The columns are the features version's minus the champion columns, so no champion table is
needed and the champion numbers can't leak in. Each platform folder is loaded on its own (the
copies of the data under data/kaggle_* are left out).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
import train as T  # noqa: E402

MIN_GAMES = 200  # a test group or training pool with fewer games is skipped
TOP_RANKS = ["Master", "Grandmaster", "Challenger"]
TITLES = {"unseen_patch": "Unseen patch", "unseen_rank": "Unseen rank"}
METRICS = ["accuracy", "log_loss", "brier", "calibration_gap_pts"]


def load_all(data: Path, features_version: int, max_rows: int | None, seed: int) -> pd.DataFrame:
    """The games of every <platform>/<patch>/v<N> folder. `train.load_data` reads every Parquet
    under the folder it's given, so loading `data` itself would also read the Kaggle copies."""
    platforms = sorted({f.parents[2] for f in data.glob("*/*/v*/*.parquet")})
    if not platforms:
        raise SystemExit(f"no <platform>/<patch>/v<N>/*.parquet files under {data}")
    df = pd.concat(
        [T.load_data(p, [], features_version, None, seed) for p in platforms], ignore_index=True
    )
    if max_rows and len(df) > max_rows:
        ids = df["match_id"].unique().to_numpy()
        np.random.default_rng(seed).shuffle(ids)
        sizes = df.groupby("match_id").size().reindex(ids).to_numpy()
        keep = set(ids[np.cumsum(sizes) <= max_rows])
        df = df[df["match_id"].isin(keep)].reset_index(drop=True)
        T.log(f"--max-rows: kept {len(keep)} games")
    return df


def patch_key(patch: str) -> tuple[int, ...]:
    return tuple(int(x) for x in patch.split("."))


def too_small(groups: dict[str, pd.DataFrame]) -> str:
    """Why these groups can't be used (empty string when all have at least MIN_GAMES games)."""
    short = [f"{name} has {df['match_id'].nunique()} games"
             for name, df in groups.items() if df["match_id"].nunique() < MIN_GAMES]  # fmt: skip
    return f"skipped, {'; '.join(short)} (need {MIN_GAMES} each)" if short else ""


def score(booster, df: pd.DataFrame, cols: list[str]) -> dict:
    y = df["blue_won"].to_numpy()
    p = T.predict(booster, df, cols)
    _, gap = T.calibration_table(y, p)
    return {"games": int(df["match_id"].nunique()), "rows": len(df), **T.scores(y, p),
            "calibration_gap_pts": gap}  # fmt: skip


def unseen_patch(df: pd.DataFrame, cols: list[str], seed: int) -> dict:
    newest = max(df["patch"].unique(), key=patch_key)
    old, new = df[df["patch"] != newest], df[df["patch"] == newest]
    why = too_small({"The older patches": old, "The newest patch": new})
    if why:
        return {"skipped": why}
    train, val, seen = T.split_by_match(old, seed)
    booster = T.fit_lightgbm(train, val, cols, "none", seed, T.PARAM_GRID[0])
    older = ", ".join(sorted(old["patch"].unique(), key=patch_key))
    return {
        "trained_on": older,
        "train_games": int(train["match_id"].nunique()),
        "validation_games": int(val["match_id"].nunique()),
        "best_round": booster.best_iteration,
        "tests": [
            {"name": f"Seen patches ({older})", **score(booster, seen, cols)},
            {"name": f"Unseen patch ({newest})", **score(booster, new, cols)},
        ],
    }


def unseen_rank(df: pd.DataFrame, cols: list[str], seed: int) -> dict:
    tier = df["tier"].astype(int)
    top = df[tier.isin([T.TIER_NAMES.index(r) for r in TOP_RANKS])]
    diamond = df[tier == T.TIER_NAMES.index("Diamond")]
    why = too_small({"Master to Challenger": top, "Diamond": diamond})
    if why:
        return {"skipped": why}
    train, val, held = T.split_by_match(top, seed)
    booster = T.fit_lightgbm(train, val, cols, "none", seed, T.PARAM_GRID[0])
    return {
        "trained_on": ", ".join(TOP_RANKS),
        "train_games": int(train["match_id"].nunique()),
        "validation_games": int(val["match_id"].nunique()),
        "best_round": booster.best_iteration,
        "tests": [
            {"name": "Held-out Master to Challenger", **score(booster, held, cols)},
            {"name": "Diamond", **score(booster, diamond, cols)},
        ],
    }


def print_experiment(title: str, result: dict) -> None:
    print(f"\n## {title}")
    if "skipped" in result:
        print(result["skipped"])
        return
    print(
        f"Trained on {result['trained_on']}: {result['train_games']} games, "
        f"{result['validation_games']} for validation, best round {result['best_round']}."
    )
    a, b = result["tests"]
    rows = [[t["name"], t["games"], t["rows"], *[t[m] for m in METRICS]] for t in (a, b)]
    rows.append(["Difference (second minus first)", "", "", *[b[m] - a[m] for m in METRICS]])
    headers = [
        "Test set",
        "Games",
        "Rows",
        "Accuracy",
        "Log loss",
        "Brier",
        "Calibration gap (pts)",
    ]
    print(T.md_table(headers, rows))


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--features-version", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-rows", type=int)
    ap.add_argument("--out", type=Path, help="also write the numbers as JSON")
    args = ap.parse_args(argv)

    df = load_all(args.data, args.features_version, args.max_rows, args.seed)
    cols = [c for c in T.COLUMNS_BY_VERSION[args.features_version] if c not in T.CHAMPION_FEATURES]
    print(f"{df['match_id'].nunique()} games, {len(df)} rows, features version "
          f"{args.features_version}")  # fmt: skip
    print(
        f"{len(cols)} columns: the version's columns minus the champion columns "
        f"{T.CHAMPION_FEATURES}, which are left out"
    )

    experiments = {
        "unseen_patch": unseen_patch(df, cols, args.seed),
        "unseen_rank": unseen_rank(df, cols, args.seed),
    }
    for key, result in experiments.items():
        print_experiment(TITLES[key], result)

    out = {
        "data": str(args.data),
        "features_version": args.features_version,
        "seed": args.seed,
        "max_rows": args.max_rows,
        "games": int(df["match_id"].nunique()),
        "columns": cols,
        "setting": T.PARAM_GRID[0],
        "experiments": experiments,
    }
    if args.out:
        args.out.write_text(json.dumps(out, indent=2))
        print(f"\nwrote {args.out}")
    return out


if __name__ == "__main__":
    main()
