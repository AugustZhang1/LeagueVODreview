"""Write frontend/src/mocks/review.fixture.json from a synthetic game and the placeholder model.

Usage: .venv/bin/python scripts/make_mock_review.py
"""

import json
from pathlib import Path

from lolreview.model import PlaceholderModel
from lolreview.review import build_review

ROOT = Path(__file__).resolve().parent.parent
MATCH_ID = "NA1_9000000001"
PARTICIPANT = 4


def main() -> None:
    folder = ROOT / "tests" / "fixtures" / "synthetic"
    match = json.loads((folder / f"{MATCH_ID}.match.json").read_text(encoding="utf-8"))
    timeline = json.loads((folder / f"{MATCH_ID}.timeline.json").read_text(encoding="utf-8"))
    champions = {
        p["championId"]: (p["championName"], p["championName"])
        for p in match["info"]["participants"]
    }
    review = build_review(
        match, timeline, PARTICIPANT, "GOLD", PlaceholderModel(), champions, "26.19.1"
    )
    out = ROOT / "frontend" / "src" / "mocks" / "review.fixture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(review.model_dump(mode="json", by_alias=True)), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
