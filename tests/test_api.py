import json

import pytest
from fastapi.testclient import TestClient

from lolreview import api, riot
from lolreview import app as app_mod
from lolreview.cache import Cache
from lolreview.demo import DemoRiot
from lolreview.schemas import Review

GRADES = {"!!": 0, "!": 0, "?": 0, "??": 0}
MID = "NA1_9000000001"
P = 4  # "Me" in the first synthetic game
SECRET = "RGAPI-secret-key"


class FakeModel:
    def __init__(self, version="v1", kind="trained"):
        self.kind = kind
        self.version = version
        self.trained_at = "2026-10-01T00:00:00Z"
        self.patches = ["26.18", "26.19"]
        self.metrics = {"auc": 0.8, "patches": ["26.19"]}
        self.changed = False


def minimal_review(match_id, p, tier, model, tier_note):
    return Review.model_validate(
        {
            "match": {
                "match_id": match_id,
                "platform": "na1",
                "patch": "26.19",
                "ddragon_version": "26.19.1",
                "started_at": "2026-10-01T00:00:00Z",
                "duration_s": 1865,
                "result": "win",
                "surrender": False,
                "my_side": "blue",
                "tier_used": tier,
                "tier_note": tier_note,
                "model": {"kind": model.kind, "version": model.version},
                "patch_in_training": True,
            },
            "players": [],
            "buildings": [],
            "curve": [{"t": 0, "p": 0.5}],
            "moments": [],
            "snapshots": [],
            "summary": {"me": GRADES, "team": GRADES, "biggest_id": "m0"},
        }
    )


class CountingRiot(DemoRiot):
    """DemoRiot that counts calls and can raise or hand out ranks."""

    def __init__(self, ranks=None, error=None):
        super().__init__()
        self.calls = []
        self.error = error
        self.ranks = ranks  # puuid -> tier, or None for the default demo behaviour

    def _hit(self, name):
        self.calls.append(name)
        if self.error:
            raise self.error

    def account_by_riot_id(self, *a):
        self._hit("account")
        return super().account_by_riot_id(*a)

    def rank_by_puuid(self, platform, puuid):
        self._hit("rank")
        if self.ranks is None:
            return super().rank_by_puuid(platform, puuid)
        tier = self.ranks.get(puuid)
        return (
            {"queueType": "RANKED_SOLO_5x5", "tier": tier, "rank": "I", "leaguePoints": 0}
            if tier
            else None
        )

    def match_ids(self, *a, **k):
        self._hit("ids")
        return super().match_ids(*a, **k)

    def match(self, *a):
        self._hit("match")
        return super().match(*a)

    def timeline(self, *a):
        self._hit("timeline")
        return super().timeline(*a)


@pytest.fixture
def env(tmp_path, monkeypatch):
    model = FakeModel()
    built = []

    def fake_build(match, timeline, p, tier, mdl, champions, version, tier_note):
        built.append({"tier": tier, "note": tier_note, "champions": champions, "version": version})
        return minimal_review(match["metadata"]["matchId"], p, tier, mdl, tier_note)

    monkeypatch.setattr(api, "_load_model", lambda models_dir: model)
    monkeypatch.setattr(api, "_build_review", fake_build)
    monkeypatch.setattr(api, "_models_changed", lambda models_dir, current: current.changed)
    monkeypatch.setattr(api, "read_env", lambda: {"RIOT_API_KEY": SECRET})

    class Env:
        pass

    e = Env()
    e.model, e.built, e.tmp = model, built, tmp_path

    def make(client=None, demo=True, dev=False):
        e.client = client or CountingRiot()
        e.app = api.create_app(demo=demo, dev=dev, cache=Cache(tmp_path / "c.db"), client=e.client)
        return TestClient(e.app, raise_server_exceptions=False)

    e.make = make
    return e


def error_of(resp):
    return resp.json()["error"]


def test_health(env):
    r = env.make().get("/api/health")
    assert r.status_code == 200
    assert r.json()["riot_key"] == "ok"
    assert r.json()["model"] == {
        "kind": "trained",
        "version": "v1",
        "trained_at": "2026-10-01T00:00:00Z",
        "patches": ["26.18", "26.19"],
    }


def test_health_key_states(env, monkeypatch):
    client = CountingRiot()
    client.key_status = "ok"
    c = env.make(client, demo=False)
    assert c.get("/api/health").json()["riot_key"] == "ok"
    client.key_status = "expired"
    assert c.get("/api/health").json()["riot_key"] == "expired"
    monkeypatch.setattr(api, "read_env", lambda: {})
    assert c.get("/api/health").json()["riot_key"] == "missing"


def test_player_happy_path(env):
    c = env.make()
    r = c.get("/api/player/na1/Me/NA1")
    assert r.status_code == 200
    body = r.json()
    assert body["riot_id"] == "Me#NA1"
    assert body["platform"] == "na1"
    assert body["rank"] == {"tier": "GOLD", "division": "III", "lp": 47}
    assert [g["match_id"] for g in body["games"]] == [
        "NA1_9000000004",
        "NA1_9000000003",
        "NA1_9000000002",
        "NA1_9000000001",
    ]
    assert body["next_start"] is None
    assert [g["result"] for g in body["games"]][0] == "remake"
    g = body["games"][-1]
    assert (g["champion"], g["role"], g["participant_id"]) == ("Ahri", "MIDDLE", 4)
    assert g["patch"] == "26.19"
    assert g["started_at"].endswith("Z")
    assert not any(x["reviewed"] for x in body["games"])


def test_player_is_cached(env):
    c = env.make()
    c.get("/api/player/na1/me/na1")
    first = len(env.client.calls)
    assert c.get("/api/player/na1/Me/NA1").status_code == 200
    assert len(env.client.calls) == first


def test_next_start_and_paging(env):
    c = env.make()
    body = c.get("/api/player/na1/Me/NA1?start=0&count=2").json()
    assert [g["match_id"][-1] for g in body["games"]] == ["4", "3"]
    assert body["next_start"] == 2
    body = c.get("/api/player/na1/Me/NA1?start=2&count=2").json()
    assert [g["match_id"][-1] for g in body["games"]] == ["2", "1"]
    assert body["next_start"] == 4  # a full page: there may be more
    body = c.get("/api/player/na1/Me/NA1?start=4&count=2").json()
    assert body["games"] == []
    assert body["next_start"] is None


def test_player_not_found(env):
    r = env.make().get("/api/player/na1/Nobody/NA1")
    assert r.status_code == 404
    assert error_of(r)["code"] == "riot_id_not_found"
    assert "Nobody#NA1" in error_of(r)["message"]


def test_review_happy_path_and_cache(env):
    c = env.make()
    r = c.get(f"/api/review/{MID}?p={P}")
    assert r.status_code == 200
    assert r.json()["match"]["match_id"] == MID
    assert r.json()["match"]["tier_used"] == "GOLD"
    assert len(env.built) == 1
    assert env.built[0]["version"] == "26.19.1"
    assert env.built[0]["champions"][103] == ("Ahri", "Ahri")
    calls = len(env.client.calls)
    r2 = c.get(f"/api/review/{MID}?p={P}")
    assert r2.json() == r.json()
    assert len(env.built) == 1
    assert len(env.client.calls) == calls


def test_reviewed_flag_follows_model_version(env):
    c = env.make()
    c.get(f"/api/review/{MID}?p={P}")
    games = c.get("/api/player/na1/Me/NA1").json()["games"]
    assert [g["reviewed"] for g in games] == [False, False, False, True]
    env.model.version = "v2"
    env.model.changed = True
    games = c.get("/api/player/na1/Me/NA1").json()["games"]
    assert not any(g["reviewed"] for g in games)


def test_model_version_change_recomputes(env):
    c = env.make()
    c.get(f"/api/review/{MID}?p={P}")
    env.model.version = "v2"
    env.model.changed = True
    r = c.get(f"/api/review/{MID}?p={P}")
    assert r.json()["match"]["model"]["version"] == "v2"
    assert len(env.built) == 2
    c.get(f"/api/review/{MID}?p={P}")
    assert len(env.built) == 2


def test_tier_falls_back_to_median_of_others(env):
    c = env.make()
    match = env.client.match("americas", MID)
    others = [x["puuid"] for x in match["info"]["participants"] if x["participantId"] != P]
    tiers = ["IRON", "GOLD", "GOLD", "PLATINUM", "DIAMOND"]
    ranks = dict(zip(others, tiers, strict=False))
    client = CountingRiot(ranks=ranks)
    c = env.make(client)
    r = c.get(f"/api/review/{MID}?p={P}")
    assert r.status_code == 200
    assert env.built[0]["tier"] == "GOLD"
    assert "unranked" in env.built[0]["note"].lower()
    assert client.calls.count("rank") == 10
    # cached: another participant's review asks for no more ranks of those players
    c.get(f"/api/review/{MID}?p={P}")
    assert client.calls.count("rank") == 10


def test_tier_silver_when_nobody_ranked(env):
    c = env.make(CountingRiot(ranks={}))
    assert c.get(f"/api/review/{MID}?p={P}").status_code == 200
    assert env.built[0]["tier"] == "SILVER"
    assert "Nobody" in env.built[0]["note"]


def test_own_rank_needs_no_note(env):
    env.make().get(f"/api/review/{MID}?p={P}")
    assert env.built[0]["note"] is None


def test_remake_is_unsupported(env):
    r = env.make().get("/api/review/NA1_9000000004?p=5")
    assert r.status_code == 422
    assert error_of(r)["code"] == "unsupported_queue"
    assert env.built == []


def test_other_queue_is_unsupported(env):
    c = env.make()
    match = json.loads(json.dumps(env.client.match("americas", MID)))
    match["info"]["queueId"] = 450
    env.client.match = lambda cluster, mid: match
    r = c.get(f"/api/review/{MID}?p={P}")
    assert r.status_code == 422
    assert error_of(r)["code"] == "unsupported_queue"


def test_review_not_found(env):
    c = env.make()
    r = c.get("/api/review/NA1_1?p=1")
    assert (r.status_code, error_of(r)["code"]) == (404, "match_not_found")
    r = c.get(f"/api/review/{MID}?p=99")
    assert (r.status_code, error_of(r)["code"]) == (404, "match_not_found")


def test_review_cache_hit_is_fast(env):
    import time

    c = env.make()
    c.get(f"/api/review/{MID}?p={P}")
    t = time.perf_counter()
    c.get(f"/api/review/{MID}?p={P}")
    assert time.perf_counter() - t < 0.2


def test_model_endpoint(env):
    c = env.make()
    assert c.get("/api/model").json() == {"auc": 0.8, "patches": ["26.19"]}
    env.model.kind = "stub"
    r = c.get("/api/model")
    assert (r.status_code, error_of(r)["code"]) == (404, "model_missing")


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (riot.KeyExpiredError("x"), 401, "key_expired"),
        (riot.KeyMissingError("x"), 401, "key_expired"),
        (riot.RateLimitedError(8), 429, "rate_limited"),
        (riot.RiotUnavailableError("x"), 503, "riot_unavailable"),
        (riot.NotFoundError("x"), 404, "match_not_found"),
        (riot.RiotError("x"), 500, "internal"),
        (RuntimeError(SECRET), 500, "internal"),
    ],
)
def test_error_mapping(env, exc, status, code):
    c = env.make(CountingRiot(error=exc), demo=False)
    r = c.get(f"/api/review/{MID}?p={P}")
    assert r.status_code == status
    assert error_of(r)["code"] == code
    assert SECRET not in r.text
    if code == "rate_limited":
        assert error_of(r)["retry_after_s"] == 8
    r = c.get("/api/player/na1/Me/NA1")
    if isinstance(exc, riot.NotFoundError):
        status, code = 404, "riot_id_not_found"
    assert (r.status_code, error_of(r)["code"]) == (status, code)


def test_missing_key_message(env):
    c = env.make(CountingRiot(error=riot.KeyMissingError("x")))
    msg = error_of(c.get("/api/player/na1/Me/NA1"))["message"]
    assert "No Riot API key" in msg


def test_no_key_in_any_body(env):
    c = env.make()
    for url in ["/api/health", "/api/player/na1/Me/NA1", f"/api/review/{MID}?p={P}", "/api/model"]:
        assert SECRET not in c.get(url).text


def test_gzip(env):
    c = env.make()
    r = c.get("/api/model", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    r = c.get("/api/player/na1/Me/NA1", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


def test_cors_only_in_dev(env):
    origin = {"Origin": "http://localhost:5173"}
    dev = env.make(dev=True).get("/api/health", headers=origin)
    assert dev.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = env.make(dev=True).get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers
    prod = env.make(dev=False).get("/api/health", headers=origin)
    assert "access-control-allow-origin" not in prod.headers


def test_spa_fallback(env, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>ui</html>")
    (dist / "assets" / "a.js").write_text("console.log(1)")
    app = app_mod.build_app(
        demo=True, dist=dist, cache=Cache(tmp_path / "c.db"), client=CountingRiot()
    )
    c = TestClient(app)
    assert c.get("/").text == "<html>ui</html>"
    assert c.get("/review/NA1_1/4").text == "<html>ui</html>"
    assert c.get("/assets/a.js").text == "console.log(1)"
    assert c.get("/../../etc/passwd").text == "<html>ui</html>"
    assert c.get("/api/health").json()["riot_key"] == "ok"
    r = c.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_missing_dist_explains_build(env, tmp_path):
    app = app_mod.build_app(
        demo=True, dist=tmp_path / "none", cache=Cache(tmp_path / "c.db"), client=CountingRiot()
    )
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "npm ci" in r.text
