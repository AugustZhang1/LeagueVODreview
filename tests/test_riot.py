import threading

import pytest

from lolreview import riot
from lolreview.riot import (
    KeyExpiredError,
    KeyMissingError,
    NotFoundError,
    RateLimitedError,
    RateLimiter,
    RiotClient,
    RiotError,
    RiotUnavailableError,
    cluster_for,
    limiter_for,
)


class FakeClock:
    def __init__(self):
        self.t = 1000.0
        self.lock = threading.Lock()
        self.sleeps: list[float] = []

    def __call__(self):
        with self.lock:
            return self.t

    def sleep(self, s):
        with self.lock:
            self.sleeps.append(s)
            self.t += max(s, 0.001)


@pytest.fixture(autouse=True)
def fresh_registry():
    riot.reset_limiters()
    yield
    riot.reset_limiters()


def make_limiter(clock, windows=((18, 1), (95, 120)), margins=None):
    return RateLimiter(list(windows), margins, clock=clock, sleep=clock.sleep)


def max_in_window(stamps, window):
    best = 0
    for i, t in enumerate(stamps):
        best = max(best, sum(1 for u in stamps[i:] if u < t + window))
    return best


# ---- limiter ----


def test_limiter_never_exceeds_windows():
    clock = FakeClock()
    lim = make_limiter(clock)
    stamps = []
    for _ in range(400):
        lim.acquire()
        stamps.append(clock())
    assert max_in_window(stamps, 1) <= 18
    assert max_in_window(stamps, 120) <= 95
    assert stamps[-1] - stamps[0] > 120


def test_limiter_threads():
    clock = FakeClock()
    lim = make_limiter(clock)
    stamps = []
    lock = threading.Lock()

    def work():
        for _ in range(60):
            lim.acquire()
            with lock:
                stamps.append(clock())

    threads = [threading.Thread(target=work) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stamps.sort()
    assert len(stamps) == 300
    assert max_in_window(stamps, 1) <= 18
    assert max_in_window(stamps, 120) <= 95


def test_limiter_respects_riot_count_above_own():
    clock = FakeClock()
    lim = make_limiter(clock, margins={1: 2, 120: 5})
    lim.update_from_headers(
        {"X-App-Rate-Limit": "20:1,100:120", "X-App-Rate-Limit-Count": "3:1,90:120"}
    )
    assert lim.count(120) == 90
    stamps = []
    for _ in range(40):
        lim.acquire()
        stamps.append(clock())
    start = 1000.0
    # Only 5 calls fit before the shared long window is full.
    assert sum(1 for s in stamps if s < start + 120) <= 5
    assert max_in_window(stamps, 1) <= 18


def test_limiter_count_never_lowers_own():
    clock = FakeClock()
    lim = make_limiter(clock)
    for _ in range(10):
        lim.acquire()
    lim.update_from_headers({"X-App-Rate-Limit-Count": "2:1,3:120"})
    assert lim.count(120) == 10


def test_header_sets_limits_with_margin():
    clock = FakeClock()
    lim = make_limiter(clock, margins={1: 2, 120: 5})
    lim.update_from_headers({"X-App-Rate-Limit": "20:1,100:120"})
    assert lim.limits == {1.0: 18, 120.0: 95}
    lim.update_from_headers({"X-App-Rate-Limit": "500:10,30000:600"})
    assert lim.limits[10.0] == 475


def test_header_garbage_ignored():
    lim = make_limiter(FakeClock())
    lim.update_from_headers({"X-App-Rate-Limit": "junk,,5", "X-App-Rate-Limit-Count": "a:b"})
    assert lim.limits == {1.0: 18, 120.0: 95}


def test_limiter_for_defaults_and_sharing():
    na = limiter_for("na1")
    assert limiter_for("americas") is na
    assert limiter_for("br1") is na
    assert limiter_for("euw1") is not na
    assert limiter_for("euw1") is limiter_for("europe")
    assert na.limits == {1.0: 18, 120.0: 80}
    assert limiter_for("euw1").limits == {1.0: 18, 120.0: 95}


def test_americas_header_keeps_reserve():
    na = limiter_for("na1")
    na.update_from_headers({"X-App-Rate-Limit": "20:1,100:120"})
    assert na.limits == {1.0: 18, 120.0: 80}
    eu = limiter_for("euw1")
    eu.update_from_headers({"X-App-Rate-Limit": "20:1,100:120"})
    assert eu.limits == {1.0: 18, 120.0: 95}


def test_cluster_for():
    assert cluster_for("kr") == "asia"
    assert cluster_for("sea") == "sea"
    with pytest.raises(KeyError):
        cluster_for("nowhere")


# ---- client ----


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = {} if body is None else body
        self.headers = headers or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make_client(responses, env=None, **kw):
    clock = FakeClock()
    session = FakeSession(responses)
    keys = env if env is not None else [{"RIOT_API_KEY": "key1"}]
    reads = iter(keys)
    last = {}

    def env_reader():
        nonlocal last
        last = next(reads, last)
        return last

    client = RiotClient(
        session=session, env_reader=env_reader, clock=clock, sleep=clock.sleep, **kw
    )
    return client, session, clock


def test_success_sends_key_and_counts():
    client, session, _ = make_client([FakeResponse(200, {"a": 1})])
    assert client.match("americas", "NA1_1") == {"a": 1}
    assert session.calls[0]["headers"] == {"X-Riot-Token": "key1"}
    assert (
        session.calls[0]["url"] == "https://americas.api.riotgames.com/lol/match/v5/matches/NA1_1"
    )
    assert client.key_status == "ok"
    assert client.stats()["requests"] == 1


def test_401_raise_mode():
    client, session, _ = make_client([FakeResponse(401)], on_key_error="raise")
    with pytest.raises(KeyExpiredError):
        client.match("americas", "NA1_1")
    assert client.key_status == "expired"
    assert client.stats()["last_error"]["status"] == 401
    assert len(session.calls) == 1


def test_403_raise_mode():
    client, _, _ = make_client([FakeResponse(403)], on_key_error="raise")
    with pytest.raises(KeyExpiredError):
        client.match("americas", "NA1_1")


def test_missing_key_raise_mode():
    client, session, _ = make_client([], env=[{}], on_key_error="raise")
    with pytest.raises(KeyMissingError):
        client.match("americas", "NA1_1")
    assert client.key_status == "missing"
    assert session.calls == []


def test_missing_key_wait_mode():
    client, session, clock = make_client(
        [FakeResponse(200, {"ok": 1})], env=[{}, {}, {"RIOT_API_KEY": "k"}]
    )
    assert client.match("americas", "NA1_1") == {"ok": 1}
    assert clock.sleeps == [60.0, 60.0]
    assert session.calls[0]["headers"]["X-Riot-Token"] == "k"


def test_401_then_new_key_wait_mode():
    envs = [
        {"RIOT_API_KEY": "old"},
        {"RIOT_API_KEY": "old"},  # still the old key after the first wait
        {"RIOT_API_KEY": "new"},
    ]
    client, session, clock = make_client(
        [FakeResponse(401), FakeResponse(200, {"ok": 1})], env=envs, on_key_error="wait"
    )
    assert client.match("americas", "NA1_1") == {"ok": 1}
    assert [c["headers"]["X-Riot-Token"] for c in session.calls] == ["old", "new"]
    assert clock.sleeps == [60.0]
    assert client.key_status == "ok"


def test_429_uses_retry_after():
    client, _, clock = make_client(
        [FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, {"x": 1})]
    )
    assert client.match("americas", "NA1_1") == {"x": 1}
    assert clock.sleeps == [7.0]
    assert client.stats()["rate_limited"] == 1


def test_429_default_wait():
    client, _, clock = make_client([FakeResponse(429), FakeResponse(200)])
    client.match("americas", "NA1_1")
    assert clock.sleeps == [10.0]


def test_429_raises_after_max_retries():
    client, session, clock = make_client(
        [FakeResponse(429, headers={"Retry-After": "3"})] * 2, max_429_retries=1
    )
    with pytest.raises(RateLimitedError) as exc:
        client.match("americas", "NA1_1")
    assert exc.value.retry_after_s == 3.0
    assert len(session.calls) == 2
    assert clock.sleeps == [3.0]


def test_5xx_backoff_sequence():
    client, session, clock = make_client([FakeResponse(503)] * 5)
    with pytest.raises(RiotUnavailableError):
        client.match("americas", "NA1_1")
    assert clock.sleeps == [2.0, 4.0, 8.0, 16.0]
    assert len(session.calls) == 5
    assert client.stats()["server_errors"] == 5


def test_5xx_then_success():
    client, _, clock = make_client(
        [FakeResponse(500), FakeResponse(502), FakeResponse(200, {"ok": 1})]
    )
    assert client.match("americas", "NA1_1") == {"ok": 1}
    assert clock.sleeps == [2.0, 4.0]


def test_connection_error_counts_as_unavailable():
    import requests

    client, _, _ = make_client([requests.ConnectionError()] * 5)
    with pytest.raises(RiotUnavailableError):
        client.match("americas", "NA1_1")


def test_404():
    client, _, clock = make_client([FakeResponse(404)])
    with pytest.raises(NotFoundError):
        client.match("americas", "NA1_1")
    assert clock.sleeps == []


def test_other_status_is_riot_error():
    client, _, _ = make_client([FakeResponse(400)])
    with pytest.raises(RiotError):
        client.match("americas", "NA1_1")


def test_headers_feed_the_limiter():
    client, _, _ = make_client(
        [
            FakeResponse(
                200,
                headers={
                    "X-App-Rate-Limit": "20:1,100:120",
                    "X-App-Rate-Limit-Count": "1:1,60:120",
                },
            )
        ]
    )
    client.match("europe", "EUW1_1")
    assert limiter_for("europe").count(120) == 60


# ---- URLs ----


def url_of(call, *args, **kwargs):
    client, session, _ = make_client([FakeResponse(200, [])])
    getattr(client, call)(*args, **kwargs)
    c = session.calls[0]
    return c["url"], c["params"]


def test_urls():
    base = "https://na1.api.riotgames.com/lol/league/v4"
    assert url_of("apex_league", "na1", "CHALLENGER") == (
        f"{base}/challengerleagues/by-queue/RANKED_SOLO_5x5",
        None,
    )
    assert url_of("apex_league", "na1", "GRANDMASTER")[0].endswith(
        "/grandmasterleagues/by-queue/RANKED_SOLO_5x5"
    )
    assert url_of("apex_league", "na1", "MASTER")[0].endswith(
        "/masterleagues/by-queue/RANKED_SOLO_5x5"
    )
    assert url_of("league_entries", "na1", "DIAMOND", "II", page=3) == (
        f"{base}/entries/RANKED_SOLO_5x5/DIAMOND/II",
        {"page": 3},
    )
    assert url_of("match_ids", "americas", "pu-uid", start_time=123, count=10) == (
        "https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/pu-uid/ids",
        {"queue": 420, "start": 0, "count": 10, "startTime": 123},
    )
    assert url_of("match_ids", "europe", "p")[1] == {"queue": 420, "start": 0, "count": 100}
    assert (
        url_of("match", "europe", "EUW1_5")[0]
        == "https://europe.api.riotgames.com/lol/match/v5/matches/EUW1_5"
    )
    assert url_of("timeline", "asia", "KR_5")[0] == (
        "https://asia.api.riotgames.com/lol/match/v5/matches/KR_5/timeline"
    )
    assert url_of("account_by_riot_id", "americas", "Me", "NA1")[0] == (
        "https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Me/NA1"
    )


def test_riot_id_is_encoded():
    url, _ = url_of("account_by_riot_id", "americas", "Hide on bush", "한국")
    assert url.endswith("/by-riot-id/Hide%20on%20bush/%ED%95%9C%EA%B5%AD")
    url, _ = url_of("account_by_riot_id", "europe", "a/b#c", "T?")
    assert url.endswith("/by-riot-id/a%2Fb%23c/T%3F")


def test_rank_by_puuid():
    entries = [
        {"queueType": "RANKED_FLEX_SR", "tier": "GOLD"},
        {"queueType": "RANKED_SOLO_5x5", "tier": "EMERALD"},
    ]
    client, session, _ = make_client([FakeResponse(200, entries), FakeResponse(200, entries[:1])])
    assert client.rank_by_puuid("na1", "abc")["tier"] == "EMERALD"
    assert (
        session.calls[0]["url"]
        == "https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/abc"
    )
    assert client.rank_by_puuid("na1", "abc") is None
