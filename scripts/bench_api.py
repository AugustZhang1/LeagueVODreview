"""Time the review API on the demo games: cold and warm /api/review, warm /api/player.

    python scripts/bench_api.py [--runs 20]

Runs in-process with FastAPI's TestClient on the synthetic demo games and a temporary cache, so
there's no Riot key and no network. The numbers include the app's own work (review build, JSON,
gzip) but not the trip to Riot.
"""

import argparse
import math
import statistics
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from lolreview import demo
from lolreview.api import create_app
from lolreview.cache import Cache


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def timed(client: TestClient, url: str) -> tuple[int, float]:
    start = time.perf_counter()
    r = client.get(url)
    return r.status_code, (time.perf_counter() - start) * 1000


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=20, help="warm calls per game, and for the player")
    args = ap.parse_args()

    demo_riot = demo.DemoRiot()
    match_ids = demo_riot.match_ids("americas", demo_riot.puuid)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cache = Cache(Path(tmp) / "bench.db")
        client = TestClient(
            create_app(demo=True, cache=cache, client=demo_riot), raise_server_exceptions=False
        )
        client.get("/api/health")  # load the model and data before anything is timed

        cold, warm, skipped = [], [], 0
        for match_id in match_ids:
            people = demo_riot.match("americas", match_id)["info"]["participants"]
            p = next(x["participantId"] for x in people if x["puuid"] == demo_riot.puuid)
            url = f"/api/review/{match_id}?p={p}"
            status, ms = timed(client, url)
            if status != 200:  # remakes are not reviewable
                skipped += 1
                continue
            cold.append(ms)
            warm += [timed(client, url)[1] for _ in range(args.runs)]

        player_url = "/api/player/na1/Me/NA1"
        client.get(player_url)  # fill the caches so the timed calls are warm
        player = [timed(client, player_url)[1] for _ in range(args.runs)]
        cache.close()

    print(f"Demo games: {len(cold)} reviewed, {skipped} skipped (not reviewable)")
    print()
    print("| Endpoint | Calls | p50 ms | p95 ms | max ms |")
    print("|---|---:|---:|---:|---:|")
    for name, times in [
        ("/api/review cold", cold),
        ("/api/review warm", warm),
        ("/api/player warm", player),
    ]:
        p50 = statistics.median(times)
        print(
            f"| {name} | {len(times)} | {p50:.1f} | {percentile(times, 0.95):.1f} | "
            f"{max(times):.1f} |"
        )


if __name__ == "__main__":
    main()
