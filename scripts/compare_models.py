"""Compare two trained models on the same games: the test split a training run on --data made.

    python scripts/compare_models.py --data data --new data/out_v3 [--current models]
                                     [--features-version 3]

The current model never saw these games (they were crawled after it was trained), so this is a
fair comparison; the numbers in a run's report.md are on other games and aren't.
"""

import argparse
import json
import sys
from pathlib import Path

import lightgbm as lgb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
import train as T  # noqa: E402


def predictions(model_dir: Path, test):
    booster = lgb.Booster(model_file=str(model_dir / "model.txt"))
    cols = booster.feature_name()
    if any(c in T.CHAMPION_FEATURES for c in cols):
        table = json.loads((model_dir / "champions.json").read_text())
        test = T.add_champion_features(test, table)
    return T.predict(booster, test, cols), cols


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--new", type=Path, required=True, help="the new run's output folder")
    ap.add_argument("--current", type=Path, default=ROOT / "models")
    ap.add_argument("--features-version", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = T.load_data(args.data, [], args.features_version, None, args.seed)
    _, _, test = T.split_by_match(df, args.seed)
    y = test["blue_won"].to_numpy()
    print(f"{test['match_id'].nunique()} test games, {len(test)} rows")
    results = {}
    for name, d in (("current", args.current), ("new", args.new)):
        p, cols = predictions(d, test)
        s = T.scores(y, p)
        _, gap = T.calibration_table(y, p)
        results[name] = (s, gap, T.by_minute(test, p))
        print(
            f"{name:8} {len(cols)} features: accuracy {s['accuracy']:.4f}, "
            f"log loss {s['log_loss']:.4f}, brier {s['brier']:.4f}, calibration gap {gap:.2f} pts"
        )
    print("log loss by minute (current / new):")
    for a, b in zip(results["current"][2], results["new"][2], strict=True):
        print(f"  {a['bucket']:6} {a['log_loss']:.4f} / {b['log_loss']:.4f}  ({a['rows']} rows)")
    better = results["new"][0]["log_loss"] < results["current"][0]["log_loss"]
    print("new model is better (lower log loss)" if better else "current model is better or equal")


if __name__ == "__main__":
    main()
