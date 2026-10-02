import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "fetch_samples.py"
spec = importlib.util.spec_from_file_location("fetch_samples", SCRIPT)
fetch_samples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_samples)


def test_build_report_on_synthetic(synthetic_games):
    report = fetch_samples.build_report(synthetic_games)
    assert "Games: 4" in report
    for heading in ("CHAMPION_KILL", "BUILDING_KILL", "ELITE_MONSTER_KILL", "GAME_END"):
        assert f"### {heading}" in report
    assert "Fields:" in report and "Example: `" in report
    assert "monsterSubType:" in report and "AIR_DRAGON" in report
    assert "- DRAGON_SOUL_GIVEN: yes" in report
    assert "- GAME_END: yes" in report
    assert "- Rift Herald: yes" in report
    assert "- Atakhan: yes" in report
    assert "- Unknown event types: none" in report
    assert "26.19.712.4021" in report
    assert "## Position bounds" in report and "x: " in report
    assert "killer team" in report
    assert "- DRAGON/AIR_DRAGON:" in report
    assert "Earliest objective kill" in report and "ELDER_DRAGON killed at" in report


def test_build_report_flags_unknown_and_absent(synthetic_games):
    match, timeline = synthetic_games[3]  # remake: no objectives
    timeline = json.loads(json.dumps(timeline))
    timeline["info"]["frames"][-1]["events"].append({"type": "NEW_THING", "timestamp": 1, "x": 1})
    report = fetch_samples.build_report([(match, timeline)])
    assert "Unknown event types: NEW_THING" in report
    assert "- DRAGON_SOUL_GIVEN: no" in report
    assert "- Atakhan: no" in report
    assert "No objective kills." in report


class FakeClient:
    def __init__(self, games):
        self.by_id = {m["metadata"]["matchId"]: (m, t) for m, t in games}

    def apex_league(self, platform, tier):
        return {"entries": [{"puuid": "a", "leaguePoints": 5}, {"puuid": "b", "leaguePoints": 9}]}

    def match_ids(self, cluster, puuid, queue=420, start_time=None, start=0, count=100):
        return list(self.by_id)[:count]

    def match(self, cluster, match_id):
        return self.by_id[match_id][0]

    def timeline(self, cluster, match_id):
        return self.by_id[match_id][1]


def test_collect_and_save(synthetic_games, tmp_path):
    games = fetch_samples.collect_games(FakeClient(synthetic_games), "na1", 3)
    assert len(games) == 3
    ids = [m["metadata"]["matchId"] for m, _ in games]
    assert len(set(ids)) == 3
    fetch_samples.save_games(games[:2], tmp_path)
    assert len(list(tmp_path.glob("*.match.json"))) == 2
    assert len(list(tmp_path.glob("*.timeline.json"))) == 2
