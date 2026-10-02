"""Demo mode end to end, with the real review engine and placeholder model (nothing faked)."""

import pytest
from fastapi.testclient import TestClient

from lolreview import api
from lolreview.cache import Cache


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "read_env", lambda: {})
    app = api.create_app(demo=True, cache=Cache(tmp_path / "c.db"))
    return TestClient(app, raise_server_exceptions=False)


def test_player_then_review(client):
    r = client.get("/api/player/na1/Me/NA1")
    assert r.status_code == 200, r.text
    games = r.json()["games"]
    assert games and all(not g["reviewed"] for g in games)
    assert [g["result"] for g in games].count("loss") == 1
    assert [g["result"] for g in games].count("win") == 2

    for g in games:
        r = client.get(f"/api/review/{g['match_id']}", params={"p": g["participant_id"]})
        if g["result"] == "remake":
            assert r.status_code == 422
            assert r.json()["error"]["code"] == "unsupported_queue"
            continue
        assert r.status_code == 200, r.text
        review = r.json()
        assert review["match"]["model"]["kind"] == "stub"
        assert review["curve"][-1]["p"] == (1.0 if g["result"] == "win" else 0.0)
        assert review["match"]["result"] == g["result"]
        graded = [m for m in review["moments"] if m["grade"]]
        assert any(m["delta"] > 0 for m in graded)
        if g["result"] == "loss":
            assert review["match"]["my_side"] == "red"
            assert any(m["delta"] < 0 for m in graded)
        assert review["moments"] and review["snapshots"]

    r = client.get("/api/player/na1/Me/NA1")
    assert all(g["reviewed"] for g in r.json()["games"] if g["result"] != "remake")


def test_health_and_model_in_demo(client):
    h = client.get("/api/health").json()
    assert h["model"]["kind"] == "stub"
    r = client.get("/api/model")
    assert r.status_code == 404 and r.json()["error"]["code"] == "model_missing"
