import logging
from collections.abc import Callable

import requests

from lolreview.cache import Cache

log = logging.getLogger(__name__)

BASE = "https://ddragon.leagueoflegends.com"
VERSIONS_TTL_S = 86400.0
TIMEOUT_S = 15


def _http_get_json(url: str):
    resp = requests.get(url, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


class DataDragon:
    """Data Dragon versions and champion tables, cached in cache.db.

    With `offline=True` (demo mode) nothing is fetched: versions come from the patch and the
    champion table is the given one.
    """

    def __init__(
        self,
        cache: Cache,
        fetch: Callable[[str], object] = _http_get_json,
        offline: bool = False,
        offline_champions: dict[int, tuple[str, str]] | None = None,
    ):
        self._cache = cache
        self._fetch = fetch
        self.offline = offline
        self._offline_champions = offline_champions or {}

    def versions(self) -> list[str]:
        cached = self._cache.get_ddragon("versions", VERSIONS_TTL_S)
        if cached:
            return cached
        data = self._fetch(f"{BASE}/api/versions.json")
        if not isinstance(data, list) or not data:
            raise ValueError("unexpected versions.json")
        self._cache.put_ddragon("versions", data)
        return data

    def version_for_patch(self, patch: str) -> str:
        """Newest Data Dragon version of a patch ("26.19" -> "26.19.1"); else the newest."""
        if self.offline:
            return f"{patch}.1"
        try:
            versions = self.versions()
        except Exception as exc:
            log.warning("Data Dragon versions unavailable (%s); using %s.1", exc, patch)
            return f"{patch}.1"
        for v in versions:  # newest first
            if v.startswith(patch + "."):
                return v
        return versions[0]

    def champions(self, version: str) -> dict[int, tuple[str, str]]:
        """championId -> (Data Dragon id, display name). Empty when unavailable."""
        if self.offline:
            return dict(self._offline_champions)
        name = f"champions-{version}"
        raw = self._cache.get_ddragon(name)
        if raw is None:
            try:
                data = self._fetch(f"{BASE}/cdn/{version}/data/en_US/champion.json")
                raw = {v["key"]: [v["id"], v["name"]] for v in data["data"].values()}
            except Exception as exc:
                log.warning(
                    "Data Dragon champions for %s unavailable (%s); using match champion names",
                    version,
                    exc,
                )
                return {}
            self._cache.put_ddragon(name, raw)
        return {int(k): (v[0], v[1]) for k, v in raw.items()}
