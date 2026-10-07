"""Per-platform crawl state in SQLite."""

import sqlite3
import time
from pathlib import Path

ERRORS_KEPT = 50

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    puuid TEXT PRIMARY KEY, tier TEXT, division TEXT, crawled_at REAL, pass_no INTEGER
);
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY, tier TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'done', 'skipped', 'failed')),
    added_at REAL
);
CREATE INDEX IF NOT EXISTS matches_status ON matches (status, added_at);
CREATE TABLE IF NOT EXISTS batches (
    file TEXT PRIMARY KEY, patch TEXT, version INTEGER, games INTEGER, rows INTEGER,
    written_at REAL, bytes INTEGER DEFAULT 0, blue_wins INTEGER DEFAULT 0,
    duration_s INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS counters (
    minute INTEGER PRIMARY KEY, requests INTEGER DEFAULT 0,
    http_429 INTEGER DEFAULT 0, http_5xx INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, message TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def state_path(data_dir: Path, platform: str) -> Path:
    return Path(data_dir) / f"state-{platform}.sqlite"


class State:
    """One connection; use each instance from a single thread."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    # meta

    def meta_get(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def meta_int(self, key: str, default: int = 0) -> int:
        value = self.meta_get(key)
        return int(value) if value is not None else default

    def meta_set(self, key: str, value) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    def meta_prefix(self, prefix: str) -> dict[str, str]:
        rows = self.db.execute("SELECT key, value FROM meta WHERE key LIKE ?", (prefix + "%",))
        return {r["key"][len(prefix) :]: r["value"] for r in rows}

    # players

    def player_crawled_since(self, puuid: str, since: float) -> bool:
        row = self.db.execute("SELECT crawled_at FROM players WHERE puuid = ?", (puuid,)).fetchone()
        return bool(row and row["crawled_at"] is not None and row["crawled_at"] >= since)

    def mark_player(self, puuid: str, tier: str, division: str, at: float, pass_no: int) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO players (puuid, tier, division, crawled_at, pass_no) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(puuid) DO UPDATE SET tier = excluded.tier, "
                "division = excluded.division, crawled_at = excluded.crawled_at, "
                "pass_no = excluded.pass_no",
                (puuid, tier, division, at, pass_no),
            )

    def player_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM players").fetchone()[0]

    # matches

    def add_matches(self, ids: list[str], tier: str, at: float, limit: int | None = None) -> int:
        """Insert unseen ids as pending, at most `limit` of them. Returns how many were new."""
        added = 0
        with self.db:
            for match_id in ids:
                if limit is not None and added >= limit:
                    break
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO matches (match_id, tier, status, added_at) "
                    "VALUES (?, ?, 'pending', ?)",
                    (match_id, tier, at),
                )
                added += cur.rowcount
        return added

    def pending(self, limit: int, exclude: set[str] | frozenset[str] = frozenset()):
        """Oldest pending (match_id, tier) pairs, skipping ids in `exclude`."""
        out: list[tuple[str, str]] = []
        rows = self.db.execute(
            "SELECT match_id, tier FROM matches WHERE status = 'pending' ORDER BY added_at, rowid"
        )
        for row in rows:
            if row["match_id"] in exclude:
                continue
            out.append((row["match_id"], row["tier"]))
            if len(out) >= limit:
                break
        return out

    def set_status(self, match_ids: list[str], status: str) -> None:
        with self.db:
            self.db.executemany(
                "UPDATE matches SET status = ? WHERE match_id = ?",
                [(status, m) for m in match_ids],
            )

    def match_counts(self) -> dict[str, int]:
        rows = self.db.execute("SELECT status, COUNT(*) AS n FROM matches GROUP BY status")
        return {r["status"]: r["n"] for r in rows}

    def match_ids_with_status(self, status: str) -> list[str]:
        rows = self.db.execute("SELECT match_id FROM matches WHERE status = ?", (status,))
        return [r["match_id"] for r in rows]

    # batches

    def record_batches(
        self,
        batches: list[dict],
        done_ids: list[str],
        skipped_ids: list[str] = (),
        now: float | None = None,
    ) -> None:
        """Record batch files and mark their matches done, in one transaction."""
        now = time.time() if now is None else now
        with self.db:
            for b in batches:
                self.db.execute(
                    "INSERT OR REPLACE INTO batches (file, patch, version, games, rows, "
                    "written_at, bytes, blue_wins, duration_s) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        b["file"],
                        b["patch"],
                        b["version"],
                        b["games"],
                        b["rows"],
                        b.get("written_at", now),
                        b.get("bytes", 0),
                        b.get("blue_wins", 0),
                        b.get("duration_s", 0),
                    ),
                )
            self.db.executemany(
                "UPDATE matches SET status = 'done' WHERE match_id = ?", [(m,) for m in done_ids]
            )
            self.db.executemany(
                "UPDATE matches SET status = 'skipped' WHERE match_id = ?",
                [(m,) for m in skipped_ids],
            )

    def batch_files(self) -> set[str]:
        return {r["file"] for r in self.db.execute("SELECT file FROM batches")}

    def delete_patch_batches(self, patch: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM batches WHERE patch = ?", (patch,))

    def patch_games(self) -> dict[str, int]:
        rows = self.db.execute("SELECT patch, SUM(games) AS n FROM batches GROUP BY patch")
        return {r["patch"]: r["n"] for r in rows}

    def totals(self) -> dict:
        row = self.db.execute(
            "SELECT COALESCE(SUM(games), 0) AS games, COALESCE(SUM(rows), 0) AS rows, "
            "COALESCE(SUM(bytes), 0) AS bytes, COALESCE(SUM(blue_wins), 0) AS blue_wins, "
            "COALESCE(SUM(duration_s), 0) AS duration_s, MAX(written_at) AS last_batch "
            "FROM batches"
        ).fetchone()
        return dict(row)

    def games_since(self, since: float) -> int:
        row = self.db.execute(
            "SELECT COALESCE(SUM(games), 0) FROM batches WHERE written_at >= ?", (since,)
        ).fetchone()
        return row[0]

    # counters

    def add_counts(self, minute: int, requests: int, http_429: int, http_5xx: int) -> None:
        if not (requests or http_429 or http_5xx):
            return
        with self.db:
            self.db.execute(
                "INSERT INTO counters (minute, requests, http_429, http_5xx) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(minute) DO UPDATE SET requests = requests + excluded.requests, "
                "http_429 = http_429 + excluded.http_429, http_5xx = http_5xx + excluded.http_5xx",
                (minute, requests, http_429, http_5xx),
            )
            self.db.execute("DELETE FROM counters WHERE minute < ?", (minute - 24 * 60,))

    def counts_since(self, minute: int) -> dict[str, int]:
        row = self.db.execute(
            "SELECT COALESCE(SUM(requests), 0) AS requests, COALESCE(SUM(http_429), 0) AS "
            "http_429, COALESCE(SUM(http_5xx), 0) AS http_5xx FROM counters WHERE minute >= ?",
            (minute,),
        ).fetchone()
        return dict(row)

    # errors

    def add_error(self, message: str, at: float | None = None) -> None:
        at = time.time() if at is None else at
        with self.db:
            self.db.execute("INSERT INTO errors (at, message) VALUES (?, ?)", (at, message[:300]))
            self.db.execute(
                "DELETE FROM errors WHERE id NOT IN (SELECT id FROM errors ORDER BY id DESC "
                "LIMIT ?)",
                (ERRORS_KEPT,),
            )

    def recent_errors(self, n: int = 10) -> list[tuple[float, str]]:
        rows = self.db.execute("SELECT at, message FROM errors ORDER BY id DESC LIMIT ?", (n,))
        return [(r["at"], r["message"]) for r in rows]
