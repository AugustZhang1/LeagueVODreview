import json
import urllib.request

import pytest

from lolreview import status
from lolreview.config import load_config
from lolreview.state import State, state_path

NOW = 1_800_000_000.0


def snapshot(**over):
    snap = {
        "now": NOW,
        "key": "ok",
        "clusters": [
            {"platform": "na1", "tier": "MASTER", "division": "I", "pass_no": 2,
             "games": 41200, "per_hour": 1302.4, "pending": 12, "key": "ok"},
            {"platform": "kr", "tier": "DIAMOND", "division": "II", "pass_no": 1,
             "games": 39870, "per_hour": 1310.0, "pending": 3, "key": "ok"},
        ],
        "tiers": [{"tier": "CHALLENGER", "pct": 100.0}, {"tier": "MASTER", "pct": 61.0}],
        "last_hour": {"requests": 4000, "http_429": 7, "http_5xx": 3},
        "last_batch": NOW - 120,
        "data": {"games": 81070, "rows": 19_200_000, "bytes": 1.4 * 1024**3,
                 "blue_win_rate": 0.506, "avg_length_s": 29 * 60 + 12,
                 "patches": [("26.19", 47000, 0.58), ("26.18", 34070, 0.42)]},
        "upload": {"uploaded_at": "2027-01-15T07:20:00+00:00", "games": 98000},
        "errors": [(NOW - 600, "kr: 503 on /lol/match/v5/matches/KR_1/timeline")],
    }  # fmt: skip
    snap.update(over)
    return snap


def test_render_has_every_section():
    html = status.render(snapshot())
    for text in [
        "Health", "Per cluster", "By tier", "Data", "Kaggle", "Recent errors",
        "NA1", "Master", "41,200", "1,302/h", "Diamond II", "61%", "done",
        "26.19 (58%)", "26.18 (42%)", "19,200,000", "1.4 GB", "50.6%", "29:12",
        "2 min ago", "98,000 games", "503 on /lol/match", "7", 'http-equiv="refresh"',
    ]:  # fmt: skip
        assert text in html, text
    assert "Key expired" not in html
    assert "<script" not in html


def test_render_expired_banner():
    html = status.render(snapshot(key="expired"))
    assert "Key expired" in html
    assert "sed -i" in html and "RIOT_API_KEY=NEW_KEY" in html


def test_render_empty_and_escapes():
    snap = snapshot(
        clusters=[], upload=None, last_batch=None, errors=[(NOW, "<b>x</b>")],
        data={"games": 0, "rows": 0, "bytes": 0, "blue_win_rate": None,
              "avg_length_s": None, "patches": []},
    )  # fmt: skip
    html = status.render(snap)
    assert "No upload yet" in html and "none yet" in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html


def make_state(tmp_path):
    cfg = load_config()
    st = State(state_path(tmp_path, "na1"))
    st.meta_set("tier", "GOLD")
    st.meta_set("division", "II")
    st.meta_set("tier_idx", 6)
    st.add_matches(["a"], "GOLD", NOW)
    batch = {
        "file": "na1/26.19/v1/part-00001.parquet", "patch": "26.19", "version": 1,
        "games": 10, "rows": 500, "bytes": 2048, "blue_wins": 6, "duration_s": 18000,
    }  # fmt: skip
    st.record_batches([batch], [], now=NOW - 60)
    st.add_counts(int(NOW // 60) - 5, 100, 4, 2)
    st.add_error("na1: 503 on /x", NOW - 30)
    st.close()
    return cfg


def test_build_snapshot(tmp_path):
    cfg = make_state(tmp_path)
    (tmp_path / "last_upload.json").write_text(json.dumps({"games": 5, "uploaded_at": "x"}))
    snap = status.build_snapshot(
        tmp_path, ["na1", "euw1"], lambda: {"na1": "expired"}, cfg, now=NOW
    )
    assert snap["key"] == "expired"
    assert len(snap["clusters"]) == 1  # euw1 has no state file yet
    c = snap["clusters"][0]
    assert (c["games"], c["pending"], c["tier"]) == (10, 1, "GOLD")
    assert snap["last_hour"] == {"requests": 100, "http_429": 4, "http_5xx": 2}
    assert snap["data"]["blue_win_rate"] == pytest.approx(0.6)
    assert snap["data"]["avg_length_s"] == pytest.approx(1800)
    assert snap["data"]["patches"] == [("26.19", 10, 1.0)]
    tiers = {t["tier"]: t["pct"] for t in snap["tiers"]}
    assert tiers["CHALLENGER"] == 100.0 and tiers["SILVER"] == 0.0
    html = status.render(snap)
    assert "Key expired" in html


def test_server_get(tmp_path):
    cfg = make_state(tmp_path)
    server = status.serve(tmp_path, ["na1"], 0, None, cfg)
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as r:
            assert r.status == 200
            assert "Crawl progress" in r.read().decode()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz") as r:
            assert r.read() == b"ok"
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope")
    finally:
        server.shutdown()
        server.server_close()
