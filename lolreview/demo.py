"""Demo mode: the whole app on the synthetic fixtures, with no Riot key and no network."""

import json
from pathlib import Path

from lolreview.config import ROOT
from lolreview.riot import NotFoundError

FIXTURES = ROOT / "tests" / "fixtures" / "synthetic"
DEMO_PLATFORM = "na1"
DEMO_NAME = "Me"
DEMO_TAG = "NA1"
DEMO_RANK = {
    "queueType": "RANKED_SOLO_5x5",
    "tier": "GOLD",
    "rank": "III",
    "leaguePoints": 47,
}

# championId -> (Data Dragon id, display name) for the champions in the fixtures.
DEMO_CHAMPIONS: dict[int, tuple[str, str]] = {
    5: ("XinZhao", "Xin Zhao"),
    9: ("Fiddlesticks", "Fiddlesticks"),
    51: ("Caitlyn", "Caitlyn"),
    54: ("Malphite", "Malphite"),
    58: ("Renekton", "Renekton"),
    61: ("Orianna", "Orianna"),
    62: ("MonkeyKing", "Wukong"),
    64: ("LeeSin", "Lee Sin"),
    81: ("Ezreal", "Ezreal"),
    86: ("Garen", "Garen"),
    89: ("Leona", "Leona"),
    103: ("Ahri", "Ahri"),
    112: ("Viktor", "Viktor"),
    113: ("Sejuani", "Sejuani"),
    117: ("Lulu", "Lulu"),
    122: ("Darius", "Darius"),
    134: ("Syndra", "Syndra"),
    145: ("Kaisa", "Kai'Sa"),
    201: ("Braum", "Braum"),
    222: ("Jinx", "Jinx"),
    234: ("Viego", "Viego"),
    238: ("Zed", "Zed"),
    254: ("Vi", "Vi"),
    267: ("Nami", "Nami"),
    360: ("Samira", "Samira"),
    412: ("Thresh", "Thresh"),
    516: ("Ornn", "Ornn"),
    523: ("Aphelios", "Aphelios"),
    526: ("Rell", "Rell"),
    777: ("Yone", "Yone"),
    887: ("Gwen", "Gwen"),
}


class DemoRiot:
    """In-process stand-in for RiotClient, serving the synthetic games for Me#NA1."""

    key_status = "ok"

    def __init__(self, folder: Path = FIXTURES):
        self._matches: dict[str, dict] = {}
        self._timelines: dict[str, dict] = {}
        for path in sorted(folder.glob("*.match.json")):
            match = json.loads(path.read_text(encoding="utf-8"))
            mid = match["metadata"]["matchId"]
            self._matches[mid] = match
            self._timelines[mid] = json.loads(
                path.with_name(f"{mid}.timeline.json").read_text(encoding="utf-8")
            )
        self._newest_first = sorted(
            self._matches, key=lambda m: self._matches[m]["info"]["gameCreation"], reverse=True
        )
        self.puuid = next(
            p["puuid"]
            for p in self._matches[self._newest_first[0]]["info"]["participants"]
            if p["riotIdGameName"] == DEMO_NAME
        )

    def account_by_riot_id(self, cluster: str, name: str, tag: str) -> dict:
        if (name.lower(), tag.lower()) != (DEMO_NAME.lower(), DEMO_TAG.lower()):
            raise NotFoundError(f"{name}#{tag}")
        return {"puuid": self.puuid, "gameName": DEMO_NAME, "tagLine": DEMO_TAG}

    def rank_by_puuid(self, platform: str, puuid: str) -> dict | None:
        return dict(DEMO_RANK) if puuid == self.puuid else None

    def match_ids(self, cluster, puuid, queue=420, start_time=None, start=0, count=100):
        return self._newest_first[start : start + count]

    def match(self, cluster: str, match_id: str) -> dict:
        if match_id not in self._matches:
            raise NotFoundError(match_id)
        return self._matches[match_id]

    def timeline(self, cluster: str, match_id: str) -> dict:
        if match_id not in self._timelines:
            raise NotFoundError(match_id)
        return self._timelines[match_id]
