import math
import threading
import time
from collections import deque
from collections.abc import Callable
from urllib.parse import quote

import requests

from lolreview.config import load_config, read_env
from lolreview.constants import CLUSTERS, PLATFORM_TO_CLUSTER, QUEUE_RANKED_SOLO

SOLO_QUEUE = "RANKED_SOLO_5x5"
KEY_RETRY_S = 60.0
DEFAULT_RETRY_AFTER_S = 10.0
MAX_5XX_TRIES = 5
BACKOFF_CAP_S = 60.0
REQUEST_TIMEOUT_S = 30

# Riot's real limits for a development key; the configured counts are these minus a margin.
REAL_SHORT = 20
REAL_LONG = 100

APEX_ENDPOINTS = {
    "CHALLENGER": "challengerleagues",
    "GRANDMASTER": "grandmasterleagues",
    "MASTER": "masterleagues",
}


class RiotError(Exception):
    pass


class KeyExpiredError(RiotError):
    pass


class KeyMissingError(RiotError):
    pass


class RateLimitedError(RiotError):
    def __init__(self, retry_after_s: float):
        super().__init__(f"rate limited, retry after {retry_after_s:g}s")
        self.retry_after_s = retry_after_s


class NotFoundError(RiotError):
    pass


class RiotUnavailableError(RiotError):
    pass


def cluster_for(platform: str) -> str:
    """Regional cluster of a platform (`na1` -> `americas`); a cluster maps to itself."""
    if platform in CLUSTERS:
        return platform
    return PLATFORM_TO_CLUSTER[platform]


def _parse_pairs(header: str | None) -> list[tuple[int, float]]:
    """Parse "20:1,100:120" into [(20, 1.0), (100, 120.0)]; bad parts are skipped."""
    out: list[tuple[int, float]] = []
    for part in (header or "").split(","):
        count, _, window = part.strip().partition(":")
        try:
            out.append((int(count), float(window)))
        except ValueError:
            continue
    return out


class RateLimiter:
    """Sliding-window limiter. `windows` is a list of (count, window_seconds).

    `margins` maps a window length to how far below Riot's real limit we stay, so
    update_from_headers can keep the same safety margin once it sees the real values.
    """

    def __init__(
        self,
        windows: list[tuple[int, float]],
        margins: dict[float, int] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._limits: dict[float, int] = {float(w): c for c, w in windows}
        self._margins: dict[float, int] = {float(w): m for w, m in (margins or {}).items()}
        self._stamps: dict[float, deque[float]] = {w: deque() for w in self._limits}

    @property
    def limits(self) -> dict[float, int]:
        with self._lock:
            return dict(self._limits)

    def count(self, window: float) -> int:
        with self._lock:
            self._prune(float(window), self._clock())
            return len(self._stamps[float(window)])

    def _prune(self, window: float, now: float) -> None:
        stamps = self._stamps[window]
        while stamps and stamps[0] <= now - window:
            stamps.popleft()

    def acquire(self) -> None:
        """Block until a slot is free in every window, then take it."""
        while True:
            with self._lock:
                now = self._clock()
                wait = 0.0
                for window, limit in self._limits.items():
                    self._prune(window, now)
                    stamps = self._stamps[window]
                    if len(stamps) >= limit:
                        wait = max(wait, stamps[len(stamps) - limit] + window - now)
                if wait <= 0:
                    for stamps in self._stamps.values():
                        stamps.append(now)
                    return
            self._sleep(wait)

    def update_from_headers(self, headers) -> None:
        limit_pairs = _parse_pairs(headers.get("X-App-Rate-Limit"))
        count_pairs = _parse_pairs(headers.get("X-App-Rate-Limit-Count"))
        with self._lock:
            now = self._clock()
            for real, window in limit_pairs:
                margin = self._margins.get(window)
                if margin is None:
                    margin = math.ceil(real * 0.05)
                    self._margins[window] = margin
                self._limits[window] = max(1, real - margin)
                self._stamps.setdefault(window, deque())
            for used, window in count_pairs:
                if window not in self._stamps:
                    continue
                self._prune(window, now)
                stamps = self._stamps[window]
                # Calls we don't know about are treated as just made: the safe side.
                for _ in range(used - len(stamps)):
                    stamps.append(now)


_registry: dict[str, RateLimiter] = {}
_registry_lock = threading.Lock()


def _make_limiter(cluster: str) -> RateLimiter:
    cfg = load_config()["rate_limit"]
    short_w = float(cfg["short_window_s"])
    long_w = float(cfg["long_window_s"])
    long_count = cfg["long_count"]
    if cluster == "americas":
        long_count = cfg.get("americas_long_count", long_count)
    reserve = cfg["long_count"] - long_count
    margins = {
        short_w: REAL_SHORT - cfg["short_count"],
        long_w: REAL_LONG - cfg["long_count"] + reserve,
    }
    return RateLimiter([(cfg["short_count"], short_w), (long_count, long_w)], margins)


def limiter_for(routing: str) -> RateLimiter:
    """The shared limiter of a platform's or cluster's regional cluster."""
    cluster = cluster_for(routing)
    with _registry_lock:
        if cluster not in _registry:
            _registry[cluster] = _make_limiter(cluster)
        return _registry[cluster]


def reset_limiters() -> None:
    with _registry_lock:
        _registry.clear()


class RiotClient:
    def __init__(
        self,
        on_key_error: str = "wait",
        max_429_retries: int | None = None,
        session: requests.Session | None = None,
        env_reader: Callable[[], dict[str, str]] = read_env,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if on_key_error not in ("wait", "raise"):
            raise ValueError("on_key_error must be 'wait' or 'raise'")
        self.on_key_error = on_key_error
        self.max_429_retries = max_429_retries
        self._session = session or requests.Session()
        self._env_reader = env_reader
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._key_status = "ok"
        self._bad_key: str | None = None
        self._requests = 0
        self._n429 = 0
        self._n5xx = 0
        self._last_error: dict | None = None

    @property
    def key_status(self) -> str:
        with self._lock:
            return self._key_status

    def stats(self) -> dict:
        with self._lock:
            return {
                "requests": self._requests,
                "rate_limited": self._n429,
                "server_errors": self._n5xx,
                "last_error": dict(self._last_error) if self._last_error else None,
                "key_status": self._key_status,
            }

    def _note_error(self, status: int | str, path: str) -> None:
        with self._lock:
            self._last_error = {"time": self._clock(), "status": status, "path": path}

    def _set_key_status(self, status: str) -> None:
        with self._lock:
            self._key_status = status

    def _current_key(self) -> str:
        """Return a key worth trying, waiting or raising as configured."""
        while True:
            key = self._env_reader().get("RIOT_API_KEY", "").strip()
            if not key:
                self._set_key_status("missing")
                if self.on_key_error == "raise":
                    raise KeyMissingError("RIOT_API_KEY is not set")
            elif key != self._bad_key or self.on_key_error == "raise":
                return key
            self._sleep(KEY_RETRY_S)

    def _get(self, routing: str, path: str, params: dict | None = None):
        url = f"https://{routing}.api.riotgames.com{path}"
        limiter = limiter_for(routing)
        tries_5xx = 0
        n429 = 0
        while True:
            key = self._current_key()
            limiter.acquire()
            with self._lock:
                self._requests += 1
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers={"X-Riot-Token": key},
                    timeout=REQUEST_TIMEOUT_S,
                )
            except requests.RequestException:
                resp = None
            status = resp.status_code if resp is not None else 599
            if resp is not None:
                limiter.update_from_headers(resp.headers)

            if status == 200:
                self._bad_key = None
                self._set_key_status("ok")
                return resp.json()
            if status in (401, 403):
                self._bad_key = key
                self._set_key_status("expired")
                self._note_error(status, path)
                if self.on_key_error == "raise":
                    raise KeyExpiredError(f"Riot rejected the API key ({status})")
                continue
            if status == 429:
                with self._lock:
                    self._n429 += 1
                self._note_error(status, path)
                n429 += 1
                try:
                    retry_after = float(resp.headers.get("Retry-After", DEFAULT_RETRY_AFTER_S))
                except (TypeError, ValueError):
                    retry_after = DEFAULT_RETRY_AFTER_S
                if self.max_429_retries is not None and n429 > self.max_429_retries:
                    raise RateLimitedError(retry_after)
                self._sleep(retry_after)
                continue
            if status == 404:
                raise NotFoundError(path)
            if status >= 500:
                with self._lock:
                    self._n5xx += 1
                self._note_error(status, path)
                tries_5xx += 1
                if tries_5xx >= MAX_5XX_TRIES:
                    raise RiotUnavailableError(f"{path}: {status} after {tries_5xx} tries")
                self._sleep(min(2.0**tries_5xx, BACKOFF_CAP_S))
                continue
            self._note_error(status, path)
            raise RiotError(f"{path}: unexpected status {status}")

    def apex_league(self, platform: str, tier: str) -> dict:
        endpoint = APEX_ENDPOINTS[tier.upper()]
        return self._get(platform, f"/lol/league/v4/{endpoint}/by-queue/{SOLO_QUEUE}")

    def league_entries(self, platform: str, tier: str, division: str, page: int = 1) -> list:
        return self._get(
            platform,
            f"/lol/league/v4/entries/{SOLO_QUEUE}/{tier}/{division}",
            {"page": page},
        )

    def match_ids(
        self,
        cluster: str,
        puuid: str,
        queue: int = QUEUE_RANKED_SOLO,
        start_time: int | None = None,
        start: int = 0,
        count: int = 100,
    ) -> list[str]:
        params: dict = {"queue": queue, "start": start, "count": count}
        if start_time is not None:
            params["startTime"] = start_time
        return self._get(
            cluster, f"/lol/match/v5/matches/by-puuid/{quote(puuid, safe='')}/ids", params
        )

    def match(self, cluster: str, match_id: str) -> dict:
        return self._get(cluster, f"/lol/match/v5/matches/{match_id}")

    def timeline(self, cluster: str, match_id: str) -> dict:
        return self._get(cluster, f"/lol/match/v5/matches/{match_id}/timeline")

    def account_by_riot_id(self, cluster: str, name: str, tag: str) -> dict:
        return self._get(
            cluster,
            f"/riot/account/v1/accounts/by-riot-id/{quote(name, safe='')}/{quote(tag, safe='')}",
        )

    def rank_by_puuid(self, platform: str, puuid: str) -> dict | None:
        entries = self._get(platform, f"/lol/league/v4/entries/by-puuid/{quote(puuid, safe='')}")
        for entry in entries:
            if entry.get("queueType") == SOLO_QUEUE:
                return entry
        return None
