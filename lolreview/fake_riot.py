"""A Riot client stand-in that serves made-up players and games cloned from the fixtures."""

import copy
import json
import threading
from pathlib import Path

from lolreview.config import ROOT

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "synthetic"
ID_BASE = 1_000_000_000
PLAYER_STRIDE = 5

_fixtures: list[tuple[dict, dict]] | None = None
_fixtures_lock = threading.Lock()


def _load_fixtures() -> list[tuple[dict, dict]]:
    global _fixtures
    with _fixtures_lock:
        if _fixtures is None:
            out = []
            for match_path in sorted(FIXTURE_DIR.glob("*.match.json")):
                timeline_path = Path(str(match_path).replace(".match.json", ".timeline.json"))
                out.append(
                    (
                        json.loads(match_path.read_text(encoding="utf-8")),
                        json.loads(timeline_path.read_text(encoding="utf-8")),
                    )
                )
            _fixtures = out
        return _fixtures


class FakeRiotClient:
    """Same method names and return shapes as RiotClient, deterministic for a given seed.

    Match ids are `<PLATFORM>_<n>`; neighbouring players share some ids, like real
    players who queued together. Game n uses fixture n % 4 and patch patches[n % len].
    """

    def __init__(
        self,
        platform: str = "na1",
        seed: int = 0,
        patches: tuple[str, ...] = ("26.19",),
        apex_size: int = 40,
        entries_per_page: int = 50,
        pages: int = 2,
        matches_per_player: int = 10,
    ):
        self.platform = platform
        self.seed = seed
        self.patches = tuple(patches)
        self.apex_size = apex_size
        self.entries_per_page = entries_per_page
        self.pages = pages
        self.matches_per_player = matches_per_player
        self.key_status = "ok"
        self._lock = threading.Lock()
        self._requests = 0

    def _count(self) -> None:
        with self._lock:
            self._requests += 1

    def stats(self) -> dict:
        with self._lock:
            return {
                "requests": self._requests,
                "rate_limited": 0,
                "server_errors": 0,
                "last_error": None,
                "key_status": self.key_status,
            }

    def _puuid(self, tier: str, division: str, i: int) -> str:
        return f"{self.platform}-{self.seed}-{tier}-{division}-{i}"

    def _entry(self, tier: str, division: str, i: int) -> dict:
        return {
            "puuid": self._puuid(tier, division, i),
            "tier": tier,
            "rank": division,
            "leaguePoints": max(0, 1000 - i),
            "wins": 10 + i,
            "losses": 10,
        }

    def apex_league(self, platform: str, tier: str) -> dict:
        self._count()
        tier = tier.upper()
        entries = [self._entry(tier, "I", i) for i in range(self.apex_size)]
        return {"tier": tier, "queue": "RANKED_SOLO_5x5", "entries": entries}

    def league_entries(self, platform: str, tier: str, division: str, page: int = 1) -> list:
        self._count()
        if page < 1 or page > self.pages:
            return []
        start = (page - 1) * self.entries_per_page
        return [
            self._entry(tier.upper(), division, i)
            for i in range(start, start + self.entries_per_page)
        ]

    def _player_ordinal(self, puuid: str) -> int:
        # Stable across processes (str hash is salted, so don't use it).
        total = self.seed
        for ch in puuid:
            total = (total * 131 + ord(ch)) % 1_000_003
        return total

    def match_ids(
        self,
        cluster: str,
        puuid: str,
        queue: int = 420,
        start_time: int | None = None,
        start: int = 0,
        count: int = 100,
    ) -> list[str]:
        self._count()
        first = ID_BASE + self._player_ordinal(puuid) * PLAYER_STRIDE
        prefix = self.platform.upper()
        ids = [f"{prefix}_{first + j}" for j in range(self.matches_per_player)]
        return ids[start : start + count]

    def _number(self, match_id: str) -> int:
        return int(match_id.rsplit("_", 1)[1])

    def match(self, cluster: str, match_id: str) -> dict:
        self._count()
        n = self._number(match_id)
        fixtures = _load_fixtures()
        match = copy.deepcopy(fixtures[n % len(fixtures)][0])
        match["metadata"]["matchId"] = match_id
        info = match["info"]
        info["platformId"] = match_id.split("_", 1)[0]
        info["gameId"] = n
        build = info["gameVersion"].split(".", 2)[2] if info["gameVersion"].count(".") > 1 else "0"
        info["gameVersion"] = f"{self.patches[n % len(self.patches)]}.{build}"
        return match

    def timeline(self, cluster: str, match_id: str) -> dict:
        self._count()
        n = self._number(match_id)
        fixtures = _load_fixtures()
        timeline = copy.deepcopy(fixtures[n % len(fixtures)][1])
        timeline["metadata"]["matchId"] = match_id
        return timeline
