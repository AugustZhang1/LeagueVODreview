"""Feature extraction and game state, built only from events at or before the asked time.

Shared by the crawler (training rows), the training script (column lists) and the review (a game
state every 15 s), so the same code builds the features in all three places.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from lolreview.config import load_config
from lolreview.constants import (
    BLUE,
    DRAGON_TYPES,
    ELDER,
    PRO_TIER_INDEX,
    QUEUE_RANKED_SOLO,
    RED,
    REMAKE_MAX_S,
    TIER_INDEX,
)

FEATURES_VERSION = 1

FEATURE_COLUMNS = [
    "tier",
    "minute",
    "gold_diff",
    "kill_diff",
    "tower_diff",
    "level_diff",
    "cs_diff",
    "grub_diff",
    "herald_diff",
    "atakhan_diff",
    "inhibs_down_diff",
    "baron_active",
    "elder_active",
    "blue_dragons",
    "red_dragons",
    "soul_diff",
    "soul_type",
]
CATEGORICAL_COLUMNS = ["soul_type"]
SOUL_TYPES = ["none", "Infernal", "Mountain", "Ocean", "Cloud", "Hextech", "Chemtech"]
EXTRA_COLUMNS = ["match_id", "platform", "patch", "duration_s", "t", "blue_won"]

MONOTONE: dict[str, int] = {c: 0 for c in FEATURE_COLUMNS}
MONOTONE.update(
    {
        c: 1
        for c in (
            "gold_diff",
            "kill_diff",
            "tower_diff",
            "inhibs_down_diff",
            "baron_active",
            "elder_active",
            "grub_diff",
            "soul_diff",
            "level_diff",
            "cs_diff",
            "blue_dragons",
            "herald_diff",
            "atakhan_diff",
        )
    }
)
MONOTONE["red_dragons"] = -1

TRINKETS = (3340, 3363, 3364, 3330)
EVENT_ROW_TYPES = ("CHAMPION_KILL", "ELITE_MONSTER_KILL", "BUILDING_KILL", "TURRET_PLATE_DESTROYED")
LANES = {"TOP_LANE": "top", "MID_LANE": "mid", "BOT_LANE": "bot"}
TOWER_KINDS = {"OUTER_TURRET": "outer", "INNER_TURRET": "inner", "BASE_TURRET": "base"}


@dataclass
class PlayerState:
    participant_id: int
    team: int
    role: str
    x: float = 0.0
    y: float = 0.0
    pos_t_ms: int = 0
    level: int = 1
    k: int = 0
    d: int = 0
    a: int = 0
    cs: int = 0
    gold: float = 0.0
    items: list[int | None] = field(default_factory=lambda: [None] * 6)
    trinket: int | None = None
    dead_until_ms: int = 0


@dataclass
class TeamState:
    kills: int = 0
    gold: float = 0.0
    towers: int = 0
    plates: int = 0
    inhibs_down: int = 0
    dragons: list[str] = field(default_factory=list)
    soul: str | None = None
    grubs: int = 0
    heralds: int = 0
    barons: int = 0
    atakhans: int = 0
    elders: int = 0
    buff: tuple[str, int] | None = None
    level_sum: int = 0
    cs_sum: int = 0
    baron_buff_end_ms: int = 0
    elder_buff_end_ms: int = 0


@dataclass
class GameState:
    t_ms: int
    teams: dict[int, TeamState]
    players: dict[int, PlayerState]
    buildings_down: set[str]
    recent_kills: list[tuple[int, float, float, int]]
    map_soul_type: str = "none"


def skip_reason(match: dict) -> str | None:
    info = match["info"]
    if info.get("queueId") != QUEUE_RANKED_SOLO:
        return "not_ranked_solo"
    early = any(p.get("gameEndedInEarlySurrender") for p in info.get("participants", []))
    if early or info.get("gameDuration", 0) < REMAKE_MAX_S:
        return "remake"
    return None


def patch_of(match: dict) -> str:
    return ".".join(match["info"]["gameVersion"].split(".")[:2])


def respawn_seconds(level: int, t_s: float, cfg: dict | None = None) -> float:
    r = (cfg or load_config())["respawn"]
    base = r["base_by_level"][min(max(level, 1), len(r["base_by_level"])) - 1]
    minutes = t_s / 60.0
    start, mid, late = r["scaling_start_min"], r["scaling_mid_min"], r["scaling_late_min"]
    if minutes <= start:
        factor = 0.0
    elif minutes <= mid:
        factor = r["scaling_early_step"] * int((minutes - start) * 2)
    elif minutes <= late:
        factor = r["scaling_mid_base"] + r["scaling_mid_step"] * int((minutes - mid) * 2)
    else:
        factor = r["scaling_late_base"] + r["scaling_late_step"] * int((minutes - late) * 2)
    return base * (1 + min(factor, r["scaling_max"]))


def _building_id(event: dict, nexus_seen: dict[str, int]) -> str:
    owner = "blue" if event["teamId"] == BLUE else "red"
    if event["buildingType"] == "INHIBITOR_BUILDING":
        return f"{owner}_{LANES.get(event.get('laneType'), 'mid')}_inhib"
    if event.get("towerType") == "NEXUS_TURRET":
        nexus_seen[owner] = nexus_seen.get(owner, 0) + 1
        return f"{owner}_nexus_{min(nexus_seen[owner], 2)}"
    lane = LANES.get(event.get("laneType"), "mid")
    return f"{owner}_{lane}_{TOWER_KINDS.get(event.get('towerType'), 'outer')}"


class _Walker:
    """Mutable game state advanced event by event; `snapshot` copies it out."""

    def __init__(self, match: dict, cfg: dict) -> None:
        self.cfg = cfg
        timers = cfg["timers"]
        self.inhib_ms = int(timers["inhibitor_respawn_s"] * 1000)
        self.baron_ms = int(timers["baron_buff_s"] * 1000)
        self.elder_ms = int(timers["elder_buff_s"] * 1000)
        self.recent_ms = int(cfg["review"]["recent_kill_s"] * 1000)
        self.players: dict[int, PlayerState] = {}
        for p in match["info"]["participants"]:
            pid = p["participantId"]
            role = p.get("teamPosition") or p.get("individualPosition") or ""
            self.players[pid] = PlayerState(pid, p["teamId"], role)
        self.teams = {BLUE: TeamState(), RED: TeamState()}
        self.towers_down: set[str] = set()
        self.inhib_until: dict[str, int] = {}
        self.nexus_seen: dict[str, int] = {}
        self.recent: list[tuple[int, float, float, int]] = []
        self.map_dragons: list[str] = []
        self.map_soul_type = "none"

    def team_of(self, pid: int) -> int | None:
        p = self.players.get(pid)
        return p.team if p else None

    def apply_frame(self, frame: dict) -> None:
        ts = frame["timestamp"]
        for key, pf in frame["participantFrames"].items():
            p = self.players.get(int(key))
            if p is None:
                continue
            p.level = pf["level"]
            p.cs = pf["minionsKilled"] + pf["jungleMinionsKilled"]
            p.gold = float(pf["totalGold"])
            pos = pf.get("position")
            if pos:
                p.x, p.y, p.pos_t_ms = pos["x"], pos["y"], ts

    def _add_item(self, p: PlayerState, item: int) -> None:
        if item in TRINKETS:
            p.trinket = item
        elif None in p.items:
            p.items[p.items.index(None)] = item

    def _remove_item(self, p: PlayerState, item: int) -> None:
        if item in p.items:
            p.items[p.items.index(item)] = None
        elif p.trinket == item:
            p.trinket = None

    def apply_event(self, e: dict) -> None:
        kind = e["type"]
        t = e["timestamp"]
        if kind == "CHAMPION_KILL":
            self._champion_kill(e, t)
        elif kind == "LEVEL_UP":
            p = self.players.get(e["participantId"])
            if p:
                p.level = e["level"]
        elif kind == "ELITE_MONSTER_KILL":
            self._monster(e, t)
        elif kind == "BUILDING_KILL":
            self._building(e, t)
        elif kind == "TURRET_PLATE_DESTROYED":
            self.teams[RED if e["teamId"] == BLUE else BLUE].plates += 1
        elif kind == "DRAGON_SOUL_GIVEN":
            self.teams[e["teamId"]].soul = e["name"]
            if self.map_soul_type == "none":
                self.map_soul_type = e["name"]
        elif kind in ("ITEM_PURCHASED", "ITEM_SOLD", "ITEM_DESTROYED", "ITEM_UNDO"):
            p = self.players.get(e["participantId"])
            if p is None:
                return
            if kind == "ITEM_PURCHASED":
                self._add_item(p, e["itemId"])
            elif kind == "ITEM_UNDO":
                if e.get("beforeId"):
                    self._remove_item(p, e["beforeId"])
                if e.get("afterId"):
                    self._add_item(p, e["afterId"])
            else:
                self._remove_item(p, e["itemId"])

    def _champion_kill(self, e: dict, t: int) -> None:
        pos = e.get("position") or {}
        x, y = pos.get("x", 0), pos.get("y", 0)
        killer = self.players.get(e.get("killerId", 0))
        victim = self.players.get(e["victimId"])
        killer_team = killer.team if killer else (RED if victim and victim.team == BLUE else BLUE)
        self.teams[killer_team].kills += 1
        if killer:
            killer.k += 1
            killer.gold += e.get("bounty", 0) + e.get("shutdownBounty", 0)
            killer.x, killer.y, killer.pos_t_ms = x, y, t
        for a in e.get("assistingParticipantIds", []):
            if a in self.players:
                self.players[a].a += 1
        if victim:
            victim.d += 1
            victim.x, victim.y, victim.pos_t_ms = x, y, t
            secs = respawn_seconds(victim.level, t / 1000, self.cfg)
            victim.dead_until_ms = t + int(round(secs * 1000))
        self.recent.append((t, x, y, killer_team))

    def _monster(self, e: dict, t: int) -> None:
        team = self.teams.get(e.get("killerTeamId"))
        if team is None:
            return
        mt = e["monsterType"]
        if mt == "DRAGON":
            sub = e.get("monsterSubType")
            if sub == ELDER:
                team.elders += 1
                team.elder_buff_end_ms = t + self.elder_ms
            elif sub in DRAGON_TYPES:
                name = DRAGON_TYPES[sub]
                team.dragons.append(name)
                self.map_dragons.append(name)
                if len(self.map_dragons) == 3:
                    self.map_soul_type = name
                if len(team.dragons) == 4 and not any(x.soul for x in self.teams.values()):
                    team.soul = self.map_soul_type
        elif mt == "HORDE":
            team.grubs += 1
        elif mt == "RIFTHERALD":
            team.heralds += 1
        elif mt == "BARON_NASHOR":
            team.barons += 1
            team.baron_buff_end_ms = t + self.baron_ms
        elif mt == "ATAKHAN":
            team.atakhans += 1

    def _building(self, e: dict, t: int) -> None:
        bid = _building_id(e, self.nexus_seen)
        if e["buildingType"] == "INHIBITOR_BUILDING":
            self.inhib_until[bid] = t + self.inhib_ms
        else:
            self.towers_down.add(bid)
            self.teams[RED if e["teamId"] == BLUE else BLUE].towers += 1

    def snapshot(self, t: int) -> GameState:
        players = {pid: replace(p, items=list(p.items)) for pid, p in self.players.items()}
        down = set(self.towers_down)
        inhibs = {BLUE: 0, RED: 0}
        for bid, until in self.inhib_until.items():
            if t < until:
                down.add(bid)
                inhibs[BLUE if bid.startswith("blue") else RED] += 1
        teams: dict[int, TeamState] = {}
        for tid, ts in self.teams.items():
            mine = [p for p in players.values() if p.team == tid]
            buffs = []
            if ts.baron_buff_end_ms > t:
                buffs.append(("baron", ts.baron_buff_end_ms))
            if ts.elder_buff_end_ms > t:
                buffs.append(("elder", ts.elder_buff_end_ms))
            teams[tid] = replace(
                ts,
                dragons=list(ts.dragons),
                gold=sum(p.gold for p in mine),
                inhibs_down=inhibs[tid],
                level_sum=sum(p.level for p in mine),
                cs_sum=sum(p.cs for p in mine),
                buff=max(buffs, key=lambda b: b[1]) if buffs else None,
            )
        cutoff = t - self.recent_ms
        recent = [k for k in self.recent if k[0] > cutoff]
        self.recent = recent
        return GameState(t, teams, players, down, list(recent), self.map_soul_type)


def states_at(match: dict, timeline: dict, times_ms: list[int]) -> list[GameState]:
    """One pass over the events; results come back in the order of `times_ms`."""
    cfg = load_config()
    frames = timeline["info"]["frames"]
    items: list[tuple[int, int, dict]] = []
    for f in frames:
        items.append((f["timestamp"], 1, f))
        items.extend((e["timestamp"], 0, e) for e in f["events"])
    items.sort(key=lambda it: (it[0], it[1]))
    order = sorted(range(len(times_ms)), key=lambda i: times_ms[i])
    out: list[GameState | None] = [None] * len(times_ms)
    walker = _Walker(match, cfg)
    pos = 0
    for i in order:
        t = times_ms[i]
        while pos < len(items) and items[pos][0] <= t:
            _, is_frame, obj = items[pos]
            if is_frame:
                walker.apply_frame(obj)
            else:
                walker.apply_event(obj)
            pos += 1
        out[i] = walker.snapshot(t)
    return out  # type: ignore[return-value]


def state_at(match: dict, timeline: dict, t_ms: int) -> GameState:
    return states_at(match, timeline, [t_ms])[0]


def _tier_index(tier: str | int) -> int:
    if isinstance(tier, int):
        return tier
    key = tier.upper()
    return PRO_TIER_INDEX if key == "PRO" else TIER_INDEX[key]


def feature_row(state: GameState, tier: str | int) -> dict:
    b, r = state.teams[BLUE], state.teams[RED]

    def side(blue_has: bool, red_has: bool) -> int:
        return 1 if blue_has else (-1 if red_has else 0)

    return {
        "tier": _tier_index(tier),
        "minute": state.t_ms / 60000,
        "gold_diff": b.gold - r.gold,
        "kill_diff": b.kills - r.kills,
        "tower_diff": b.towers - r.towers,
        "level_diff": b.level_sum - r.level_sum,
        "cs_diff": b.cs_sum - r.cs_sum,
        "grub_diff": b.grubs - r.grubs,
        "herald_diff": b.heralds - r.heralds,
        "atakhan_diff": b.atakhans - r.atakhans,
        "inhibs_down_diff": r.inhibs_down - b.inhibs_down,
        "baron_active": side(b.baron_buff_end_ms > state.t_ms, r.baron_buff_end_ms > state.t_ms),
        "elder_active": side(b.elder_buff_end_ms > state.t_ms, r.elder_buff_end_ms > state.t_ms),
        "blue_dragons": len(b.dragons),
        "red_dragons": len(r.dragons),
        "soul_diff": side(b.soul is not None, r.soul is not None),
        "soul_type": state.map_soul_type,
    }


def extract_rows(match: dict, timeline: dict, tier: str | int) -> list[dict]:
    if skip_reason(match) is not None:
        return []
    frames = timeline["info"]["frames"]
    times = {f["timestamp"] for f in frames}
    for f in frames:
        times.update(e["timestamp"] + 1 for e in f["events"] if e["type"] in EVENT_ROW_TYPES)
    times_list = sorted(times)
    info = match["info"]
    blue_won = int(any(t["teamId"] == BLUE and t["win"] for t in info["teams"]))
    extra = {
        "match_id": match["metadata"]["matchId"],
        "platform": info["platformId"],
        "patch": patch_of(match),
        "duration_s": info["gameDuration"],
        "blue_won": blue_won,
    }
    rows = []
    for t, state in zip(times_list, states_at(match, timeline, times_list), strict=True):
        row = feature_row(state, tier)
        row.update(extra)
        row["t"] = t
        rows.append(row)
    return rows


def rows_to_table(rows: list[dict]):
    import pyarrow as pa

    floats = {"minute", "gold_diff"}
    big = {"t"}
    strings = {"match_id"}
    dicts = {"platform", "patch"}
    arrays = {}
    for col in FEATURE_COLUMNS + EXTRA_COLUMNS:
        values = [r[col] for r in rows]
        if col == "soul_type":
            idx = pa.array([SOUL_TYPES.index(v) for v in values], type=pa.int8())
            arrays[col] = pa.DictionaryArray.from_arrays(idx, pa.array(SOUL_TYPES))
        elif col in dicts:
            arrays[col] = (
                pa.array(values, type=pa.string())
                .dictionary_encode()
                .cast(pa.dictionary(pa.int16(), pa.string()))
            )
        elif col in strings:
            arrays[col] = pa.array(values, type=pa.string())
        elif col in floats:
            arrays[col] = pa.array(values, type=pa.float32())
        elif col in big:
            arrays[col] = pa.array(values, type=pa.int32())
        else:
            arrays[col] = pa.array(values, type=pa.int16())
    return pa.table(arrays)
