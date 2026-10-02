"""Write a fake Parquet dataset in the crawler's layout, for testing training end to end.

    python training/make_synthetic_dataset.py --out data_synth [--games 3000] [--seed 7]

Layout: <out>/<platform>/<patch>/v1/part-00001.parquet. The label depends on the features
(a logistic of gold, kills, towers and objectives plus noise), so a model can learn it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

SOUL_TYPES = ["none", "Infernal", "Mountain", "Ocean", "Cloud", "Hextech", "Chemtech"]
PLATFORMS = ["NA1", "EUW1", "KR"]
PATCHES = ["26.17", "26.18", "26.19"]


def make_game(rng: np.random.Generator, game_id: int, platform: str, patch: str) -> dict:
    tier = int(rng.integers(2, 10))
    duration = int(rng.integers(20, 40)) * 60 + int(rng.integers(0, 60))
    skill = rng.normal()  # latent edge for blue
    n = duration // 60 + 1
    minutes = np.arange(n)
    # a few extra rows between minute frames, like kill/objective rows
    extra = rng.random(n) < 0.4
    t = np.sort(
        np.concatenate([minutes * 60.0, (minutes[extra] * 60.0 + rng.uniform(5, 55, extra.sum()))])
    )
    t = t[t <= duration]
    minute = (t // 60).astype(int)
    frac = minute / max(minute.max(), 1)

    drift = skill * (0.4 + frac)
    gold = drift * 2500 + rng.normal(0, 400, len(t)) * (0.3 + frac)
    kills = np.round(drift * 4 + rng.normal(0, 1.5, len(t))).astype(int)
    towers = np.round(np.clip(drift * 1.5 * frac * 3 + rng.normal(0, 0.7, len(t)), -11, 11))
    level = np.round(drift * 1.2 + rng.normal(0, 0.5, len(t)))
    cs = np.round(drift * 25 + rng.normal(0, 8, len(t)))
    grub = np.round(np.clip(drift * 0.6 + rng.normal(0, 0.8, len(t)), -3, 3))
    herald = np.clip(np.round(drift * 0.3 + rng.normal(0, 0.5, len(t))), -1, 1)
    atakhan = np.clip(np.round(drift * 0.2 + rng.normal(0, 0.4, len(t))), -1, 1)
    inhibs = np.where(frac > 0.6, np.clip(np.round(drift * 0.8), -3, 3), 0)
    baron = np.where(
        frac > 0.6, np.clip(np.round(drift * 0.7 + rng.normal(0, 0.5, len(t))), -1, 1), 0
    )
    elder = np.where(frac > 0.85, np.clip(np.round(drift * 0.5), -1, 1), 0)
    blue_d = np.clip(np.round(2 + drift * 0.8 * frac * 2 + rng.normal(0, 0.6, len(t))), 0, 4)
    red_d = np.clip(np.round(2 - drift * 0.8 * frac * 2 + rng.normal(0, 0.6, len(t))), 0, 4)
    blue_d = np.maximum.accumulate(blue_d)
    red_d = np.maximum.accumulate(red_d)
    soul = np.where(blue_d >= 4, 1, np.where(red_d >= 4, -1, 0))
    soul_type = np.where(blue_d + red_d >= 3, rng.choice(SOUL_TYPES[1:]), "none")

    logit = (
        0.0004 * gold
        + 0.05 * kills
        + 0.12 * towers
        + 0.1 * level
        + 0.01 * cs
        + 0.3 * baron
        + 0.4 * elder
        + 0.5 * soul
        + 0.6 * skill
    )
    blue_won = bool(rng.random() < 1 / (1 + np.exp(-logit[-1] * 1.3)))
    n_rows = len(t)
    return {
        "match_id": np.full(n_rows, f"{platform}_{game_id}"),
        "platform": np.full(n_rows, platform),
        "patch": np.full(n_rows, patch),
        "duration_s": np.full(n_rows, duration, dtype=np.int32),
        "t": t.astype(np.float32),
        "blue_won": np.full(n_rows, blue_won),
        "tier": np.full(n_rows, tier, dtype=np.int16),
        "minute": minute.astype(np.int16),
        "gold_diff": gold.astype(np.float32),
        "kill_diff": kills.astype(np.int16),
        "tower_diff": towers.astype(np.int16),
        "level_diff": level.astype(np.float32),
        "cs_diff": cs.astype(np.float32),
        "grub_diff": grub.astype(np.int16),
        "herald_diff": herald.astype(np.int16),
        "atakhan_diff": atakhan.astype(np.int16),
        "inhibs_down_diff": inhibs.astype(np.int16),
        "baron_active": baron.astype(np.int16),
        "elder_active": elder.astype(np.int16),
        "blue_dragons": blue_d.astype(np.int16),
        "red_dragons": red_d.astype(np.int16),
        "soul_diff": soul.astype(np.int16),
        "soul_type": soul_type,
    }


def make_dataset(out: Path, games: int = 3000, seed: int = 7, games_per_file: int = 500) -> int:
    """Write the dataset and return the number of rows."""
    rng = np.random.default_rng(seed)
    groups: dict[tuple[str, str], list[dict]] = {}
    for g in range(games):
        key = (PLATFORMS[g % len(PLATFORMS)], PATCHES[(g // len(PLATFORMS)) % len(PATCHES)])
        groups.setdefault(key, []).append(make_game(rng, g, *key))
    total = 0
    for (platform, patch), items in groups.items():
        folder = out / platform / patch / "v1"
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(0, len(items), games_per_file):
            chunk = items[i : i + games_per_file]
            cols = {k: np.concatenate([c[k] for c in chunk]) for k in chunk[0]}
            table = pa.table(cols)
            pq.write_table(table, folder / f"part-{i // games_per_file + 1:05d}.parquet")
            total += table.num_rows
    return total


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--games", type=int, default=3000)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args(argv)
    rows = make_dataset(args.out, args.games, args.seed)
    print(f"wrote {args.games} games, {rows} rows to {args.out}")


if __name__ == "__main__":
    main()
