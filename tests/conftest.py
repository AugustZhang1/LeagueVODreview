import json
import os
import sys
from pathlib import Path

import pytest

# One OpenMP thread for LightGBM: parallel test runs otherwise oversubscribe the CPUs and crawl.
os.environ.setdefault("OMP_NUM_THREADS", "1")

FIXTURES = Path(__file__).parent / "fixtures"
SYNTHETIC = FIXTURES / "synthetic"
sys.path.insert(0, str(FIXTURES))

SYNTHETIC_IDS = [f"NA1_900000000{i}" for i in range(1, 5)]


def _load(match_id: str, folder: Path = SYNTHETIC) -> tuple[dict, dict]:
    match = json.loads((folder / f"{match_id}.match.json").read_text(encoding="utf-8"))
    timeline = json.loads((folder / f"{match_id}.timeline.json").read_text(encoding="utf-8"))
    return match, timeline


@pytest.fixture(scope="session")
def load_game():
    """load_game(match_id) -> (match, timeline) from the synthetic folder."""
    return _load


@pytest.fixture(scope="session")
def synthetic_games() -> list[tuple[dict, dict]]:
    return [_load(match_id) for match_id in SYNTHETIC_IDS]
