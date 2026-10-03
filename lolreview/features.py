"""Feature extraction and game state, built only from events at or before the asked time.

Shared by the crawler (training rows), the training script (column lists) and the review (a game
state every 15 s), so the same code builds the features in all three places.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from lolreview import map_data
from lolreview.config import load_config
from lolreview.constants import (
    BLUE,
    BOOTS,
    BOT_QUEST,
    CONTROL_WARD,
    DRAGON_TYPES,
    ELDER,
    ELIXIRS,
    FOOTWEAR,
    FOOTWEAR_RUNE,
    MID_BOOTS,
    MID_QUEST,
    PRO_TIER_INDEX,
    QUEST_DONE_ITEMS,
    QUEUE_RANKED_SOLO,
    RED,
    REMAKE_MAX_S,
    SILENT_UPGRADES,
    SUPPORT_FINAL,
    SUPPORT_UPGRADES,
    TIER_INDEX,
)

FEATURES_VERSION = 3

V1_COLUMNS = [
    "tier",
    "minute",
    "gold_diff",
    "kill_diff",
    "tower_diff",
    "level_diff",
    "cs_diff",
    "grub_diff",
    "herald_diff",
    "quest_diff",
    "inhibs_down_diff",
    "baron_active",
    "elder_active",
    "blue_dragons",
    "red_dragons",
    "soul_diff",
    "soul_type",
]
# Version 2: who is alive, when the pits' monsters are up, where players stand (minute frames and
# events) and recent wards. Any change to these or the constants below needs a new version.
FEATURE_COLUMNS = V1_COLUMNS + [
    "alive_diff",
    "blue_dead_s",
    "red_dead_s",
    "baron_pit_in_s",
    "dragon_pit_in_s",
    "baron_setup_diff",
    "dragon_setup_diff",
    "grouped_diff",
    "split_diff",
    "enemy_jungle_diff",
    "wards_placed_diff",
    "wards_killed_diff",
]
# Version 3: each team's champions, as sorted comma-joined names (`blue_champs`, `red_champs`).
# Training turns them into these model columns with a per-champion table (`champions.json`, from
# the training games only), and the app does the same with that table (`champion_features`).
CHAMPION_FEATURES = ["champ_wr_diff", "scaling_diff"]
CATEGORICAL_COLUMNS = ["soul_type"]
SOUL_TYPES = ["none", "Infernal", "Mountain", "Ocean", "Cloud", "Hextech", "Chemtech"]
EXTRA_COLUMNS = [
    "match_id", "platform", "patch", "duration_s", "t", "blue_won", "blue_champs", "red_champs",
]  # fmt: skip

MONOTONE: dict[str, int] = {c: 0 for c in FEATURE_COLUMNS + CHAMPION_FEATURES}
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
            "quest_diff",
            "alive_diff",
            "red_dead_s",
        )
    }
)
MONOTONE["red_dragons"] = -1
MONOTONE["blue_dead_s"] = -1

SETUP_S = 90  # a pit counts as contested from this long before its monster is up
PIT_RADIUS = 3000  # players this close to a pit are setting up for it
GROUP_RADIUS = 2000  # teammates this close count as one group
SPLIT_ALONE = 4000  # a split pusher's nearest living teammate is at least this far
SPLIT_FROM_MIN = 14  # before plates fall, a lone side laner is just laning
WARD_WINDOW_S = 180
WARD_TYPES = {"YELLOW_TRINKET", "SIGHT_WARD", "CONTROL_WARD", "BLUE_TRINKET"}  # not traps
GRUBS_PER_CAMP = 3

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
    quest_item: int | None = None  # boots in the slot the Bot Lane quest adds
    quest: int | None = None  # the item whose ITEM_DESTROYED marked the role quest done
    dead_until_ms: int = 0
    champion: str = ""  # championName, e.g. "Belveth"; "" when unknown


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
    quests: int = 0
    buff: tuple[str, int] | None = None
    level_sum: int = 0
    cs_sum: int = 0
    baron_buff_end_ms: int = 0
    elder_buff_end_ms: int = 0
    wards_placed: int = 0  # in the last WARD_WINDOW_S
    wards_killed: int = 0


@dataclass
class GameState:
    t_ms: int
    teams: dict[int, TeamState]
    players: dict[int, PlayerState]
    buildings_down: set[str]
    recent_kills: list[tuple[int, float, float, int]]
    map_soul_type: str = "none"
    baron_pit_in_ms: int = 0  # until the Baron pit's next monster (grubs, Herald, Baron) is up
    dragon_pit_in_ms: int = 0  # until the next dragon or Elder is up


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
        self.timers_ms = {k: int(v * 1000) for k, v in timers.items()}
        self.recent_ms = int(cfg["review"]["recent_kill_s"] * 1000)
        self.grub_kills = 0
        self.herald_gone = False
        self.baron_next_ms = self.timers_ms["baron_first_s"]
        self.dragon_next_ms = self.timers_ms["dragon_first_s"]
        self.wards: list[tuple[int, int, bool]] = []  # (t, team, killed)
        self.players: dict[int, PlayerState] = {}
        self.support_final: dict[int, int] = {}  # what Bounty of Worlds became, from the end items
        self.footwear: dict[int, int] = {}  # Magical Footwear: player -> when the boots arrive (ms)
        for p in match["info"]["participants"]:
            pid = p["participantId"]
            role = p.get("teamPosition") or p.get("individualPosition") or ""
            # Real games don't always log the starting Stealth Ward
            self.players[pid] = PlayerState(
                pid, p["teamId"], role, trinket=3340, champion=p.get("championName", "")
            )
            final = [p.get(f"item{i}") for i in range(7)] + [p.get("roleBoundItem")]
            self.support_final[pid] = next((i for i in final if i in SUPPORT_FINAL), 3867)
            styles = p.get("perks", {}).get("styles", [])
            for sel in (s for st in styles for s in st["selections"]):
                if sel["perk"] == FOOTWEAR_RUNE:
                    self.footwear[pid] = sel.get("var1", 12) * 60_000  # var1: arrival minute
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
            return
        if item in ELIXIRS or (item == CONTROL_WARD and p.role == "UTILITY"):
            return  # drunk at once / kept in the support quest slot, which isn't shown
        if p.quest == MID_QUEST:
            item = MID_BOOTS.get(item, item)
        if item in BOOTS and p.quest == BOT_QUEST:
            p.quest_item = item
        elif None in p.items:
            p.items[p.items.index(None)] = item

    def _remove_item(self, p: PlayerState, item: int, becomes: int | None = None) -> bool:
        if item in p.items:
            p.items[p.items.index(item)] = becomes
        elif p.trinket == item:
            p.trinket = None
        elif p.quest_item == item:
            p.quest_item = becomes
        else:
            return False
        return True

    def _destroy_item(self, p: PlayerState, item: int) -> None:
        if item in TRINKETS:
            return  # real games log trinkets as destroyed while the player still has them
        if item in QUEST_DONE_ITEMS and p.quest is None:
            p.quest = item
        if item in SUPPORT_UPGRADES or item == 3867:
            becomes = SUPPORT_UPGRADES.get(item) or self.support_final[p.participant_id]
            if not self._remove_item(p, item, becomes):
                self._add_item(p, becomes)  # World Atlas's purchase had participantId 0
        elif item in MID_BOOTS and p.role == "MIDDLE":
            self._remove_item(p, item, MID_BOOTS[item])  # destroyed just before the quest item
        elif p.quest == BOT_QUEST and p.quest_item is None and item in BOOTS and item in p.items:
            self._remove_item(p, item)  # moved to the Bot Lane quest's slot
            p.quest_item = item
        else:
            self._remove_item(p, item, SILENT_UPGRADES.get(item))

    def _give_footwear(self, t: int) -> None:
        for pid, at in sorted(self.footwear.items()):
            if t >= at:
                del self.footwear[pid]
                self._add_item(self.players[pid], FOOTWEAR)

    def apply_event(self, e: dict) -> None:
        kind = e["type"]
        t = e["timestamp"]
        self._give_footwear(t)
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
            self._seen_at(e, t)
            self.teams[RED if e["teamId"] == BLUE else BLUE].plates += 1
        elif kind == "DRAGON_SOUL_GIVEN":
            # teamId 0 only reveals the soul type after the 2nd dragon; 100 or 200 took the soul
            if e["teamId"] in self.teams:
                self.teams[e["teamId"]].soul = e["name"]
            self.map_soul_type = e["name"]
        elif kind in ("WARD_PLACED", "WARD_KILL"):
            placed = kind == "WARD_PLACED"
            team = self.team_of(e.get("creatorId" if placed else "killerId", 0))
            if team is not None and e.get("wardType") in WARD_TYPES:
                self.wards.append((t, team, not placed))
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
            elif kind == "ITEM_DESTROYED":
                self._destroy_item(p, e["itemId"])
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

    def _seen_at(self, e: dict, t: int) -> None:
        """An objective, building or plate puts its killer and assisters where it was."""
        pos = e.get("position")
        if not pos:
            return
        for pid in [e.get("killerId"), *e.get("assistingParticipantIds", [])]:
            p = self.players.get(pid)
            if p is not None:
                p.x, p.y, p.pos_t_ms = pos["x"], pos["y"], t

    def _monster(self, e: dict, t: int) -> None:
        self._seen_at(e, t)
        mt = e["monsterType"]
        timers = self.timers_ms
        # The pits' timers: grubs and Herald don't respawn, and despawns come as kills by team 300
        if mt == "HORDE":
            self.grub_kills += 1
        elif mt == "RIFTHERALD":
            self.herald_gone = True
        elif mt == "BARON_NASHOR":
            self.baron_next_ms = t + timers["baron_respawn_s"]
        elif mt == "DRAGON" and e.get("monsterSubType") == ELDER:
            self.dragon_next_ms = t + timers["elder_respawn_s"]
        elif mt == "DRAGON":
            self.dragon_next_ms = t + timers["dragon_respawn_s"]
        team = self.teams.get(e.get("killerTeamId"))
        if team is None:
            return
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
                if len(team.dragons) == 4:  # the soul: Elder comes next
                    self.dragon_next_ms = t + timers["elder_first_s"]
                    if not any(x.soul for x in self.teams.values()):
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
        self._seen_at(e, t)
        bid = _building_id(e, self.nexus_seen)
        if e["buildingType"] == "INHIBITOR_BUILDING":
            self.inhib_until[bid] = t + self.inhib_ms
        else:
            self.towers_down.add(bid)
            self.teams[RED if e["teamId"] == BLUE else BLUE].towers += 1

    def snapshot(self, t: int) -> GameState:
        self._give_footwear(t)
        players = {pid: replace(p, items=list(p.items)) for pid, p in self.players.items()}
        down = set(self.towers_down)
        inhibs = {BLUE: 0, RED: 0}
        for bid, until in self.inhib_until.items():
            if t < until:
                down.add(bid)
                inhibs[BLUE if bid.startswith("blue") else RED] += 1
        self.wards = [w for w in self.wards if w[0] > t - WARD_WINDOW_S * 1000]
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
                quests=sum(p.quest is not None for p in mine),
                buff=max(buffs, key=lambda b: b[1]) if buffs else None,
                wards_placed=sum(1 for _, team, killed in self.wards if team == tid and not killed),
                wards_killed=sum(1 for _, team, killed in self.wards if team == tid and killed),
            )
        cutoff = t - self.recent_ms
        recent = [k for k in self.recent if k[0] > cutoff]
        self.recent = recent
        return GameState(
            t, teams, players, down, list(recent), self.map_soul_type,
            baron_pit_in_ms=max(0, self._baron_pit_next(t) - t),
            dragon_pit_in_ms=max(0, self.dragon_next_ms - t),
        )  # fmt: skip

    def _baron_pit_next(self, t: int) -> int:
        """When the Baron pit's next monster is up: grubs, then Herald, then Baron."""
        timers = self.timers_ms
        if self.grub_kills < GRUBS_PER_CAMP and t < timers["grubs_despawn_s"]:
            return timers["grubs_first_s"]
        if not self.herald_gone and t < timers["herald_despawn_s"]:
            return timers["herald_first_s"]
        return self.baron_next_ms


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


def _located(state: GameState) -> dict[int, list[tuple[float, float]]]:
    """Positions of living players, per team. A position from before a player's last death
    (where they died, or a frame while dead) says nothing about where they are now."""
    out: dict[int, list[tuple[float, float]]] = {BLUE: [], RED: []}
    for p in state.players.values():
        if p.team in out and p.dead_until_ms <= p.pos_t_ms:
            out[p.team].append((p.x, p.y))
    return out


def _near(points: list[tuple[float, float]], spot: tuple[float, float], radius: float) -> int:
    return sum(1 for x, y in points if math.hypot(x - spot[0], y - spot[1]) <= radius)


def _largest_group(points: list[tuple[float, float]]) -> int:
    return max((_near(points, p, GROUP_RADIUS) for p in points), default=0)


def _split_pushers(points: list[tuple[float, float]], color: str) -> int:
    """Players alone in a side lane on the enemy's half of the map."""
    n = 0
    for i, (x, y) in enumerate(points):
        if map_data.side_of(x, y) == color:
            continue
        if map_data.zone_of(x, y) not in ("top lane", "bot lane"):
            continue
        mates = [q for j, q in enumerate(points) if j != i]
        if all(math.hypot(x - qx, y - qy) >= SPLIT_ALONE for qx, qy in mates):
            n += 1
    return n


def _in_enemy_jungle(points: list[tuple[float, float]], color: str) -> int:
    enemy = "red jungle" if color == "blue" else "blue jungle"
    return sum(1 for x, y in points if map_data.zone_of(x, y).startswith(enemy))


def map_features(state: GameState) -> dict:
    """Version 2 features: who is alive, the pits' timers, where players stand, recent wards."""
    t = state.t_ms
    b, r = state.teams[BLUE], state.teams[RED]
    alive = {BLUE: 0, RED: 0}
    dead_ms = {BLUE: 0, RED: 0}
    for p in state.players.values():
        if p.team in alive:
            alive[p.team] += p.dead_until_ms <= t
            dead_ms[p.team] += max(0, p.dead_until_ms - t)
    at = _located(state)
    setup = {}
    for name, spot, wait_ms in (
        ("baron", map_data.BARON_PIT, state.baron_pit_in_ms),
        ("dragon", map_data.DRAGON_PIT, state.dragon_pit_in_ms),
    ):
        contested = wait_ms <= SETUP_S * 1000
        setup[name] = (
            _near(at[BLUE], spot, PIT_RADIUS) - _near(at[RED], spot, PIT_RADIUS) if contested else 0
        )
    late = t >= SPLIT_FROM_MIN * 60_000
    return {
        "alive_diff": alive[BLUE] - alive[RED],
        "blue_dead_s": round(dead_ms[BLUE] / 1000),
        "red_dead_s": round(dead_ms[RED] / 1000),
        "baron_pit_in_s": round(state.baron_pit_in_ms / 1000),
        "dragon_pit_in_s": round(state.dragon_pit_in_ms / 1000),
        "baron_setup_diff": setup["baron"],
        "dragon_setup_diff": setup["dragon"],
        "grouped_diff": _largest_group(at[BLUE]) - _largest_group(at[RED]),
        "split_diff": (
            _split_pushers(at[BLUE], "blue") - _split_pushers(at[RED], "red") if late else 0
        ),
        "enemy_jungle_diff": _in_enemy_jungle(at[BLUE], "blue") - _in_enemy_jungle(at[RED], "red"),
        "wards_placed_diff": b.wards_placed - r.wards_placed,
        "wards_killed_diff": b.wards_killed - r.wards_killed,
    }


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
        "quest_diff": b.quests - r.quests,
        "inhibs_down_diff": r.inhibs_down - b.inhibs_down,
        "baron_active": side(b.baron_buff_end_ms > state.t_ms, r.baron_buff_end_ms > state.t_ms),
        "elder_active": side(b.elder_buff_end_ms > state.t_ms, r.elder_buff_end_ms > state.t_ms),
        "blue_dragons": len(b.dragons),
        "red_dragons": len(r.dragons),
        "soul_diff": side(b.soul is not None, r.soul is not None),
        "soul_type": state.map_soul_type,
        **map_features(state),
        "blue_champs": team_champions(state, BLUE),
        "red_champs": team_champions(state, RED),
    }


def team_champions(state: GameState, team: int) -> str:
    return ",".join(sorted(p.champion for p in state.players.values() if p.team == team))


def champion_features(blue_champs: str, red_champs: str, table: dict[str, dict]) -> dict:
    """`CHAMPION_FEATURES` for one game, blue minus red, from train.py's `champions.json`:
    the champions' win rates above 50% and how their win rates rise per minute of game length.
    Champions missing from the table count as 0. train.py computes the same, vectorised."""

    def total(champs: str, key: str, base: float) -> float:
        return sum(table[c][key] - base for c in champs.split(",") if c in table)

    return {
        "champ_wr_diff": total(blue_champs, "win_rate", 0.5) - total(red_champs, "win_rate", 0.5),
        "scaling_diff": total(blue_champs, "slope", 0.0) - total(red_champs, "slope", 0.0),
    }


def champions_from_timeline(timeline: dict) -> dict[int, str]:
    """participantId -> championName, from kill events' damage lists (the most common name each
    player gets there). In `victimDamageReceived` an entry's name is its participant's champion;
    in `victimDamageDealt` it is the victim's, and the participant is whoever was hit. Right for
    all 170 players of 17 real games checked; a player in no kill at all is left out."""
    votes: dict[int, dict[str, int]] = {}

    def vote(pid: int, name: str | None) -> None:
        if 1 <= pid <= 10 and name:
            names = votes.setdefault(pid, {})
            names[name] = names.get(name, 0) + 1

    for f in timeline["info"]["frames"]:
        for e in f["events"]:
            if e["type"] != "CHAMPION_KILL":
                continue
            for d in e.get("victimDamageReceived") or []:
                if d.get("type") == "OTHER":
                    vote(d.get("participantId", 0), d.get("name"))
            for d in e.get("victimDamageDealt") or []:
                vote(e.get("victimId", 0), d.get("name"))
    return {pid: max(names, key=lambda n: (names[n], n)) for pid, names in votes.items()}


def match_from_timeline(timeline: dict, patch: str) -> dict | None:
    """The parts of a match `extract_rows` needs, rebuilt from its timeline, or None without a
    GAME_END. Saves the crawler one request per game: it only asks for ranked solo games, the
    patch comes from the game id, and participants 1-5 are blue (true in 100 real games)."""
    info = timeline["info"]
    end = next((e for f in info["frames"] for e in f["events"] if e["type"] == "GAME_END"), None)
    if end is None:
        return None
    match_id = timeline["metadata"]["matchId"]
    winner = end.get("winningTeam")
    champions = champions_from_timeline(timeline)
    return {
        "metadata": {"matchId": match_id},
        "info": {
            "platformId": match_id.split("_")[0],
            "gameVersion": f"{patch}.0",
            "queueId": QUEUE_RANKED_SOLO,
            "gameDuration": end["timestamp"] // 1000,
            "participants": [
                {
                    "participantId": p["participantId"],
                    "teamId": BLUE if p["participantId"] <= 5 else RED,
                    "championName": champions.get(p["participantId"], ""),
                }
                for p in info["participants"]
            ],
            "teams": [
                {"teamId": BLUE, "win": winner == BLUE},
                {"teamId": RED, "win": winner == RED},
            ],
        },
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
    dicts = {"platform", "patch", "blue_champs", "red_champs"}
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
