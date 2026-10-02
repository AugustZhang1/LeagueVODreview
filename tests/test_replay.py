import json

import pytest
import requests
from fastapi.testclient import TestClient

from lolreview import api, replay
from lolreview.cache import Cache
from lolreview.ddragon import DataDragon
from lolreview.demo import FIXTURES, DemoRiot

MID = "NA1_9000000001"


@pytest.fixture
def match():
    return json.loads((FIXTURES / f"{MID}.match.json").read_text(encoding="utf-8"))


@pytest.fixture
def cert(tmp_path):
    path = tmp_path / "riotgames.pem"
    path.write_text("not a real certificate")
    return path


def live_players(match):
    return [
        {"championName": n, "rawChampionName": f"game_character_displayname_{n}"}
        for n in (p["championName"] for p in match["info"]["participants"])
    ]


class FakeResponse:
    def __init__(self, data=None, status=200):
        self.data, self.status = data, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(str(self.status))

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, players=None, error=None):
        self.players, self.error = players, error
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        if self.error:
            raise self.error
        return FakeResponse(self.players)

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        if self.error:
            raise self.error
        return FakeResponse({})


def client(cert, **kw):
    session = FakeSession(**kw)
    return replay.ReplayClient(session, cert), session


def test_unreachable(match, cert):
    c, _ = client(cert, error=requests.ConnectionError("refused"))
    s = c.status(match)
    assert (s.available, s.reason) == (False, replay.REASON_OPEN)


def test_same_game(match, cert):
    c, session = client(cert, players=live_players(match))
    s = c.status(match, newest_patch="26.19")
    assert (s.available, s.reason) == (True, None)
    method, url, kw = session.calls[0]
    assert (method, url) == ("GET", "https://127.0.0.1:2999/liveclientdata/playerlist")
    assert kw["timeout"] == 0.5


def test_display_names_also_match(match, cert):
    players = [{"championName": p["championName"]} for p in match["info"]["participants"]]
    c, _ = client(cert, players=players)
    assert c.status(match).available


def test_different_game(match, cert):
    players = live_players(match)
    players[0] = {"championName": "Teemo", "rawChampionName": "game_character_displayname_Teemo"}
    c, _ = client(cert, players=players)
    s = c.status(match)
    assert (s.available, s.reason) == (False, replay.REASON_OTHER_GAME)
    c, _ = client(cert, players=live_players(match)[:5])
    assert c.status(match).reason == replay.REASON_OTHER_GAME


def test_old_patch_needs_no_request(match, cert):
    c, session = client(cert, players=live_players(match))
    s = c.status(match, newest_patch="26.20")
    assert (s.available, s.reason) == (False, replay.REASON_OLD_PATCH)
    assert session.calls == []
    assert c.status(match, newest_patch="26.19").available


def test_missing_certificate(match, tmp_path):
    c, session = client(tmp_path / "nope.pem", players=live_players(match))
    s = c.status(match)
    assert not s.available
    assert "riotgames.pem" in s.reason and replay.CERT_URL in s.reason
    with pytest.raises(replay.ReplayUnavailable):
        c.seek(60)
    assert session.calls == []


@pytest.mark.parametrize(("t", "expected"), [(100, 95), (5, 0), (3, 0), (0, 0), (12.5, 7.5)])
def test_seek_body(cert, t, expected):
    c, session = client(cert)
    c.seek(t)
    method, url, kw = session.calls[0]
    assert (method, url) == ("POST", "https://127.0.0.1:2999/replay/playback")
    assert kw["json"] == {"time": expected, "paused": False}
    assert kw["timeout"] == 0.5


def test_seek_failure_is_unavailable(cert):
    c, _ = client(cert, error=requests.ConnectionError("refused"))
    with pytest.raises(replay.ReplayUnavailable) as e:
        c.seek(60)
    assert e.value.reason == replay.REASON_OPEN


def test_tls_settings(cert):
    session = replay.make_session(cert)
    assert session.verify == str(cert)
    adapter = session.get_adapter(replay.BASE)
    assert isinstance(adapter, replay._LocalAdapter)
    assert adapter.poolmanager.connection_pool_kw["assert_hostname"] is False
    # The chain check is on: the pool uses the default (required) cert mode.
    assert adapter.poolmanager.connection_pool_kw.get("cert_reqs", "CERT_REQUIRED") != "CERT_NONE"
    assert replay.ReplayClient(cert_path=cert)._http().verify is not False


# --- API endpoints


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "read_env", lambda: {})

    def make(demo, versions=("26.19.1", "26.18.1")):
        cache = Cache(tmp_path / "c.db")
        dd = DataDragon(cache, fetch=lambda url: list(versions))
        app = api.create_app(demo=demo, cache=cache, client=DemoRiot(), ddragon=dd)
        return TestClient(app, raise_server_exceptions=False)

    return make


def test_demo_status_and_seek(make_client):
    c = make_client(demo=True)
    r = c.get("/api/replay/status", params={"match_id": MID})
    assert r.json() == {"available": False, "reason": "Replays aren't available in demo mode"}
    r = c.post("/api/replay/seek", json={"match_id": MID, "t": 60})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "replay_unavailable"
    assert "demo mode" in r.json()["error"]["message"]


def test_status_endpoint(make_client, monkeypatch, match):
    seen = []

    def fake_status(m, newest_patch=None):
        seen.append((m["metadata"]["matchId"], newest_patch))
        return replay.ReplayStatus(available=True)

    monkeypatch.setattr(replay, "status", fake_status)
    c = make_client(demo=False)
    r = c.get("/api/replay/status", params={"match_id": MID})
    assert r.json() == {"available": True, "reason": None}
    assert seen == [(MID, "26.19")]
    assert c.get("/api/replay/status", params={"match_id": "NA1_1"}).status_code == 404
    assert c.get("/api/replay/status", params={"match_id": "XX_1"}).status_code == 404


def test_seek_endpoint(make_client, monkeypatch):
    sought = []
    avail = {"v": True}
    monkeypatch.setattr(
        replay,
        "status",
        lambda m, newest_patch=None: replay.ReplayStatus(
            available=avail["v"], reason=None if avail["v"] else "nope"
        ),
    )
    monkeypatch.setattr(replay, "seek", sought.append)
    c = make_client(demo=False)
    r = c.post("/api/replay/seek", json={"match_id": MID, "t": 321.5})
    assert (r.status_code, r.json()) == (200, {"ok": True})
    assert sought == [321.5]
    avail["v"] = False
    r = c.post("/api/replay/seek", json={"match_id": MID, "t": 1})
    assert r.status_code == 409
    assert r.json()["error"] == {
        "code": "replay_unavailable",
        "message": "nope",
        "retry_after_s": None,
    }
    assert sought == [321.5]
