import json
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path

from lolreview.config import ROOT, load_config

RANK_TTL_S = 3600.0
MATCH_IDS_TTL_S = 300.0
ACCOUNT_TTL_S = 86400.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    stored_at REAL NOT NULL,
    PRIMARY KEY (kind, key)
)
"""


def default_path() -> Path:
    p = Path(load_config()["paths"]["cache_db"])
    return p if p.is_absolute() else ROOT / p


class Cache:
    """SQLite store of everything the review app fetches or computes.

    One table of (kind, key) -> JSON; the typed methods below pick the kind and key shape.
    """

    def __init__(self, path: str | Path | None = None, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._lock = threading.Lock()
        target = Path(path) if path is not None else default_path()
        self._db = sqlite3.connect(str(target), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def get(self, kind: str, key: str, max_age_s: float | None = None):
        with self._lock:
            row = self._db.execute(
                "SELECT value, stored_at FROM entries WHERE kind = ? AND key = ?", (kind, key)
            ).fetchone()
        if row is None:
            return None
        if max_age_s is not None and self._clock() - row[1] > max_age_s:
            return None
        return json.loads(row[0])

    def put(self, kind: str, key: str, value) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO entries (kind, key, value, stored_at) VALUES (?, ?, ?, ?)",
                (kind, key, json.dumps(value, separators=(",", ":")), self._clock()),
            )
            self._db.commit()

    def has(self, kind: str, key: str) -> bool:
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM entries WHERE kind = ? AND key = ?", (kind, key)
            ).fetchone()
        return row is not None

    # raw Riot data, kept forever
    def get_match(self, match_id: str) -> dict | None:
        return self.get("match", match_id)

    def put_match(self, match_id: str, match: dict) -> None:
        self.put("match", match_id, match)

    def get_timeline(self, match_id: str) -> dict | None:
        return self.get("timeline", match_id)

    def put_timeline(self, match_id: str, timeline: dict) -> None:
        self.put("timeline", match_id, timeline)

    # one participant's row of the games list
    def get_summary(self, match_id: str, puuid: str) -> dict | None:
        return self.get("summary", f"{match_id}|{puuid}")

    def put_summary(self, match_id: str, puuid: str, summary: dict) -> None:
        self.put("summary", f"{match_id}|{puuid}", summary)

    # account lookups and match-id pages expire so a player's new games show up
    def get_account(self, cluster: str, name: str, tag: str) -> dict | None:
        return self.get("account", f"{cluster}|{name.lower()}|{tag.lower()}", ACCOUNT_TTL_S)

    def put_account(self, cluster: str, name: str, tag: str, account: dict) -> None:
        self.put("account", f"{cluster}|{name.lower()}|{tag.lower()}", account)

    def get_match_ids(self, puuid: str, start: int, count: int) -> list[str] | None:
        return self.get("match_ids", f"{puuid}|{start}|{count}", MATCH_IDS_TTL_S)

    def put_match_ids(self, puuid: str, start: int, count: int, ids: list[str]) -> None:
        self.put("match_ids", f"{puuid}|{start}|{count}", ids)

    # rank entries; "none" is stored as {"entry": None} so unranked players are cached too
    def get_rank(self, platform: str, puuid: str) -> dict | None:
        return self.get("rank", f"{platform}|{puuid}", RANK_TTL_S)

    def put_rank(self, platform: str, puuid: str, entry: dict | None) -> None:
        self.put("rank", f"{platform}|{puuid}", {"entry": entry})

    # Data Dragon files
    def get_ddragon(self, name: str, max_age_s: float | None = None):
        return self.get("ddragon", name, max_age_s)

    def put_ddragon(self, name: str, data) -> None:
        self.put("ddragon", name, data)

    # computed reviews
    @staticmethod
    def _review_key(match_id: str, participant_id: int, model_version: str) -> str:
        return f"{match_id}|{participant_id}|{model_version}"

    def get_review(self, match_id: str, participant_id: int, model_version: str) -> dict | None:
        return self.get("review", self._review_key(match_id, participant_id, model_version))

    def has_review(self, match_id: str, participant_id: int, model_version: str) -> bool:
        return self.has("review", self._review_key(match_id, participant_id, model_version))

    def put_review(
        self, match_id: str, participant_id: int, model_version: str, review: dict
    ) -> None:
        self.put("review", self._review_key(match_id, participant_id, model_version), review)
