import pytest

from lolreview import config
from lolreview.constants import PLATFORM_TO_CLUSTER, TIER_INDEX, TIERS


def test_default_config_loads():
    cfg = config.load_config()
    assert cfg["crawl"]["platforms"] == ["na1", "euw1", "kr"]
    assert cfg["crawl"]["queue"] == 420
    assert cfg["rate_limit"]["short_count"] == 18
    assert cfg["review"]["step_s"] == 15
    assert cfg["review"]["great"] > cfg["review"]["good"] > 0
    assert cfg["review"]["blunder"] < cfg["review"]["mistake"] < 0
    assert len(cfg["respawn"]["base_by_level"]) == 18


def test_crawl_settings_are_consistent():
    cfg = config.load_config()
    tiers = cfg["crawl"]["tiers"]
    assert cfg["crawl"]["bottom_tier"] == tiers[-1]
    assert [TIER_INDEX[t] for t in tiers] == sorted((TIER_INDEX[t] for t in tiers), reverse=True)
    assert all(p in PLATFORM_TO_CLUSTER for p in cfg["crawl"]["platforms"])


def test_timers_present():
    timers = config.load_config()["timers"]
    for name in ("dragon", "grubs", "herald", "baron", "elder"):
        assert timers[f"{name}_first_s"] > 0
    for name in ("dragon", "baron", "elder"):
        assert timers[f"{name}_respawn_s"] > 0
    for name in ("grubs", "herald"):
        assert timers[f"{name}_despawn_s"] > timers[f"{name}_first_s"]
    for name in ("baron_buff_s", "elder_buff_s", "inhibitor_respawn_s"):
        assert timers[name] > 0


def test_path_from_env_and_reload(tmp_path, monkeypatch):
    path = tmp_path / "c.toml"
    path.write_text("[a]\nx = 1\n")
    monkeypatch.setenv("LOLREVIEW_CONFIG", str(path))
    assert config.load_config() == {"a": {"x": 1}}
    path.write_text("[a]\nx = 2\n")
    assert config.load_config()["a"]["x"] == 1  # cached
    assert config.load_config(reload=True)["a"]["x"] == 2


def test_read_env(tmp_path):
    path = tmp_path / ".env"
    path.write_text('# comment\nRIOT_API_KEY=RGAPI-abc\nKAGGLE_API_TOKEN = "KGAT_x"\n\nEMPTY=\n')
    assert config.read_env(path) == {
        "RIOT_API_KEY": "RGAPI-abc",
        "KAGGLE_API_TOKEN": "KGAT_x",
        "EMPTY": "",
    }
    path.write_text("RIOT_API_KEY=RGAPI-new\n")
    assert config.read_env(path)["RIOT_API_KEY"] == "RGAPI-new"


def test_read_env_missing_file(tmp_path):
    assert config.read_env(tmp_path / "nope") == {}


def test_tier_constants():
    assert TIERS[0] == "IRON" and TIERS[-1] == "CHALLENGER"
    assert TIER_INDEX["IRON"] == 0 and TIER_INDEX["CHALLENGER"] == 9


@pytest.mark.parametrize("platform", ["na1", "euw1", "kr", "oc1", "me1", "la2"])
def test_platform_map(platform):
    assert PLATFORM_TO_CLUSTER[platform] in ("americas", "europe", "asia", "sea")
