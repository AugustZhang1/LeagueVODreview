"""Report the crawler's dataset: games and rows by platform, patch, rank and features version, the
Parquet size on disk, games stored in more than one file, and each platform's crawl state.

    python scripts/dataset_report.py --data data

Reads `<platform>/<patch>/v<N>/*.parquet` under --data (the copies under data/kaggle_* are not in
that layout, so they're left out) and `state-<platform>.sqlite` in --data, read-only, if present.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
import train as T  # noqa: E402


def rank_name(tier: int) -> str:
    return T.TIER_NAMES[tier] if 0 <= tier < len(T.TIER_NAMES) else str(tier)


def load_rows(data: Path) -> tuple[pd.DataFrame, int]:
    """One row per Parquet row (match_id, tier, platform, patch, version, file) and the files'
    total size in bytes."""
    frames, size = [], 0
    for f in sorted(data.glob("*/*/v*/*.parquet")):
        rel = f.relative_to(data)
        platform, patch, version = rel.parts[:3]
        t = pq.read_table(f, columns=["match_id", "tier"]).to_pandas()
        frames.append(t.assign(
            match_id=t["match_id"].astype(str), tier=t["tier"].astype(int),
            platform=platform, patch=patch, version=int(version[1:]), file=rel.as_posix(),
        ))  # fmt: skip
        size += f.stat().st_size
    if not frames:
        raise SystemExit(f"no <platform>/<patch>/v<N>/*.parquet files under {data}")
    return pd.concat(frames, ignore_index=True), size


def breakdown(rows: pd.DataFrame, key: str, label: str, name=str) -> str:
    grouped = rows.groupby(key)
    games, count = grouped["match_id"].nunique(), grouped.size()
    body = [[name(k), int(games[k]), int(count[k])] for k in games.index]
    return T.md_table([label, "Games", "Rows"], body)


def duplicates(rows: pd.DataFrame) -> tuple[int, int]:
    """Games in more than one file, and the extra copies they make."""
    files = rows.groupby("match_id")["file"].nunique()
    dup = files[files > 1]
    return len(dup), int((dup - 1).sum())


def state_counts(data: Path) -> dict[str, dict[str, int]]:
    """Each platform's matches by status, from its crawl state file (lolreview/state.py)."""
    out = {}
    for path in sorted(data.glob("state-*.sqlite")):
        db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            rows = db.execute("SELECT status, COUNT(*) FROM matches GROUP BY status").fetchall()
        finally:
            db.close()
        out[path.stem.removeprefix("state-")] = {status: int(n) for status, n in rows}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, required=True)
    args = ap.parse_args(argv)

    rows, size = load_rows(args.data)
    print(
        f"{rows['match_id'].nunique()} games, {len(rows)} rows in {rows['file'].nunique()} "
        f"files, {size / 1e6:.1f} MB of Parquet on disk"
    )
    for key, label, name in (
        ("platform", "Platform", str),
        ("patch", "Patch", str),
        ("tier", "Rank", rank_name),
        ("version", "Features version", str),
    ):
        print(f"\n## By {label.lower()}\n")
        print(breakdown(rows, key, label, name))
    games, extra = duplicates(rows)
    print(f"\nGames in more than one file: {games} ({extra} extra copies)")
    states = state_counts(args.data)
    if states:
        print("\n## Crawl state (matches by status)\n")
        for platform, counts in states.items():
            print(f"{platform}: " + ", ".join(f"{s} {n}" for s, n in sorted(counts.items())))


if __name__ == "__main__":
    main()
