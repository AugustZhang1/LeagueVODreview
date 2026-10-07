"""Crawl ranked solo games into Parquet batches.

python -m lolreview.crawler [--platforms na1,euw1,kr] [--fake] [--minutes N]
                            [--data DIR] [--batch-games N]
"""

import argparse
import json
import logging
import os
import re
import shutil
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from lolreview import features, status
from lolreview.config import ROOT, load_config
from lolreview.constants import APEX_TIERS, DIVISIONS
from lolreview.fake_riot import FakeRiotClient
from lolreview.riot import NotFoundError, RiotClient, RiotError, cluster_for
from lolreview.state import State, state_path

log = logging.getLogger("lolreview.crawler")

DAY_S = 86400
IDLE_SLEEP_S = 60.0
ERROR_SLEEP_S = 30.0
PENDING_CHUNK = 50
# A thread can sit in the rate limiter for up to a full long window (120 s) before it sees the
# stop; leaving earlier loses its unsaved games. systemd's TimeoutStopSec must be longer.
JOIN_TIMEOUT_S = 150.0
PATCH_DIR = re.compile(r"^\d+\.\d+$")
PART_NAME = re.compile(r"^part-(\d+)\.parquet(?:\.tmp)?$")


def patch_key(patch: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", patch))


@dataclass
class Game:
    match_id: str
    patch: str
    rows: list[dict]


class PlatformCrawler:
    def __init__(
        self,
        platform: str,
        client,
        data_dir: Path,
        stop: threading.Event,
        cfg: dict | None = None,
        batch_games: int | None = None,
        idle_sleep_s: float = IDLE_SLEEP_S,
        clock=time.time,
    ):
        cfg = cfg if cfg is not None else load_config()
        crawl = cfg["crawl"]
        self.platform = platform
        self.cluster = cluster_for(platform)
        self.client = client
        self.data_dir = Path(data_dir)
        self.stop = stop
        self.clock = clock
        self.idle_sleep_s = idle_sleep_s
        self.queue = int(crawl.get("queue", 420))
        self.cap = int(crawl["games_per_tier_per_pass"])
        self.batch_games = int(batch_games or crawl["batch_games"])
        self.patches_kept = int(crawl["patches_kept"])
        self.window_days = float(crawl.get("patch_window_days", 42))
        tiers = list(crawl["tiers"])
        self.tiers = tiers[: tiers.index(crawl["bottom_tier"].upper()) + 1]
        self.state = State(state_path(self.data_dir, platform))
        self.platform_dir = self.data_dir / platform
        self.buffer: list[Game] = []
        self.buffered: set[str] = set()
        self.restart = False
        self._seen_stats = {"requests": 0, "rate_limited": 0, "server_errors": 0}
        self._last_error_time = None

    # lifecycle

    def run(self) -> None:
        st = self.state
        st.meta_set("started_at", self.clock())
        st.meta_set("pass_no", st.meta_int("pass_no", 1))
        self._recover_batches()
        self._drop_old_patch_folders()
        try:
            while not self.stop.is_set():
                try:
                    self._run_pass()
                except Exception as e:  # keep the service alive; the page shows the error
                    log.exception("%s: pass failed", self.platform)
                    st.add_error(f"{self.platform}: {type(e).__name__}: {e}", self.clock())
                    self.stop.wait(ERROR_SLEEP_S)
            self.flush()
        finally:
            st.close()

    # passes

    def _window_start(self) -> float:
        return float(self.state.meta_get("window_start", "0"))

    def _run_pass(self) -> None:
        st = self.state
        pass_no = st.meta_int("pass_no", 1)
        crawled_before = st.player_count()
        for idx in range(st.meta_int("tier_idx", 0), len(self.tiers)):
            if self.stop.is_set():
                return
            st.meta_set("tier_idx", idx)
            self._run_tier(self.tiers[idx], pass_no)
            if self.restart:
                self.restart = False
                return
        if self.stop.is_set():
            return
        st.meta_set("tier_idx", 0)
        if st.player_count() > crawled_before:
            st.meta_set("pass_no", pass_no + 1)
        else:
            self.stop.wait(self.idle_sleep_s)

    def _added_key(self, pass_no: int, tier: str) -> str:
        return f"added:{pass_no}:{tier}"

    def _players(self, tier: str):
        """Yield (puuid, division); lower tiers are spread across divisions page by page."""
        if tier in APEX_TIERS:
            entries = self.client.apex_league(self.platform, tier)["entries"]
            for e in sorted(entries, key=lambda e: -e.get("leaguePoints", 0)):
                yield e["puuid"], e.get("rank", "I")
            return
        page = 1
        while True:
            any_entries = False
            for division in DIVISIONS:
                for e in self.client.league_entries(self.platform, tier, division, page):
                    any_entries = True
                    yield e["puuid"], division
            if not any_entries:
                return
            page += 1

    def _run_tier(self, tier: str, pass_no: int) -> None:
        st = self.state
        key = self._added_key(pass_no, tier)
        st.meta_set("tier", tier)
        window_start = self._window_start()
        try:
            for puuid, division in self._players(tier):
                if self.stop.is_set() or self.restart:
                    return
                added = st.meta_int(key, 0)
                if added >= self.cap:
                    break
                if st.player_crawled_since(puuid, window_start):
                    continue
                st.meta_set("division", division)
                self._tick()
                try:
                    ids = self.client.match_ids(
                        self.cluster,
                        puuid,
                        queue=self.queue,
                        start_time=int(self.clock() - self.window_days * DAY_S),
                        count=100,
                    )
                except NotFoundError:
                    ids = []
                except RiotError as e:
                    st.add_error(f"{self.platform}: match ids failed: {e}", self.clock())
                    continue
                new = st.add_matches(ids, tier, self.clock(), limit=self.cap - added)
                st.meta_set(key, added + new)
                st.mark_player(puuid, tier, division, self.clock(), pass_no)
                self._process_pending()
        except RiotError as e:
            st.add_error(f"{self.platform}: {tier} listing failed: {e}", self.clock())
            self.stop.wait(1.0)

    # games

    def _process_pending(self) -> None:
        while not self.stop.is_set() and not self.restart:
            items = self.state.pending(PENDING_CHUNK, self.buffered)
            if not items:
                return
            for match_id, tier in items:
                if self.stop.is_set() or self.restart:
                    return
                self._fetch_game(match_id, tier)
                self._tick()
                if len(self.buffer) >= self.batch_games:
                    self.flush()

    def _fetch_game(self, match_id: str, tier: str) -> None:
        st = self.state
        try:
            patch = self._patch_of_id(match_id)
            match = timeline = None
            if patch is not None:  # one request: the timeline has everything the rows need
                if patch not in self._kept_patches():
                    st.set_status([match_id], "skipped")
                    return
                timeline = self.client.timeline(self.cluster, match_id)
                match = features.match_from_timeline(timeline, patch)
            if match is None:  # learn the patch from the match itself
                match = self.client.match(self.cluster, match_id)
                patch = features.patch_of(match)
                self._see_patch(patch)
                self._note_patch_id(match_id, patch)
                if features.skip_reason(match) is not None or patch not in self._kept_patches():
                    st.set_status([match_id], "skipped")
                    return
                timeline = timeline or self.client.timeline(self.cluster, match_id)
            rows = features.extract_rows(match, timeline, tier)
        except RiotError as e:
            st.add_error(f"{self.platform}: {match_id}: {e}", self.clock())
            st.set_status([match_id], "failed")
            return
        except Exception as e:  # one malformed match must not stall the platform
            log.exception("%s: %s: could not process match", self.platform, match_id)
            st.add_error(f"{self.platform}: {match_id}: {type(e).__name__}: {e}", self.clock())
            st.set_status([match_id], "failed")
            return
        if not rows:
            st.set_status([match_id], "skipped")
            return
        self.buffer.append(Game(match_id, patch, rows))
        self.buffered.add(match_id)

    def _patch_ids(self) -> dict[str, list[int]]:
        return json.loads(self.state.meta_get("patch_ids", "{}"))

    def _own_id(self, match_id: str) -> bool:
        """A game of this platform: a player's match list also has their games on the cluster's
        other platforms (an NA player's LA1 games), whose ids count separately."""
        return match_id.split("_", 1)[0].lower() == self.platform.lower()

    def _patch_of_id(self, match_id: str) -> str | None:
        """The patch whose seen game ids (lowest to highest) include this one, else None. Ids grow
        over time and a patch starts at one id, so between two ids of a patch it's that patch."""
        if not self._own_id(match_id):
            return None
        n = int(match_id.rsplit("_", 1)[1])
        hits = [p for p, (lo, hi) in self._patch_ids().items() if lo <= n <= hi]
        return hits[0] if len(hits) == 1 else None

    def _note_patch_id(self, match_id: str, patch: str) -> None:
        if not self._own_id(match_id):
            return
        n = int(match_id.rsplit("_", 1)[1])
        ids = self._patch_ids()
        lo, hi = ids.get(patch, (n, n))
        ids[patch] = [min(lo, n), max(hi, n)]
        self.state.meta_set("patch_ids", json.dumps(ids))

    def _kept_patches(self) -> list[str]:
        return json.loads(self.state.meta_get("patches_seen", "[]"))

    def _see_patch(self, patch: str) -> None:
        st = self.state
        seen = set(self._kept_patches())
        if patch not in seen:
            seen.add(patch)
            kept = sorted(seen, key=patch_key)[-self.patches_kept :]
            st.meta_set("patches_seen", json.dumps(kept))
            self._drop_old_patch_folders()
        newest = max(self._kept_patches(), key=patch_key)
        previous = st.meta_get("newest_patch")
        if newest == previous:
            return
        st.meta_set("newest_patch", newest)
        if previous is None:
            return
        log.info("%s: new patch %s, restarting from the top", self.platform, newest)
        st.meta_set("window_start", self.clock())
        st.meta_set("pass_no", st.meta_int("pass_no", 1) + 1)
        st.meta_set("tier_idx", 0)
        self.restart = True

    # batches

    def _drop_old_patch_folders(self) -> None:
        kept = self._kept_patches()
        if not kept or not self.platform_dir.is_dir():
            return
        oldest = min(patch_key(p) for p in kept)
        for folder in self.platform_dir.iterdir():
            if not (folder.is_dir() and PATCH_DIR.match(folder.name)):
                continue
            if patch_key(folder.name) < oldest:
                shutil.rmtree(folder, ignore_errors=True)
                self.state.delete_patch_batches(folder.name)

    def _recover_batches(self) -> None:
        """Settle batch files left by a crash; never delete a finished part file."""
        if not self.platform_dir.is_dir():
            return
        known = self.state.batch_files()
        for tmp in sorted(self.platform_dir.rglob("part-*.parquet.tmp")):
            final = tmp.with_suffix("")
            if final.relative_to(self.data_dir).as_posix() in known and not final.exists():
                os.replace(tmp, final)  # crash between the commit and the rename
                log.info("%s: finished rename of %s", self.platform, final.name)
            else:
                tmp.unlink()  # crash before the commit, or a stale copy
        stray = sorted(
            p.relative_to(self.data_dir).as_posix()
            for p in self.platform_dir.rglob("part-*.parquet")
            if p.relative_to(self.data_dir).as_posix() not in known
        )
        if stray:
            log.warning(
                "%s: %d batch file(s) not in the state database, left in place: %s",
                self.platform,
                len(stray),
                ", ".join(stray),
            )

    def _next_part(self, folder: Path) -> int:
        nums = [
            int(m.group(1))
            for p in folder.glob("part-*.parquet*")
            if (m := PART_NAME.match(p.name))
        ]
        return max(nums, default=0) + 1

    def flush(self) -> None:
        if not self.buffer:
            return
        kept = set(self._kept_patches())
        by_patch: dict[str, list[Game]] = {}
        skipped: list[str] = []
        for game in self.buffer:
            if game.patch in kept:
                by_patch.setdefault(game.patch, []).append(game)
            else:
                skipped.append(game.match_id)
        written: list[tuple[Path, Path]] = []
        batches: list[dict] = []
        done: list[str] = []
        try:
            for patch, games in by_patch.items():
                batches.append(self._write_batch(patch, games, written))
                done.extend(g.match_id for g in games)
            self.state.record_batches(batches, done, skipped, self.clock())
        except BaseException:
            for tmp, _ in written:
                tmp.unlink(missing_ok=True)
            raise
        self.buffer = []
        self.buffered = set()
        for tmp, final in written:  # a failure here is finished by _recover_batches on start
            os.replace(tmp, final)

    def _write_batch(self, patch: str, games: list[Game], written: list[tuple[Path, Path]]) -> dict:
        import pyarrow.parquet as pq

        version = features.FEATURES_VERSION
        folder = self.platform_dir / patch / f"v{version}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"part-{self._next_part(folder):05d}.parquet"
        rows = [r for g in games for r in g.rows]
        blue_wins = sum(g.rows[0]["blue_won"] for g in games)
        duration = sum(g.rows[0]["duration_s"] for g in games)
        table = features.rows_to_table(rows).replace_schema_metadata(
            {
                "games": str(len(games)),
                "blue_wins": str(blue_wins),
                "duration_s": str(duration),
                "features_version": str(version),
            }
        )
        tmp = path.with_name(path.name + ".tmp")
        written.append((tmp, path))
        pq.write_table(table, tmp, compression="zstd")
        return {
            "file": path.relative_to(self.data_dir).as_posix(),
            "patch": patch,
            "version": version,
            "games": len(games),
            "rows": len(rows),
            "bytes": tmp.stat().st_size,
            "blue_wins": blue_wins,
            "duration_s": duration,
        }

    # request counters and errors

    def _tick(self) -> None:
        stats = self.client.stats()
        delta = {k: stats[k] - self._seen_stats[k] for k in self._seen_stats}
        if any(delta.values()):
            self._seen_stats = {k: stats[k] for k in self._seen_stats}
            self.state.add_counts(
                int(self.clock() // 60),
                delta["requests"],
                delta["rate_limited"],
                delta["server_errors"],
            )
        err = stats.get("last_error")
        if err and err["time"] != self._last_error_time:
            self._last_error_time = err["time"]
            self.state.add_error(f"{self.platform}: {err['status']} on {err['path']}", err["time"])


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    crawl = cfg["crawl"]
    default_data = Path(cfg["paths"]["data_dir"])
    if not default_data.is_absolute():
        default_data = ROOT / default_data
    ap = argparse.ArgumentParser(description="Crawl ranked solo games into Parquet batches")
    ap.add_argument("--platforms", default=",".join(crawl["platforms"]))
    ap.add_argument("--fake", action="store_true", help="use made-up data, no API key needed")
    ap.add_argument("--minutes", type=float, default=None, help="stop after this many minutes")
    ap.add_argument("--data", type=Path, default=default_data)
    ap.add_argument("--batch-games", type=int, default=None)
    ap.add_argument("--status-port", type=int, default=int(crawl.get("status_port", 8080)))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    args.data.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    clients: dict[str, object] = {}

    def key_status() -> dict[str, str]:
        return {p: getattr(c, "key_status", "ok") for p, c in clients.items()}

    try:
        server = status.serve(args.data, platforms, args.status_port, key_status, cfg)
        log.info("progress page on http://127.0.0.1:%d", server.server_address[1])
    except OSError as e:
        server = None
        log.warning("progress page not started: %s", e)

    threads = []
    for platform in platforms:
        client = FakeRiotClient(platform=platform) if args.fake else RiotClient(on_key_error="wait")
        clients[platform] = client
        crawler_args = (platform, client, args.data, stop, cfg, args.batch_games)
        t = threading.Thread(
            target=lambda a=crawler_args: PlatformCrawler(*a).run(),
            name=f"crawl-{platform}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    deadline = time.monotonic() + args.minutes * 60 if args.minutes else None
    while not stop.is_set() and any(t.is_alive() for t in threads):
        if deadline is not None and time.monotonic() >= deadline:
            stop.set()
            break
        stop.wait(0.5)
    stop.set()
    for t in threads:
        t.join(JOIN_TIMEOUT_S)
    if server is not None:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
