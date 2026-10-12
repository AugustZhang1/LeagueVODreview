import pytest

from lolreview.cache import Cache
from lolreview.ddragon import OFFLINE_VERSION, DataDragon

VERSIONS = ["26.20.1", "26.19.2", "26.19.1", "26.18.1"]
CHAMPS = {"data": {"Fiddlesticks": {"key": "9", "id": "Fiddlesticks", "name": "Fiddlesticks"}}}


class Fetch:
    def __init__(self, fail=False):
        self.urls = []
        self.fail = fail

    def __call__(self, url):
        self.urls.append(url)
        if self.fail:
            raise OSError("offline")
        return VERSIONS if url.endswith("versions.json") else CHAMPS


@pytest.fixture
def cache(tmp_path):
    return Cache(tmp_path / "c.db")


def test_version_for_patch_picks_newest_of_patch(cache):
    dd = DataDragon(cache, Fetch())
    assert dd.version_for_patch("26.19") == "26.19.2"
    assert dd.version_for_patch("26.1") == "26.20.1"  # no 26.1.x: newest overall


def test_versions_cached(cache):
    f = Fetch()
    dd = DataDragon(cache, f)
    dd.version_for_patch("26.19")
    dd.version_for_patch("26.18")
    assert len(f.urls) == 1


def test_champions_map_and_cache(cache):
    f = Fetch()
    dd = DataDragon(cache, f)
    assert dd.champions("26.19.2") == {9: ("Fiddlesticks", "Fiddlesticks")}
    dd.champions("26.19.2")
    assert len(f.urls) == 1
    assert "26.19.2/data/en_US/champion.json" in f.urls[0]


def test_offline_fallback(cache, caplog):
    dd = DataDragon(cache, Fetch(fail=True))
    with caplog.at_level("WARNING"):
        assert dd.version_for_patch("26.19") == "26.19.1"
        assert dd.champions("26.19.1") == {}
    assert "unavailable" in caplog.text


def test_offline_mode_makes_no_calls(cache):
    f = Fetch()
    dd = DataDragon(cache, f, offline=True, offline_champions={1: ("A", "Annie")})
    assert dd.version_for_patch("26.19") == OFFLINE_VERSION
    assert dd.champions("x") == {1: ("A", "Annie")}
    assert f.urls == []
