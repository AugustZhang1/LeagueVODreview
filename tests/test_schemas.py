import pytest

from lolreview import api, schemas

GRADES = {"!!": 0, "!": 1, "?": 0, "??": 0}


def team_state():
    return {
        "kills": 1,
        "gold": 2500,
        "towers": 0,
        "dragons": ["Infernal"],
        "soul": None,
        "grubs": 0,
        "heralds": 0,
        "barons": 0,
        "buff": {"kind": "baron", "ends_in_s": 90},
    }


def player_state(pid):
    return {
        "participant_id": pid, "x": 100, "y": 200.5, "pos_age_s": 0, "level": 3,
        "k": 1, "d": 0, "a": 0, "cs": 20, "gold": 800, "items": [1055] + [None] * 5,
        "trinket": 3340, "respawn_in_s": 0,
    }  # fmt: skip


def minimal_review():
    return {
        "match": {
            "match_id": "NA1_1", "platform": "NA1", "patch": "26.19", "ddragon_version": "26.19.1",
            "started_at": "2026-09-28T01:05:11Z", "duration_s": 1865, "result": "win",
            "surrender": False, "my_side": "blue", "tier_used": "GOLD", "tier_note": None,
            "model": {"kind": "stub", "version": "abc123"}, "patch_in_training": False,
        },
        "players": [
            {
                "participant_id": 1, "riot_id": "Me#NA1", "champion": "MonkeyKing",
                "champion_name": "Wukong", "role": "JUNGLE", "team": "ally", "is_me": True,
            }
        ],
        "buildings": [{"id": "ally_top_outer", "team": "ally", "kind": "tower", "x": 1, "y": 2}],
        "curve": [{"t": 0, "p": 0.5}, {"t": 1865, "p": 1}],
        "moments": [
            {
                "id": "m1", "t_start": 200, "t_end": 215, "p_before": 0.5, "p_after": 0.56,
                "delta": 0.06, "grade": "!", "title": "Wukong killed Zed", "zone": "mid lane",
                "involves_me": True,
                "events": [
                    {"t": 205, "team": "ally", "kind": "kill", "killer": 1, "victim": 6,
                     "assists": [2], "x": 7000, "y": 7000}
                ],
            }
        ],
        "snapshots": [
            {
                "t": 0, "players": [player_state(1)],
                "teams": {"ally": team_state(), "enemy": team_state()},
                "buildings_down": [],
                "recent_kills": [{"x": 1, "y": 2, "team": "ally", "age_s": 3}],
            }
        ],
        "summary": {"me": GRADES, "team": GRADES, "biggest_id": "m1"},
    }  # fmt: skip


def test_minimal_review_validates():
    review = schemas.Review.model_validate(minimal_review())
    dumped = review.model_dump(mode="json", by_alias=True)
    assert dumped["summary"]["me"] == GRADES
    assert dumped["moments"][0]["grade"] == "!"


def test_review_rejects_bad_literals():
    bad = minimal_review()
    bad["moments"][0]["grade"] = "!!!"
    with pytest.raises(ValueError):
        schemas.Review.model_validate(bad)


def test_grade_counts_aliases():
    counts = schemas.GradeCounts.model_validate({"!!": 2, "!": 1, "?": 0, "??": 3})
    assert counts.blunder == 3 and counts.great == 2


def test_health_and_player_games():
    schemas.Health.model_validate({"riot_key": "ok", "model": {"kind": "stub", "version": "x"}})
    schemas.PlayerGames.model_validate(
        {
            "puuid": "p", "riot_id": "Me#NA1", "platform": "na1",
            "rank": {"tier": "GOLD", "division": "III", "lp": 40},
            "games": [
                {
                    "match_id": "NA1_1", "participant_id": 4, "champion": "Ahri", "role": "MIDDLE",
                    "result": "win", "k": 1, "d": 2, "a": 3, "cs": 200, "duration_s": 1800,
                    "started_at": "2026-09-28T01:05:11Z", "patch": "26.19",
                    "ddragon_version": "26.19.1", "reviewed": False,
                }
            ],
            "next_start": None,
        }
    )  # fmt: skip


def test_model_metrics_allows_extra():
    metrics = schemas.ModelMetrics.model_validate({"auc": 0.8, "anything": [1, 2]})
    assert metrics.model_dump()["auc"] == 0.8


def test_error_response_shape():
    body = schemas.ErrorResponse.model_validate(
        {"error": {"code": "rate_limited", "message": "slow down", "retry_after_s": 8}}
    )
    assert body.model_dump() == {
        "error": {"code": "rate_limited", "message": "slow down", "retry_after_s": 8}
    }


def test_openapi_paths():
    paths = api.app.openapi()["paths"]
    assert set(paths) == {
        "/api/health",
        "/api/player/{platform}/{name}/{tag}",
        "/api/review/{match_id}",
        "/api/patterns",
        "/api/model",
        "/api/replay/status",
        "/api/replay/seek",
    }
    params = {p["name"] for p in paths["/api/player/{platform}/{name}/{tag}"]["get"]["parameters"]}
    assert {"start", "count"} <= params
    assert "p" in {p["name"] for p in paths["/api/review/{match_id}"]["get"]["parameters"]}


def test_committed_openapi_is_current():
    import json
    from pathlib import Path

    committed = json.loads((Path(__file__).parent.parent / "frontend" / "openapi.json").read_text())
    assert committed == api.app.openapi()
