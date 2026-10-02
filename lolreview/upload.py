"""Upload the recent crawl batches to a private Kaggle dataset (Plan.md Step 9)."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

from lolreview.config import ROOT, load_config, read_env

DEFAULT_DATASET = "augustzhang1/lol-winprob"
UPLOAD_DIRNAME = ".upload"
TITLE = "lol-winprob"


class UploadError(RuntimeError):
    pass


def _patch_key(patch: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", patch))


def _batch_files(data_dir: Path) -> dict[str, list[Path]]:
    """Map patch -> batch Parquet files, across platforms and feature versions."""
    out: dict[str, list[Path]] = {}
    for platform in sorted(data_dir.iterdir()):
        if not platform.is_dir() or platform.name.startswith("."):
            continue
        for patch in platform.iterdir():
            if patch.is_dir():
                out.setdefault(patch.name, []).extend(sorted(patch.rglob("*.parquet")))
    return out


def recent_patches(data_dir: Path, keep: int) -> dict[str, list[Path]]:
    by_patch = _batch_files(data_dir)
    newest = sorted(by_patch, key=_patch_key)[-keep:]
    return {p: by_patch[p] for p in newest}


def count_games(path: Path) -> int:
    """Games in one batch file, read from Parquet metadata or a single column."""
    pf = pq.ParquetFile(path)
    meta = pf.schema_arrow.metadata or {}
    if b"games" in meta:
        return int(meta[b"games"])
    if "match_id" in pf.schema_arrow.names:
        ids: set[str] = set()
        for i in range(pf.num_row_groups):
            ids.update(pf.read_row_group(i, columns=["match_id"]).column(0).to_pylist())
        return len(ids)
    return 0


def build_upload_dir(data_dir: Path, patches: dict[str, list[Path]], dataset_id: str) -> Path:
    """Hard-link the chosen batch files into <data_dir>/.upload, keeping their relative paths."""
    up = data_dir / UPLOAD_DIRNAME
    if up.exists():
        shutil.rmtree(up)
    up.mkdir(parents=True)
    for files in patches.values():
        for f in files:
            dest = up / f.relative_to(data_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.hardlink_to(f)
    (up / "dataset-metadata.json").write_text(
        json.dumps(
            {
                "title": TITLE,
                "id": dataset_id,
                "licenses": [{"name": "other"}],
                "isPrivate": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return up


def _redact(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def _kaggle(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["kaggle", *args], env=env, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise UploadError("kaggle CLI not found. Install it with: pip install -e '.[vm]'") from e


def run_upload(
    data_dir: Path, dataset_id: str, dry_run: bool = False, env_file: Path | None = None
) -> dict:
    cfg = load_config()
    keep = int(cfg["crawl"]["patches_kept"])
    if not data_dir.is_dir():
        raise UploadError(f"data folder not found: {data_dir}")
    patches = recent_patches(data_dir, keep)
    if not patches:
        raise UploadError(f"no batch files under {data_dir}")
    files = [f for fs in patches.values() for f in fs]
    games = sum(count_games(f) for f in files)
    size = sum(f.stat().st_size for f in files)
    summary = {"games": games, "bytes": size, "patches": sorted(patches, key=_patch_key)}
    print(f"{len(files)} files, {games} games, {size} bytes, patches {summary['patches']}")
    if dry_run:
        print("dry run: nothing built or uploaded")
        return summary

    token = (read_env(env_file) if env_file else read_env()).get("KAGGLE_API_TOKEN", "")
    if not token:
        raise UploadError("KAGGLE_API_TOKEN is missing from .env")
    # Run as .venv/bin/python -m lolreview.upload, the venv's kaggle isn't on PATH yet
    path = os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")])
    if shutil.which("kaggle", path=path) is None:
        raise UploadError("kaggle CLI not found. Install it with: pip install -e '.[vm]'")
    env = {**os.environ, "KAGGLE_API_TOKEN": token, "PATH": path}

    up = build_upload_dir(data_dir, patches, dataset_id)
    exists = _kaggle(["datasets", "status", dataset_id], env).returncode == 0
    if exists:
        cmd = ["datasets", "version", "-p", str(up), "--dir-mode", "zip", "-m", f"{games} games"]
    else:
        cmd = ["datasets", "create", "-p", str(up), "--dir-mode", "zip"]
    print(f"kaggle {'version' if exists else 'create'} {dataset_id}")
    res = _kaggle(cmd, env)
    if res.stdout:
        print(_redact(res.stdout, token).strip())
    if res.returncode != 0:
        raise UploadError(f"kaggle failed ({res.returncode}): {_redact(res.stderr, token).strip()}")

    record = {"uploaded_at": datetime.now(UTC).isoformat(timespec="seconds"), **summary}
    (data_dir / "last_upload.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    default_data = Path(cfg["paths"]["data_dir"])
    if not default_data.is_absolute():
        default_data = ROOT / default_data
    ap = argparse.ArgumentParser(description="Upload recent batches to a private Kaggle dataset")
    ap.add_argument("--data", type=Path, default=default_data)
    ap.add_argument("--dataset-id", default=DEFAULT_DATASET)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        run_upload(args.data, args.dataset_id, args.dry_run)
    except UploadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
