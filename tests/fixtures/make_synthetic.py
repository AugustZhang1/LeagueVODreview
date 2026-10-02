"""Deterministic generator for synthetic match-v5 match + timeline JSON.

The games are made up but shaped like Riot's documented `/lol/match/v5/matches/{id}` and
`/timeline` responses. Run `python tests/fixtures/make_synthetic.py` to rewrite
`tests/fixtures/synthetic/`. Standard library only.
"""

import heapq
import json
import math
import random
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import consistency  # noqa: E402
from item_table import ITEMS, SELLABLE_STARTERS, next_component, plan_buy  # noqa: E402

OUT = HERE / "synthetic"
CFG = tomllib.loads((HERE.parents[1] / "config.toml").read_text())
BASE_RESPAWN = CFG["respawn"]["base_by_level"]
BLUE, RED = 100, 200
MAP_MAX = 14820

CHAMPS = {
    "Ahri": (103, "Ahri"),
    "Aphelios": (523, "Aphelios"),
    "Caitlyn": (51, "Caitlyn"),
    "Darius": (122, "Darius"),
    "Ezreal": (81, "Ezreal"),
    "Fiddlesticks": (9, "FiddleSticks"),
    "Garen": (86, "Garen"),
    "Gwen": (887, "Gwen"),
    "Braum": (201, "Braum"),
    "Jinx": (222, "Jinx"),
    "Kaisa": (145, "Kaisa"),
    "LeeSin": (64, "LeeSin"),
    "Leona": (89, "Leona"),
    "Lulu": (117, "Lulu"),
    "Malphite": (54, "Malphite"),
    "Nami": (267, "Nami"),
    "Orianna": (61, "Orianna"),
    "Ornn": (516, "Ornn"),
    "Rell": (526, "Rell"),
    "Renekton": (58, "Renekton"),
    "Sejuani": (113, "Sejuani"),
    "Samira": (360, "Samira"),
    "Syndra": (134, "Syndra"),
    "Thresh": (412, "Thresh"),
    "Vi": (254, "Vi"),
    "Viego": (234, "Viego"),
    "Viktor": (112, "Viktor"),
    "Wukong": (62, "MonkeyKing"),
    "XinZhao": (5, "XinZhao"),
    "Yone": (777, "Yone"),
    "Zed": (238, "Zed"),
}
BAN_POOL = [11, 21, 53, 76, 99, 103, 119, 157, 202, 245, 266, 350, 497, 555, 777]

BUILDS = {
    "TOP": [1055, 3047, 3053, 3075, 3068, 3143],
    "JUNGLE": [1101, 3006, 3071, 3053, 3075, 3143],
    "MIDDLE": [1056, 3020, 6655, 3089, 3135, 3157],
    "BOTTOM": [1055, 3006, 3031, 3085, 3036, 3033],
    "UTILITY": [3865, 3158, 6617, 3190, 3068, 3143],
}
SPELLS = {
    "TOP": (4, 12),
    "JUNGLE": (11, 4),
    "MIDDLE": (4, 14),
    "BOTTOM": (4, 7),
    "UTILITY": (4, 3),
}
LANE_ROLE = {"TOP": "TOP", "MID": "MIDDLE", "BOT": "BOTTOM"}
LANE_TYPE = {"TOP": "TOP_LANE", "MID": "MID_LANE", "BOT": "BOT_LANE"}

# Blue-side buildings (red mirrors them, with the lanes swapped: blue's TOP faces red's TOP).
BLUE_BUILDINGS = {
    ("TOP", "OUTER"): (981, 10441),
    ("TOP", "INNER"): (1512, 6699),
    ("TOP", "BASE"): (1169, 4287),
    ("TOP", "INHIB"): (1171, 3571),
    ("MID", "OUTER"): (5048, 4812),
    ("MID", "INNER"): (3651, 3696),
    ("MID", "BASE"): (3037, 3445),
    ("MID", "INHIB"): (3203, 3208),
    ("BOT", "OUTER"): (10504, 1029),
    ("BOT", "INNER"): (6919, 1483),
    ("BOT", "BASE"): (4281, 1253),
    ("BOT", "INHIB"): (3452, 1236),
    ("MID", "NEXUS_A"): (1748, 2270),
    ("MID", "NEXUS_B"): (2177, 1807),
}
MIRROR_LANE = {"TOP": "BOT", "MID": "MID", "BOT": "TOP"}
TOWER_TYPE = {
    "OUTER": "OUTER_TURRET",
    "INNER": "INNER_TURRET",
    "BASE": "BASE_TURRET",
    "NEXUS_A": "NEXUS_TURRET",
    "NEXUS_B": "NEXUS_TURRET",
}
BUILDING_BOUNTY = {
    "OUTER": 250,
    "INNER": 175,
    "BASE": 150,
    "INHIB": 50,
    "NEXUS_A": 50,
    "NEXUS_B": 50,
}
PLATE_GOLD = 125
PLATE_END_S = 840

MONSTER_BOUNTY = {
    "DRAGON": 100,
    "ELDER_DRAGON": 200,
    "BARON_NASHOR": 300,
    "RIFTHERALD": 50,
    "HORDE": 35,
    "ATAKHAN": 100,
}
PLACES = {
    "TOP": ((2500, 12500), 1200),
    "MID": ((7400, 7400), 1300),
    "BOT": ((12300, 2300), 1200),
    "dragon": ((9866, 4414), 450),
    "baron": ((5007, 10471), 450),
    "atakhan": ((6900, 8200), 500),
    "river": ((7400, 7400), 2500),
    "jg_blue_top": ((3500, 7600), 900),
    "jg_blue_bot": ((7000, 3500), 900),
    "jg_red_top": ((7800, 11300), 900),
    "jg_red_bot": ((11300, 7200), 900),
}
FOUNTAIN = {BLUE: (600, 600), RED: (MAP_MAX - 600, MAP_MAX - 600)}
JUNGLE_SPOTS = {
    BLUE: ["jg_blue_top", "jg_blue_bot", "jg_red_top", "jg_blue_top"],
    RED: ["jg_red_bot", "jg_red_top", "jg_blue_bot", "jg_red_bot"],
}


def building_pos(defender: int, lane: str, part: str) -> tuple[int, int]:
    if defender == BLUE:
        return BLUE_BUILDINGS[(lane, part)]
    if part.startswith("NEXUS"):
        x, y = BLUE_BUILDINGS[(lane, part)]
    else:
        x, y = BLUE_BUILDINGS[(MIRROR_LANE[lane], part)]
    return MAP_MAX - x, MAP_MAX - y


def respawn_s(level: int, t_s: float) -> float:
    r = CFG["respawn"]
    m = t_s / 60
    if m < r["scaling_start_min"]:
        factor = 0.0
    elif m < r["scaling_mid_min"]:
        factor = math.ceil(2 * (m - r["scaling_start_min"])) * r["scaling_early_step"]
    elif m < r["scaling_late_min"]:
        factor = (
            r["scaling_mid_base"]
            + math.ceil(2 * (m - r["scaling_mid_min"])) * r["scaling_mid_step"]
        )
    else:
        factor = (
            r["scaling_late_base"]
            + math.ceil(2 * (m - r["scaling_late_min"])) * r["scaling_late_step"]
        )
    return BASE_RESPAWN[level - 1] * (1 + min(factor, r["scaling_max"]))


def clamp(v: float) -> int:
    return int(max(0, min(MAP_MAX, v)))


class Player:
    def __init__(self, pid: int, role: str, champ: str, rng: random.Random):
        self.pid = pid
        self.team = BLUE if pid <= 5 else RED
        self.role = role
        self.champ_id, self.champ_name = CHAMPS[champ]
        self.skill = rng.uniform(0.88, 1.12)
        self.xp = 0.0
        self.level = 1
        self.cs = 0
        self.jcs = 0
        self.total_gold = 500.0
        self.spent = 0
        self.refund = 0
        self.items: list[int] = []
        self.k = self.d = self.a = 0
        self.streak = 0
        self.multi = 0
        self.last_kill_ms = -(10**9)
        self.death_ms = 0
        self.shop_on_respawn = False
        self.next_recall = 5
        self.ward_ready = rng.randint(90, 150)
        self.build = BUILDS[role]
        self.done: list[int] = []
        self.pos = FOUNTAIN[self.team]
        self.pos_until = 0
        self.dmg_champs = 0
        self.dmg_taken = 0
        self.cc_ms = 0
        self.skill_pts = 0
        self.turrets = 0
        self.inhibs = 0

    @property
    def gold(self) -> int:
        return int(self.total_gold) - self.spent + self.refund


class Sim:
    def __init__(self, game: dict):
        self.g = game
        self.rng = random.Random(game["seed"])
        self.players: dict[int, Player] = {}
        pid = 1
        for roster in (game["blue"], game["red"]):
            for role, champ in roster:
                self.players[pid] = Player(pid, role, champ, self.rng)
                pid += 1
        self.events: list[dict] = []
        self.frames: list[dict] = []
        self.heap: list[tuple[int, int, tuple]] = []
        self.seq = 0
        self.cursor = 0
        self.T = 0
        self.first_blood = False
        self.destroyed: dict[int, dict[tuple[str, str], int]] = {BLUE: {}, RED: {}}
        self.plates = {(BLUE, ln): 0 for ln in LANE_TYPE} | {(RED, ln): 0 for ln in LANE_TYPE}
        self.dragon_log: list[str] = []
        self.dragon_count = {BLUE: 0, RED: 0}
        self.soul_team = 0
        self.mon_gold = {BLUE: 0, RED: 0}

    # --- plumbing -------------------------------------------------------------------------
    def push(self, t: int, action: tuple) -> None:
        self.seq += 1
        heapq.heappush(self.heap, (t, self.seq, action))

    def now(self) -> int:
        ts = min(self.cursor, self.T * 1000 + 999)
        self.cursor += self.rng.randrange(40, 260)
        return ts

    def emit(self, ev: dict, ts: int) -> None:
        ev["timestamp"] = ts
        ev = {"type": ev.pop("type"), **dict(sorted(ev.items()))}
        self.events.append(ev)

    def alive(self, team: int, ts: int) -> list[Player]:
        return [p for p in self.players.values() if p.team == team and ts >= p.death_ms]

    def place_xy(self, place: str, jitter_scale: float = 1.0) -> dict:
        (cx, cy), j = PLACES[place]
        r = self.rng
        return {
            "x": clamp(cx + r.uniform(-j, j) * jitter_scale),
            "y": clamp(cy + r.uniform(-j, j) * jitter_scale),
        }

    def move(self, p: Player, pos: dict, ts: int) -> None:
        p.pos = (pos["x"] + self.rng.randint(-250, 250), pos["y"] + self.rng.randint(-250, 250))
        p.pos = (clamp(p.pos[0]), clamp(p.pos[1]))
        p.pos_until = ts + 14000

    def pick(self, pool: list[Player], weights: dict[str, float] | None = None) -> Player:
        w = [(weights or {}).get(p.role, 1.0) for p in pool]
        return self.rng.choices(pool, weights=w)[0]

    def give_gold(self, p: Player, amount: float) -> None:
        p.total_gold += amount

    def give_xp(self, p: Player, amount: float, ts: int) -> None:
        p.xp += amount
        self.level_check(p, ts)

    def level_check(self, p: Player, ts: int) -> None:
        target = consistency.level_from_xp(int(p.xp))
        while p.level < target:
            p.level += 1
            self.emit({"type": "LEVEL_UP", "level": p.level, "participantId": p.pid}, self.now())
            self.skill_up(p, self.now())

    def skill_up(self, p: Player, ts: int) -> None:
        slot = 4 if p.level in (6, 11, 16) else (p.level + p.pid) % 3 + 1
        self.emit(
            {
                "type": "SKILL_LEVEL_UP",
                "levelUpType": "NORMAL",
                "participantId": p.pid,
                "skillSlot": slot,
            },
            ts,
        )

    # --- shopping -------------------------------------------------------------------------
    def buy(self, p: Player, item: int, allow_undo: bool = True) -> bool:
        destroyed, paid = plan_buy(p.items, item)
        trinket = item in (3340, 3364)
        held = [i for i in p.items if i not in (3340, 3364)]
        if not trinket and len(held) - len(destroyed) >= 6:
            starter = next((i for i in p.items if i in SELLABLE_STARTERS), None)
            if starter is None or paid > p.gold + int(ITEMS[starter][1] * 0.7):
                return False
            p.items.remove(starter)
            p.refund += int(ITEMS[starter][1] * 0.7)
            self.emit({"type": "ITEM_SOLD", "itemId": starter, "participantId": p.pid}, self.now())
        if paid > p.gold:
            return False
        ts = self.now()
        for comp in destroyed:
            p.items.remove(comp)
            self.emit({"type": "ITEM_DESTROYED", "itemId": comp, "participantId": p.pid}, ts)
        p.items.append(item)
        p.spent += paid
        self.emit({"type": "ITEM_PURCHASED", "itemId": item, "participantId": p.pid}, ts)
        if allow_undo and not destroyed and paid >= 300 and self.rng.random() < 0.06:
            p.items.remove(item)
            p.spent -= paid
            self.emit(
                {
                    "type": "ITEM_UNDO",
                    "afterId": 0,
                    "beforeId": item,
                    "goldGain": paid,
                    "participantId": p.pid,
                },
                self.now(),
            )
        return True

    def shop(self, p: Player, T: int) -> None:
        first = T < 60
        if first:
            self.buy(p, 3340, allow_undo=False)
            if self.buy(p, p.build[0], allow_undo=False):
                p.done.append(p.build[0])
            if p.gold >= 50:
                self.buy(p, 2003, allow_undo=False)
                self.push(T + self.rng.randint(60, 170), ("destroy", p.pid, 2003))
            return
        if T >= 540 and p.role in ("JUNGLE", "UTILITY") and 3340 in p.items:
            p.items.remove(3340)
            self.emit({"type": "ITEM_SOLD", "itemId": 3340, "participantId": p.pid}, self.now())
            self.buy(p, 3364, allow_undo=False)
        if T > 180 and T < self.g["duration_s"] - 150 and self.rng.random() < 0.4:
            if self.buy(p, 2055, allow_undo=False):
                self.push(T + self.rng.randint(25, 80), ("ward", p.pid))
        for _ in range(8):
            target = next((i for i in p.build if i not in p.done), None)
            if target is None:
                break
            _, paid = plan_buy(p.items, target)
            if paid <= p.gold:
                if not self.buy(p, target):
                    break
                if target in p.items:
                    p.done.append(target)
                continue
            comp = next_component(p.items, target, p.gold)
            if comp is None or not self.buy(p, comp):
                break

    # --- economy --------------------------------------------------------------------------
    def economy(self, T: int) -> None:
        r = self.rng
        minute = T / 60
        for p in self.players.values():
            ts = T * 1000 + 500
            if ts < p.death_ms:
                continue
            if p.shop_on_respawn:
                p.shop_on_respawn = False
                if p.gold >= 300:
                    self.shop(p, T)
            if T >= p.next_recall and p.gold >= 500 and T > 60:
                p.next_recall = T + r.randint(300, 480)
                self.shop(p, T)
            if T >= 110:
                p.total_gold += 2.04
            lane_rate = {"TOP": 0.125, "MIDDLE": 0.125, "BOTTOM": 0.125, "JUNGLE": 0.012}
            if T >= 65 and r.random() < lane_rate.get(p.role, 0.015) * p.skill:
                p.cs += 1
                p.total_gold += 21
            if T >= 90 and p.role == "JUNGLE" and r.random() < 0.105 * p.skill:
                p.jcs += 1
                p.total_gold += 36
            if T >= 65:
                mult = {"UTILITY": 0.8}.get(p.role, 1.0)
                p.xp += (5.5 + 0.12 * minute) * mult * p.skill
                self.level_check(p, self.now())
            if T >= p.ward_ready and T >= 60:
                p.ward_ready = T + r.randint(60, 120)
                self.emit(
                    {"type": "WARD_PLACED", "creatorId": p.pid, "wardType": "YELLOW_TRINKET"},
                    self.now(),
                )
            if T > 150 and r.random() < 1 / 260:
                self.emit(
                    {
                        "type": "WARD_KILL",
                        "killerId": p.pid,
                        "wardType": r.choice(["YELLOW_TRINKET", "CONTROL_WARD"]),
                    },
                    self.now(),
                )
            if T >= 15 and T < 180:
                p.dmg_taken += r.randint(0, 6)
            elif T >= 180:
                p.dmg_taken += r.randint(0, 14)
            p.dmg_champs += r.randint(0, 5) if T >= 180 else 0

    # --- scripted actions -----------------------------------------------------------------
    def run_action(self, action: tuple, T: int) -> bool:
        kind = action[0]
        ts = self.now()
        if kind == "fight":
            _, _, winner, kw, kl, place = action
            n = kw + kl
            offsets = sorted(self.rng.sample(range(0, 16), n)) if n <= 16 else list(range(n))
            sides = [winner] * kw + [BLUE + RED - winner] * kl
            self.rng.shuffle(sides)
            for off, side in zip(offsets, sides, strict=True):
                self.push(T + off, ("kill", side, BLUE + RED - side, place))
            return True
        if kind == "kill":
            return self.do_kill(action[1], action[2], action[3], ts)
        if kind == "mon":
            return self.do_mon(action[2], action[3], action[4] if len(action) > 4 else None, ts)
        if kind == "bld":
            return self.do_building(action[2], action[3], action[4], ts)
        if kind == "plates":
            return self.do_plates(action[2], action[3], action[4], ts)
        if kind == "destroy":
            p = self.players[action[1]]
            if action[2] in p.items:
                p.items.remove(action[2])
                self.emit(
                    {"type": "ITEM_DESTROYED", "itemId": action[2], "participantId": p.pid}, ts
                )
            return True
        if kind == "ward":
            p = self.players[action[1]]
            if ts < p.death_ms:
                return False
            if 2055 in p.items:
                p.items.remove(2055)
                self.emit(
                    {"type": "WARD_PLACED", "creatorId": p.pid, "wardType": "CONTROL_WARD"}, ts
                )
                self.emit({"type": "ITEM_DESTROYED", "itemId": 2055, "participantId": p.pid}, ts)
            return True
        raise ValueError(kind)

    def do_kill(self, att: int, vic: int, place: str, ts: int) -> bool:
        killers, victims = self.alive(att, ts), self.alive(vic, ts)
        if not killers or not victims:
            return True
        kweights = {"UTILITY": 0.5, "JUNGLE": 1.2, "MIDDLE": 1.4, "BOTTOM": 1.4, "TOP": 1.0}
        killer = self.pick(killers, kweights)
        victim = self.pick(victims)
        mates = [p for p in killers if p is not killer]
        n_assist = min(len(mates), self.rng.choices([0, 1, 2, 3, 4], [1, 4, 4, 3, 1])[0])
        assists = self.rng.sample(mates, n_assist)
        pos = self.place_xy(place)
        shutdown = 0
        if victim.streak >= 3:
            shutdown = {3: 150, 4: 200}.get(victim.streak, 300)
        bounty = 400 if not self.first_blood else 300
        self.emit(
            {
                "type": "CHAMPION_KILL",
                "assistingParticipantIds": sorted(a.pid for a in assists),
                "bounty": bounty,
                "killStreakLength": killer.streak,
                "killerId": killer.pid,
                "position": pos,
                "shutdownBounty": shutdown,
                "victimId": victim.pid,
            },
            ts,
        )
        if not self.first_blood:
            self.first_blood = True
            self.emit(
                {
                    "type": "CHAMPION_SPECIAL_KILL",
                    "killType": "KILL_FIRST_BLOOD",
                    "killerId": killer.pid,
                    "position": pos,
                },
                ts,
            )
        if ts - killer.last_kill_ms <= 10000:
            killer.multi = min(killer.multi + 1, 5)
        else:
            killer.multi = 1
        killer.last_kill_ms = ts
        if killer.multi >= 2:
            self.emit(
                {
                    "type": "CHAMPION_SPECIAL_KILL",
                    "killType": "KILL_MULTI",
                    "killerId": killer.pid,
                    "multiKillLength": killer.multi,
                    "position": pos,
                },
                ts,
            )
        victim.death_ms = ts + int(respawn_s(victim.level, ts / 1000) * 1000)
        victim.shop_on_respawn = True
        if not self.alive(vic, ts):
            self.emit(
                {
                    "type": "CHAMPION_SPECIAL_KILL",
                    "killType": "KILL_ACE",
                    "killerId": killer.pid,
                    "position": pos,
                    "teamId": att,
                },
                ts,
            )
        killer.k += 1
        killer.streak += 1
        victim.d += 1
        victim.streak = 0
        self.give_gold(killer, bounty + shutdown)
        self.give_xp(killer, 120 + 12 * victim.level, ts)
        killer.dmg_champs += self.rng.randint(900, 2400)
        victim.dmg_taken += self.rng.randint(1200, 2600)
        victim.cc_ms += self.rng.randint(0, 1500)
        for a in assists:
            a.a += 1
            self.give_gold(a, bounty * 0.5 / max(1, len(assists)))
            self.give_xp(a, 60, ts)
            a.dmg_champs += self.rng.randint(300, 1200)
            a.cc_ms += self.rng.randint(0, 3500)
            self.move(a, pos, ts)
        self.move(killer, pos, ts)
        return True

    def team_killers(self, team: int, ts: int, jungle_first: bool = False):
        alive = self.alive(team, ts)
        if not alive:
            return None
        killer = self.pick(alive, {"JUNGLE": 8.0 if jungle_first else 1.0})
        mates = [p for p in alive if p is not killer]
        assists = self.rng.sample(mates, self.rng.randint(0, len(mates)))
        return killer, assists

    def do_mon(self, team: int, mtype: str, sub: str | None, ts: int) -> bool:
        got = self.team_killers(team, ts, jungle_first=True)
        if got is None:
            return False
        killer, assists = got
        key = sub if sub == "ELDER_DRAGON" else mtype
        bounty = MONSTER_BOUNTY[key]
        place = {
            "DRAGON": "dragon",
            "BARON_NASHOR": "baron",
            "RIFTHERALD": "baron",
            "HORDE": "baron",
            "ATAKHAN": "atakhan",
        }[mtype]
        pos = self.place_xy(place)
        ev = {
            "type": "ELITE_MONSTER_KILL",
            "assistingParticipantIds": sorted(a.pid for a in assists),
            "bounty": bounty,
            "killerId": killer.pid,
            "killerTeamId": team,
            "monsterType": mtype,
            "position": pos,
        }
        if sub:
            ev["monsterSubType"] = sub
        self.emit(ev, ts)
        for p in self.players.values():
            if p.team == team:
                self.give_gold(p, bounty)
        for p in [killer, *assists]:
            self.move(p, pos, ts)
            self.give_xp(p, 80 if mtype != "BARON_NASHOR" else 300, ts)
        if mtype == "DRAGON" and sub != "ELDER_DRAGON":
            self.dragon_log.append(sub)
            self.dragon_count[team] += 1
            if self.dragon_count[team] == 4 and not self.soul_team:
                self.soul_team = team
                name = consistency_soul(self.dragon_log[2])
                self.emit({"type": "DRAGON_SOUL_GIVEN", "name": name, "teamId": team}, ts)
        return True

    def do_building(self, team: int, lane: str, part: str, ts: int) -> bool:
        defender = BLUE + RED - team
        down = self.destroyed[defender]
        if part.startswith("NEXUS"):
            assert any(
                k[1] == "INHIB" and ts < v + CFG["timers"]["inhibitor_respawn_s"] * 1000
                for k, v in down.items()
            ), "nexus turrets need a fallen inhibitor"
            assert (lane, part) not in down
        elif part == "INHIB":
            assert (lane, "BASE") in down
            if (lane, "INHIB") in down:
                assert ts >= down[(lane, "INHIB")] + CFG["timers"]["inhibitor_respawn_s"] * 1000
        else:
            prev = {"OUTER": None, "INNER": "OUTER", "BASE": "INNER"}[part]
            assert prev is None or (lane, prev) in down, f"{part} before {prev} in {lane}"
            assert (lane, part) not in down
        got = self.team_killers(team, ts)
        if got is None:
            return False
        killer, assists = got
        assists = assists[:3]
        pos = building_pos(defender, lane, part)
        bounty = BUILDING_BOUNTY[part]
        ev = {
            "type": "BUILDING_KILL",
            "assistingParticipantIds": sorted(a.pid for a in assists),
            "bounty": bounty,
            "buildingType": "INHIBITOR_BUILDING" if part == "INHIB" else "TOWER_BUILDING",
            "killerId": killer.pid,
            "laneType": LANE_TYPE[lane],
            "position": {"x": pos[0], "y": pos[1]},
            "teamId": defender,
        }
        if part != "INHIB":
            ev["towerType"] = TOWER_TYPE[part]
        self.emit(ev, ts)
        down[(lane, part)] = ts
        self.give_gold(killer, bounty)
        for p in assists:
            self.give_gold(p, bounty * 0.3)
        for p in [killer, *assists]:
            self.move(p, {"x": pos[0], "y": pos[1]}, ts)
        if part == "INHIB":
            killer.inhibs += 1
        else:
            killer.turrets += 1
        return True

    def do_plates(self, team: int, lane: str, n: int, ts: int) -> bool:
        defender = BLUE + RED - team
        assert ts < PLATE_END_S * 1000
        assert (lane, "OUTER") not in self.destroyed[defender]
        assert self.plates[(defender, lane)] + n <= 5
        alive = self.alive(team, ts)
        if not alive:
            return False
        laner = [p for p in alive if p.role == LANE_ROLE[lane]]
        pos = building_pos(defender, lane, "OUTER")
        for _ in range(n):
            killer = self.pick(laner or alive)
            self.plates[(defender, lane)] += 1
            self.emit(
                {
                    "type": "TURRET_PLATE_DESTROYED",
                    "killerId": killer.pid,
                    "laneType": LANE_TYPE[lane],
                    "position": {"x": pos[0] + 100, "y": pos[1]},
                    "teamId": defender,
                },
                self.now(),
            )
            self.give_gold(killer, PLATE_GOLD)
            self.move(killer, {"x": pos[0], "y": pos[1]}, ts)
        return True

    # --- frames ---------------------------------------------------------------------------
    def idle_pos(self, p: Player, T: int) -> tuple[int, int]:
        r = self.rng
        if T * 1000 < p.death_ms or T < 20:
            fx, fy = FOUNTAIN[p.team]
            return clamp(fx + r.randint(-150, 150)), clamp(fy + r.randint(-150, 150))
        if T * 1000 < p.pos_until:
            return p.pos
        if T < 840:
            if p.role == "JUNGLE":
                place = JUNGLE_SPOTS[p.team][(T // 60) % 4]
                (cx, cy), j = PLACES[place]
                return clamp(cx + r.randint(-j, j)), clamp(cy + r.randint(-j, j))
            lane = {"TOP": "TOP", "MIDDLE": "MID", "BOTTOM": "BOT", "UTILITY": "BOT"}[p.role]
        else:
            lane = r.choice(["MID", "MID", "BOT", "TOP"])
            if p.role == "TOP" and r.random() < 0.6:
                lane = "TOP"
        (cx, cy), _ = PLACES[lane]
        bx, by = FOUNTAIN[p.team]
        u = r.uniform(0.08, 0.32) if T < 840 else r.uniform(-0.1, 0.2)
        return clamp(cx + (bx - cx) * u + r.randint(-350, 350)), clamp(
            cy + (by - cy) * u + r.randint(-350, 350)
        )

    def frame(self, ts: int) -> dict:
        T = ts // 1000
        pfs = {}
        for pid, p in self.players.items():
            x, y = self.idle_pos(p, T)
            level = p.level
            champ_stats = {
                "abilityHaste": 0 + 5 * level // 3,
                "abilityPower": 0 + 12 * len(p.items),
                "armor": 30 + 4 * level,
                "armorPen": 0,
                "armorPenPercent": 0,
                "attackDamage": 60 + 4 * level + 8 * len(p.items),
                "attackSpeed": 100 + 2 * level,
                "bonusArmorPenPercent": 0,
                "bonusMagicPenPercent": 0,
                "ccReduction": 0,
                "cooldownReduction": 0,
                "health": 500 + 80 * level,
                "healthMax": 600 + 90 * level + 40 * len(p.items),
                "healthRegen": 6 + level,
                "lifesteal": 0,
                "magicPen": 0,
                "magicPenPercent": 0,
                "magicResist": 30 + 1 * level,
                "movementSpeed": 330 + 5 * len(p.items),
                "omnivamp": 0,
                "physicalVamp": 0,
                "power": 300 + 30 * level,
                "powerMax": 300 + 30 * level,
                "powerRegen": 8 + level,
                "spellVamp": 0,
            }
            dealt = p.dmg_champs
            total_dealt = dealt + 40 * (p.cs + p.jcs)
            dmg = {
                "magicDamageDone": total_dealt // 2,
                "magicDamageDoneToChampions": dealt // 2,
                "magicDamageTaken": p.dmg_taken // 3,
                "physicalDamageDone": total_dealt - total_dealt // 2,
                "physicalDamageDoneToChampions": dealt - dealt // 2,
                "physicalDamageTaken": p.dmg_taken - p.dmg_taken // 3 - p.dmg_taken // 20,
                "totalDamageDone": total_dealt,
                "totalDamageDoneToChampions": dealt,
                "totalDamageTaken": p.dmg_taken - p.dmg_taken // 20,
                "trueDamageDone": 0,
                "trueDamageDoneToChampions": 0,
                "trueDamageTaken": p.dmg_taken // 20,
            }
            pfs[str(pid)] = {
                "championStats": champ_stats,
                "currentGold": p.gold,
                "damageStats": dmg,
                "goldPerSecond": 0,
                "jungleMinionsKilled": p.jcs,
                "level": consistency.level_from_xp(int(p.xp)),
                "minionsKilled": p.cs,
                "participantId": pid,
                "position": {"x": x, "y": y},
                "timeEnemySpentControlled": p.cc_ms,
                "totalGold": int(p.total_gold),
                "xp": int(p.xp),
            }
        return {"timestamp": ts, "participantFrames": pfs, "events": []}

    # --- driver ---------------------------------------------------------------------------
    def run(self) -> None:
        end = self.g["duration_s"]
        for item in self.g["script"]:
            self.push(item[1], item)
        for T in range(end):
            self.T = T
            self.cursor = T * 1000 + self.rng.randrange(0, 200)
            if T % 60 == 0:
                self.frames.append(self.frame(T * 1000))
            if T == 2:
                for p in self.players.values():
                    self.skill_up(p, self.now())
            if T in (3, 4, 5):
                for p in self.players.values():
                    if p.pid % 3 == T - 3:
                        self.shop(p, T)
            self.economy(T)
            while self.heap and self.heap[0][0] <= T:
                t, _, action = heapq.heappop(self.heap)
                if not self.run_action(action, T):
                    self.push(T + 3, action)
        assert not self.heap, f"{self.g['match_id']}: unexecuted actions {self.heap[:3]}"
        self.T = end
        end_ms = end * 1000 + self.rng.randrange(0, 900)
        self.events.append(
            {
                "type": "GAME_END",
                "gameId": self.g["game_id"],
                "realTimestamp": self.g["start_ms"] + end_ms,
                "timestamp": end_ms,
                "winningTeam": self.g["winner"],
            }
        )
        self.frames.append(self.frame(end_ms))
        stamps = [f["timestamp"] for f in self.frames]
        for ev in self.events:
            idx = next(i for i, s in enumerate(stamps) if ev["timestamp"] <= s)
            self.frames[idx]["events"].append(ev)


def consistency_soul(subtype: str) -> str:
    names = {
        "FIRE_DRAGON": "Infernal",
        "EARTH_DRAGON": "Mountain",
        "WATER_DRAGON": "Ocean",
        "AIR_DRAGON": "Cloud",
        "HEXTECH_DRAGON": "Hextech",
        "CHEMTECH_DRAGON": "Chemtech",
    }
    return names[subtype]


# --- scenarios -----------------------------------------------------------------------------
def fight(t, winner, kw, kl, place):
    return ("fight", t, winner, kw, kl, place)


def mon(t, team, mtype, sub=None):
    return ("mon", t, team, mtype, sub)


def bld(t, team, lane, part):
    return ("bld", t, team, lane, part)


def plates(t, team, lane, n):
    return ("plates", t, team, lane, n)


D = "DRAGON"
FIRE, EARTH, WATER, AIR = "FIRE_DRAGON", "EARTH_DRAGON", "WATER_DRAGON", "AIR_DRAGON"
HEX, CHEM, ELDER = "HEXTECH_DRAGON", "CHEMTECH_DRAGON", "ELDER_DRAGON"

SCRIPT_1 = [
    fight(215, BLUE, 1, 0, "TOP"),
    fight(290, RED, 1, 0, "BOT"),
    fight(320, BLUE, 2, 1, "dragon"),
    mon(345, BLUE, D, FIRE),
    mon(490, BLUE, "HORDE"),
    mon(494, BLUE, "HORDE"),
    mon(498, BLUE, "HORDE"),
    plates(520, BLUE, "TOP", 2),
    plates(600, RED, "BOT", 2),
    fight(650, BLUE, 2, 2, "MID"),
    mon(700, BLUE, D, WATER),
    plates(730, BLUE, "MID", 3),
    plates(780, RED, "TOP", 2),
    bld(810, BLUE, "MID", "OUTER"),
    bld(835, RED, "TOP", "OUTER"),
    fight(985, RED, 3, 1, "baron"),
    mon(1010, RED, "RIFTHERALD"),
    mon(1040, BLUE, D, HEX),
    fight(1100, BLUE, 3, 1, "MID"),
    bld(1135, BLUE, "MID", "INNER"),
    bld(1170, BLUE, "BOT", "OUTER"),
    fight(1300, BLUE, 4, 1, "dragon"),
    mon(1370, BLUE, D, EARTH),
    fight(1560, BLUE, 4, 0, "baron"),
    mon(1600, BLUE, "BARON_NASHOR"),
    bld(1625, BLUE, "BOT", "INNER"),
    bld(1650, BLUE, "BOT", "BASE"),
    bld(1675, BLUE, "BOT", "INHIB"),
    bld(1700, BLUE, "MID", "BASE"),
    bld(1730, BLUE, "MID", "INHIB"),
    fight(1790, BLUE, 3, 1, "MID"),
    bld(1815, BLUE, "MID", "NEXUS_A"),
    bld(1828, BLUE, "MID", "NEXUS_B"),
]

SCRIPT_2 = [
    fight(190, RED, 1, 0, "BOT"),
    fight(260, RED, 1, 1, "TOP"),
    mon(350, RED, D, AIR),
    mon(490, BLUE, "HORDE"),
    mon(494, BLUE, "HORDE"),
    mon(498, BLUE, "HORDE"),
    plates(500, RED, "BOT", 3),
    plates(560, BLUE, "TOP", 2),
    fight(640, RED, 2, 1, "MID"),
    mon(700, BLUE, D, WATER),
    plates(760, RED, "MID", 3),
    fight(800, RED, 3, 2, "BOT"),
    bld(850, RED, "BOT", "OUTER"),
    bld(880, RED, "MID", "OUTER"),
    bld(1005, BLUE, "TOP", "OUTER"),
    mon(1010, RED, D, FIRE),
    mon(990, RED, "RIFTHERALD"),
    fight(1110, RED, 3, 1, "MID"),
    bld(1150, RED, "MID", "INNER"),
    bld(1185, RED, "BOT", "INNER"),
    fight(1250, RED, 4, 1, "BOT"),
    bld(1290, RED, "BOT", "BASE"),
    fight(1330, RED, 5, 0, "baron"),
    mon(1360, RED, "BARON_NASHOR"),
    bld(1400, RED, "BOT", "INHIB"),
    fight(1425, RED, 3, 1, "MID"),
]

SCRIPT_3 = [
    fight(220, BLUE, 1, 0, "TOP"),
    fight(300, RED, 1, 1, "BOT"),
    mon(345, BLUE, D, AIR),
    mon(490, RED, "HORDE"),
    mon(494, RED, "HORDE"),
    mon(498, RED, "HORDE"),
    plates(480, RED, "TOP", 3),
    plates(600, BLUE, "MID", 2),
    plates(700, BLUE, "BOT", 3),
    fight(640, BLUE, 3, 2, "river"),
    mon(665, RED, D, WATER),
    bld(760, BLUE, "MID", "OUTER"),
    bld(880, RED, "TOP", "OUTER"),
    bld(900, BLUE, "BOT", "OUTER"),
    fight(960, BLUE, 3, 1, "dragon"),
    mon(985, BLUE, D, FIRE),
    bld(1000, RED, "MID", "OUTER"),
    mon(1030, RED, "RIFTHERALD"),
    bld(1100, RED, "BOT", "OUTER"),
    bld(1190, BLUE, "MID", "INNER"),
    fight(1260, BLUE, 3, 1, "atakhan"),
    mon(1305, BLUE, D, EARTH),
    mon(1360, BLUE, "ATAKHAN"),
    fight(1430, RED, 3, 2, "baron"),
    mon(1460, RED, "BARON_NASHOR"),
    bld(1500, RED, "TOP", "INNER"),
    fight(1590, BLUE, 3, 1, "dragon"),
    mon(1625, BLUE, D, CHEM),
    bld(1640, BLUE, "MID", "BASE"),
    bld(1700, BLUE, "MID", "INHIB"),
    bld(1740, BLUE, "BOT", "INNER"),
    fight(1800, BLUE, 4, 1, "MID"),
    bld(1840, BLUE, "BOT", "BASE"),
    bld(1880, BLUE, "BOT", "INHIB"),
    fight(1960, BLUE, 3, 2, "baron"),
    mon(2000, BLUE, "BARON_NASHOR"),
    fight(2020, BLUE, 3, 1, "dragon"),
    mon(2060, BLUE, D, ELDER),
    bld(2080, BLUE, "MID", "INHIB"),
    fight(2150, BLUE, 4, 1, "MID"),
    bld(2230, BLUE, "MID", "NEXUS_A"),
    bld(2244, BLUE, "MID", "NEXUS_B"),
]

GAMES = [
    {
        "match_id": "NA1_9000000001",
        "seed": 1001,
        "me": 4,
        "start_ms": datetime(2026, 9, 28, 1, 5, 11, tzinfo=UTC),
        "duration_s": 1865,
        "winner": BLUE,
        "end": "nexus",
        "blue": [
            ("TOP", "Ornn"),
            ("JUNGLE", "LeeSin"),
            ("BOTTOM", "Kaisa"),
            ("MIDDLE", "Ahri"),
            ("UTILITY", "Nami"),
        ],
        "red": [
            ("TOP", "Darius"),
            ("JUNGLE", "Vi"),
            ("MIDDLE", "Zed"),
            ("BOTTOM", "Caitlyn"),
            ("UTILITY", "Lulu"),
        ],
        "script": SCRIPT_1,
    },
    {
        "match_id": "NA1_9000000002",
        "seed": 1002,
        "me": 9,
        "start_ms": datetime(2026, 9, 28, 3, 20, 40, tzinfo=UTC),
        "duration_s": 1470,
        "winner": RED,
        "end": "surrender",
        "blue": [
            ("TOP", "Garen"),
            ("JUNGLE", "Sejuani"),
            ("MIDDLE", "Syndra"),
            ("BOTTOM", "Ezreal"),
            ("UTILITY", "Braum"),
        ],
        "red": [
            ("TOP", "Renekton"),
            ("JUNGLE", "XinZhao"),
            ("MIDDLE", "Orianna"),
            ("BOTTOM", "Jinx"),
            ("UTILITY", "Leona"),
        ],
        "script": SCRIPT_2,
    },
    {
        "match_id": "NA1_9000000003",
        "seed": 1003,
        "me": 2,
        "start_ms": datetime(2026, 9, 29, 22, 47, 5, tzinfo=UTC),
        "duration_s": 2285,
        "winner": BLUE,
        "end": "nexus",
        "blue": [
            ("TOP", "Malphite"),
            ("JUNGLE", "Wukong"),
            ("MIDDLE", "Yone"),
            ("BOTTOM", "Samira"),
            ("UTILITY", "Rell"),
        ],
        "red": [
            ("TOP", "Gwen"),
            ("JUNGLE", "Fiddlesticks"),
            ("MIDDLE", "Viktor"),
            ("BOTTOM", "Aphelios"),
            ("UTILITY", "Thresh"),
        ],
        "script": SCRIPT_3,
    },
    {
        "match_id": "NA1_9000000004",
        "seed": 1004,
        "me": 5,
        "start_ms": datetime(2026, 9, 30, 2, 2, 30, tzinfo=UTC),
        "duration_s": 190,
        "winner": 0,
        "end": "remake",
        "blue": [
            ("TOP", "Garen"),
            ("JUNGLE", "LeeSin"),
            ("MIDDLE", "Ahri"),
            ("BOTTOM", "Jinx"),
            ("UTILITY", "Thresh"),
        ],
        "red": [
            ("TOP", "Ornn"),
            ("JUNGLE", "Viego"),
            ("MIDDLE", "Zed"),
            ("BOTTOM", "Caitlyn"),
            ("UTILITY", "Lulu"),
        ],
        "script": [],
    },
]


# --- output --------------------------------------------------------------------------------
def fake_puuid(rng: random.Random) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    return "".join(rng.choice(alphabet) for _ in range(78))


def build_match(g: dict, sim: Sim, puuids: dict[int, str]) -> dict:
    ev = sim.events
    start = g["start_ms"]
    end_ms = ev[-1]["timestamp"]
    kind = g["end"]
    parts = []
    for pid, p in sim.players.items():
        name = "Me" if pid == g["me"] else f"Synth{pid}"
        spells = SPELLS[p.role]
        slots = [i for i in p.items if i not in (3340, 3364)]
        trinket = next((i for i in p.items if i in (3340, 3364)), 0)
        slots = (slots + [0] * 6)[:6]
        win = kind != "remake" and p.team == g["winner"]
        parts.append(
            {
                "assists": p.a,
                "baronKills": sum(
                    1
                    for e in ev
                    if e["type"] == "ELITE_MONSTER_KILL"
                    and e["monsterType"] == "BARON_NASHOR"
                    and e["killerId"] == pid
                ),
                "champExperience": int(p.xp),
                "champLevel": p.level,
                "championId": p.champ_id,
                "championName": p.champ_name,
                "deaths": p.d,
                "dragonKills": sum(
                    1
                    for e in ev
                    if e["type"] == "ELITE_MONSTER_KILL"
                    and e["monsterType"] == "DRAGON"
                    and e["killerId"] == pid
                ),
                "gameEndedInEarlySurrender": kind == "remake",
                "gameEndedInSurrender": kind == "surrender",
                "goldEarned": int(p.total_gold),
                "goldSpent": p.spent,
                "individualPosition": p.role,
                "inhibitorKills": p.inhibs,
                "item0": slots[0],
                "item1": slots[1],
                "item2": slots[2],
                "item3": slots[3],
                "item4": slots[4],
                "item5": slots[5],
                "item6": trinket,
                "kills": p.k,
                "lane": {"MIDDLE": "MIDDLE", "UTILITY": "BOTTOM"}.get(p.role, p.role),
                "neutralMinionsKilled": p.jcs,
                "participantId": pid,
                "profileIcon": 1000 + pid,
                "puuid": puuids[pid],
                "riotIdGameName": name,
                "riotIdTagline": "NA1",
                "role": "SOLO" if p.role in ("TOP", "MIDDLE", "JUNGLE") else "DUO",
                "summoner1Id": spells[0],
                "summoner2Id": spells[1],
                "summonerLevel": 100 + pid,
                "teamEarlySurrendered": kind == "remake" and p.team == RED,
                "teamId": p.team,
                "teamPosition": p.role,
                "timePlayed": g["duration_s"],
                "totalDamageDealtToChampions": p.dmg_champs,
                "totalMinionsKilled": p.cs,
                "turretKills": p.turrets,
                "visionScore": int(g["duration_s"] / 60 * (2.4 if p.role == "UTILITY" else 0.9)),
                "win": win,
            }
        )
    teams = []
    for team in (BLUE, RED):
        rng = random.Random(g["seed"] * 7 + team)
        bans = [{"championId": c, "pickTurn": i + 1} for i, c in enumerate(rng.sample(BAN_POOL, 5))]
        objectives = {
            "baron": "BARON_NASHOR",
            "champion": None,
            "dragon": "DRAGON",
            "horde": "HORDE",
            "inhibitor": None,
            "riftHerald": "RIFTHERALD",
            "tower": None,
            "atakhan": "ATAKHAN",
        }
        obj = {}
        for key, mtype in objectives.items():
            if key == "champion":
                mine = [
                    e
                    for e in ev
                    if e["type"] == "CHAMPION_KILL" and (e["killerId"] <= 5) == (team == BLUE)
                ]
            elif key in ("tower", "inhibitor"):
                btype = "TOWER_BUILDING" if key == "tower" else "INHIBITOR_BUILDING"
                mine = [
                    e
                    for e in ev
                    if e["type"] == "BUILDING_KILL"
                    and e["buildingType"] == btype
                    and e["teamId"] != team
                ]
            else:
                mine = [
                    e
                    for e in ev
                    if e["type"] == "ELITE_MONSTER_KILL"
                    and e["monsterType"] == mtype
                    and e["killerTeamId"] == team
                ]
            firsts = [e for e in ev if e in mine][:1]
            others = {
                "champion": lambda e: e["type"] == "CHAMPION_KILL",
                "tower": lambda e: (
                    e["type"] == "BUILDING_KILL" and e["buildingType"] == "TOWER_BUILDING"
                ),
                "inhibitor": lambda e: (
                    e["type"] == "BUILDING_KILL" and e["buildingType"] == "INHIBITOR_BUILDING"
                ),
            }
            if key in others:
                allk = [e for e in ev if others[key](e)]
            else:
                allk = [
                    e for e in ev if e["type"] == "ELITE_MONSTER_KILL" and e["monsterType"] == mtype
                ]
            obj[key] = {"first": bool(firsts) and allk[0] is firsts[0], "kills": len(mine)}
        teams.append(
            {
                "bans": bans,
                "objectives": obj,
                "teamId": team,
                "win": kind != "remake" and team == g["winner"],
            }
        )
    return {
        "metadata": {
            "dataVersion": "2",
            "matchId": g["match_id"],
            "participants": [puuids[i] for i in range(1, 11)],
        },
        "info": {
            "endOfGameResult": "GameComplete",
            "gameCreation": start - 70000,
            "gameDuration": g["duration_s"],
            "gameEndTimestamp": start + end_ms + 2500,
            "gameId": g["game_id"],
            "gameMode": "CLASSIC",
            "gameStartTimestamp": start,
            "gameType": "MATCHED_GAME",
            "gameVersion": "26.19.712.4021",
            "mapId": 11,
            "participants": parts,
            "platformId": "NA1",
            "queueId": 420,
            "teams": teams,
            "tournamentCode": "",
        },
    }


def build_timeline(g: dict, sim: Sim, puuids: dict[int, str]) -> dict:
    return {
        "metadata": {
            "dataVersion": "2",
            "matchId": g["match_id"],
            "participants": [puuids[i] for i in range(1, 11)],
        },
        "info": {
            "endOfGameResult": "GameComplete",
            "frameInterval": 60000,
            "frames": sim.frames,
            "gameId": g["game_id"],
            "participants": [{"participantId": i, "puuid": puuids[i]} for i in range(1, 11)],
        },
    }


def generate(g: dict) -> tuple[dict, dict]:
    g = dict(g)
    g["game_id"] = int(g["match_id"].split("_")[1])
    g["start_ms"] = int(g["start_ms"].timestamp() * 1000)
    sim = Sim(g)
    sim.run()
    prng = random.Random(g["seed"] + 5)
    me_puuid = "MeSynthPuuid" + "x" * 66
    puuids = {pid: (me_puuid if pid == g["me"] else fake_puuid(prng)) for pid in range(1, 11)}
    match = build_match(g, sim, puuids)
    timeline = build_timeline(g, sim, puuids)
    return match, timeline


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for g in GAMES:
        match, timeline = generate(g)
        consistency.check_all(match, timeline)
        dump(OUT / f"{g['match_id']}.match.json", match)
        dump(OUT / f"{g['match_id']}.timeline.json", timeline)
        print(g["match_id"], "ok", len(timeline["info"]["frames"]), "frames")


if __name__ == "__main__":
    main()
