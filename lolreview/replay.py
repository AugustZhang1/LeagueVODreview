"""Client for the League client's local Replay API (Plan Step 16)."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

from lolreview.schemas import ReplayStatus

BASE = "https://127.0.0.1:2999"
CERT_PATH = Path(__file__).parent / "certs" / "riotgames.pem"
CERT_URL = "https://static.developer.riotgames.com/docs/lol/riotgames.pem"
TIMEOUT_S = 0.5
LEAD_S = 5.0

REASON_OPEN = "Open this game's replay in the League client"
REASON_OTHER_GAME = "The open replay is a different game"
REASON_OLD_PATCH = "Replays only exist for the current patch"
REASON_NO_CERT = f"Riot's certificate is missing: download {CERT_URL} to {CERT_PATH}"


class ReplayUnavailable(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _LocalAdapter(HTTPAdapter):
    """Verifies the certificate chain against Riot's root, but not the hostname.

    The local API's certificate isn't issued for 127.0.0.1, so only the hostname check is off;
    the chain check stays on.
    """

    def init_poolmanager(self, *args, **kwargs):
        kwargs["assert_hostname"] = False
        super().init_poolmanager(*args, **kwargs)


def make_session(cert_path: Path = CERT_PATH) -> requests.Session:
    session = requests.Session()
    session.verify = str(cert_path)
    session.mount(BASE, _LocalAdapter())
    return session


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _patch_tuple(patch: str) -> tuple[int, ...]:
    return tuple(int(x) for x in patch.split(".")[:2])


def _same_game(live_players: list[dict], match: dict) -> bool:
    """True when the replay's 10 champions are the match's 10 champions."""
    remaining = Counter(_norm(p["championName"]) for p in match["info"]["participants"])
    if len(live_players) != sum(remaining.values()):
        return False
    for player in live_players:
        raw = str(player.get("rawChampionName", "")).rsplit("_", 1)[-1]
        candidates = [_norm(raw), _norm(str(player.get("championName", "")))]
        hit = next((c for c in candidates if c and remaining[c] > 0), None)
        if hit is None:
            return False
        remaining[hit] -= 1
    return True


class ReplayClient:
    def __init__(self, session: requests.Session | None = None, cert_path: Path = CERT_PATH):
        self.cert_path = Path(cert_path)
        self._session = session

    def _http(self) -> requests.Session:
        if self._session is None:
            self._session = make_session(self.cert_path)
        return self._session

    def _cert_missing(self) -> bool:
        return not self.cert_path.is_file()

    def status(self, match: dict, newest_patch: str | None = None) -> ReplayStatus:
        match_patch = ".".join(str(match["info"]["gameVersion"]).split(".")[:2])
        if newest_patch and _patch_tuple(match_patch) < _patch_tuple(newest_patch):
            return ReplayStatus(available=False, reason=REASON_OLD_PATCH)
        if self._cert_missing():
            return ReplayStatus(available=False, reason=REASON_NO_CERT)
        try:
            resp = self._http().get(f"{BASE}/liveclientdata/playerlist", timeout=TIMEOUT_S)
            resp.raise_for_status()
            players = resp.json()
        except (requests.RequestException, ValueError):
            return ReplayStatus(available=False, reason=REASON_OPEN)
        if not isinstance(players, list) or not _same_game(players, match):
            return ReplayStatus(available=False, reason=REASON_OTHER_GAME)
        return ReplayStatus(available=True, reason=None)

    def seek(self, t_s: float) -> None:
        if self._cert_missing():
            raise ReplayUnavailable(REASON_NO_CERT)
        body = {"time": max(0.0, t_s - LEAD_S), "paused": False}
        try:
            resp = self._http().post(f"{BASE}/replay/playback", json=body, timeout=TIMEOUT_S)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ReplayUnavailable(REASON_OPEN) from exc


_default = ReplayClient()


def status(match: dict, newest_patch: str | None = None) -> ReplayStatus:
    return _default.status(match, newest_patch)


def seek(t_s: float) -> None:
    _default.seek(t_s)
