import type {
  Building,
  CurvePoint,
  FightDamage,
  GameEvent,
  GradeCounts,
  Moment,
  Player,
  PlayerState,
  Review,
  Role,
  Side,
  Snapshot,
  TeamState,
} from "../api/models";
import type { Grade } from "../lib/grades";

/**
 * A deterministic 31:42 ranked game for "Me#NA1" playing Ahri mid (participant 4),
 * built from a hand-written script of moments. Nothing here is random at run time.
 */

const DURATION = 1902;
const STEP = 15;
const BASE_RESPAWN = [
  6, 6, 8, 8, 10, 12, 16, 21, 26.5, 32.5, 35, 37.5, 40, 42.5, 45, 47.5, 50, 52.5,
];

function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Ref = "aT" | "aJ" | "aM" | "aB" | "aS" | "eT" | "eJ" | "eM" | "eB" | "eS";

type RosterEntry = {
  ref: Ref;
  id: number;
  role: Role;
  champion: string;
  name: string;
  riotId: string;
  starter: number;
  csPerMin: number;
  build: number[];
};

const ROSTER: RosterEntry[] = [
  {
    ref: "aT",
    id: 1,
    role: "TOP",
    champion: "Camille",
    name: "Camille",
    riotId: "Friend#1234",
    starter: 1055,
    csPerMin: 6.4,
    build: [3047, 3078, 6692, 3053, 3071, 3026],
  },
  {
    ref: "aJ",
    id: 2,
    role: "JUNGLE",
    champion: "Vi",
    name: "Vi",
    riotId: "Junglist#NA1",
    starter: 1101,
    csPerMin: 5.2,
    build: [3047, 6692, 3071, 3053, 3036, 3026],
  },
  {
    ref: "aM",
    id: 4,
    role: "MIDDLE",
    champion: "Ahri",
    name: "Ahri",
    riotId: "Me#NA1",
    starter: 1056,
    csPerMin: 7.0,
    build: [3020, 6655, 3089, 3157, 3135, 3102],
  },
  {
    ref: "aB",
    id: 3,
    role: "BOTTOM",
    champion: "Jinx",
    name: "Jinx",
    riotId: "Duo#8841",
    starter: 1055,
    csPerMin: 7.3,
    build: [3006, 3031, 6672, 3094, 3036, 3072],
  },
  {
    ref: "aS",
    id: 5,
    role: "UTILITY",
    champion: "Lulu",
    name: "Lulu",
    riotId: "Sup#0007",
    starter: 3865,
    csPerMin: 1.1,
    build: [3158, 2065, 3504, 3107, 3222, 3190],
  },
  {
    ref: "eT",
    id: 6,
    role: "TOP",
    champion: "MonkeyKing",
    name: "Wukong",
    riotId: "Someone#NA1",
    starter: 1054,
    csPerMin: 6.1,
    build: [3111, 3078, 6333, 3053, 3156, 3742],
  },
  {
    ref: "eJ",
    id: 7,
    role: "JUNGLE",
    champion: "LeeSin",
    name: "Lee Sin",
    riotId: "Hexgate#4431",
    starter: 1101,
    csPerMin: 4.9,
    build: [3047, 6693, 3142, 3814, 3071, 3026],
  },
  {
    ref: "eM",
    id: 8,
    role: "MIDDLE",
    champion: "Zed",
    name: "Zed",
    riotId: "ZedMain#EUW",
    starter: 1055,
    csPerMin: 6.6,
    build: [3158, 3142, 6693, 3814, 3036, 6694],
  },
  {
    ref: "eB",
    id: 9,
    role: "BOTTOM",
    champion: "Kaisa",
    name: "Kai'Sa",
    riotId: "nocturne#9",
    starter: 1055,
    csPerMin: 6.9,
    build: [3158, 3115, 6655, 3089, 3157, 3135],
  },
  {
    ref: "eS",
    id: 10,
    role: "UTILITY",
    champion: "Nautilus",
    name: "Nautilus",
    riotId: "TankMain#2210",
    starter: 3865,
    csPerMin: 1.0,
    build: [3047, 3109, 3190, 3050, 3075, 3107],
  },
];

const BY_REF = new Map(ROSTER.map((r) => [r.ref, r]));
const sideOf = (ref: Ref): Side => (ref.startsWith("a") ? "ally" : "enemy");
const ME: Ref = "aM";

type Pt = [number, number];
const mirror = ([x, y]: Pt): Pt => [14870 - x, 14870 - y];

type BuildingDef = { key: string; kind: Building["kind"]; xy: Pt };
const ALLY_BUILDINGS: BuildingDef[] = [
  { key: "top_outer", kind: "tower", xy: [981, 10441] },
  { key: "top_inner", kind: "tower", xy: [1512, 6699] },
  { key: "top_base", kind: "tower", xy: [1169, 4287] },
  { key: "top_inhibitor", kind: "inhibitor", xy: [1171, 3571] },
  { key: "mid_outer", kind: "tower", xy: [5846, 6396] },
  { key: "mid_inner", kind: "tower", xy: [5048, 4812] },
  { key: "mid_base", kind: "tower", xy: [3651, 3696] },
  { key: "mid_inhibitor", kind: "inhibitor", xy: [3203, 3208] },
  { key: "bot_outer", kind: "tower", xy: [10504, 1029] },
  { key: "bot_inner", kind: "tower", xy: [6919, 1483] },
  { key: "bot_base", kind: "tower", xy: [4281, 1253] },
  { key: "bot_inhibitor", kind: "inhibitor", xy: [3452, 1236] },
  { key: "nexus_tower_1", kind: "tower", xy: [1748, 2270] },
  { key: "nexus_tower_2", kind: "tower", xy: [2177, 1807] },
  { key: "nexus", kind: "nexus", xy: [1551, 1695] },
];

const BUILDINGS: Building[] = (["ally", "enemy"] as const).flatMap((team) =>
  ALLY_BUILDINGS.map((b) => {
    const [x, y] = team === "ally" ? b.xy : mirror(b.xy);
    return { id: `${team}_${b.key}`, team, kind: b.kind, x, y };
  }),
);
const BUILDING = new Map(BUILDINGS.map((b) => [b.id, b]));

const DRAGON_PIT: Pt = [9866, 4414];
const BARON_PIT: Pt = [5007, 10471];

type EvSpec = {
  dt?: number;
  kind: GameEvent["kind"];
  team: Side;
  killer?: Ref;
  victim?: Ref;
  assists?: Ref[];
  detail?: string;
  building?: string;
};
type Spec = {
  at: number;
  zone: string;
  xy: Pt;
  z: number;
  me?: boolean;
  events: EvSpec[];
};

const kill = (dt: number, killer: Ref, victim: Ref, assists: Ref[] = []): EvSpec => ({
  dt,
  kind: "kill",
  team: sideOf(killer),
  killer,
  victim,
  assists,
});
const tower = (team: Side, building: string, detail: string, dt = 0): EvSpec => ({
  dt,
  kind: "tower",
  team,
  building,
  detail,
});
const inhib = (team: Side, building: string, detail: string, dt = 0): EvSpec => ({
  dt,
  kind: "inhibitor",
  team,
  building,
  detail,
});
const objective = (kind: EvSpec["kind"], team: Side, detail?: string, dt = 0): EvSpec => ({
  dt,
  kind,
  team,
  detail,
});

// z is the move in your team's win chance (logit units) once the moment has played out.
const SPECS: Spec[] = [
  { at: 192, zone: "mid lane", xy: [5400, 5600], z: -0.3, events: [kill(0, "eM", "aM", ["eJ"])] },
  {
    at: 304,
    zone: "dragon pit",
    xy: DRAGON_PIT,
    z: 0.16,
    me: true,
    events: [objective("dragon", "ally", "Ocean")],
  },
  { at: 390, zone: "bot lane", xy: [9000, 1700], z: 0.12, events: [kill(0, "aB", "eS", ["aS"])] },
  { at: 440, zone: "top lane", xy: [1800, 8200], z: 0.03, events: [kill(0, "aT", "eT", ["aJ"])] },
  {
    at: 520,
    zone: "bot lane",
    xy: [10200, 1500],
    z: 0.3,
    events: [kill(0, "aB", "eB", ["aS", "aJ"]), kill(6, "aS", "eS", ["aB"])],
  },
  { at: 625, zone: "top river", xy: BARON_PIT, z: -0.2, events: [objective("herald", "enemy")] },
  { at: 705, zone: "mid lane", xy: [7400, 7400], z: 0.2, events: [kill(0, "aM", "eM")] },
  {
    at: 745,
    zone: "mid lane",
    xy: [9300, 9300],
    z: 0.07,
    me: true,
    events: [tower("ally", "enemy_mid_outer", "mid outer")],
  },
  {
    at: 790,
    zone: "bot lane",
    xy: [10504, 1029],
    z: -0.16,
    events: [tower("enemy", "ally_bot_outer", "bot outer")],
  },
  { at: 872, zone: "top lane", xy: [2400, 8600], z: -0.08, events: [kill(0, "eT", "aT", ["eJ"])] },
  {
    at: 960,
    zone: "dragon pit",
    xy: DRAGON_PIT,
    z: -0.12,
    events: [objective("dragon", "enemy", "Infernal")],
  },
  {
    at: 1060,
    zone: "top lane",
    xy: [4400, 13800],
    z: 0.06,
    events: [tower("ally", "enemy_top_outer", "top outer")],
  },
  {
    at: 1100,
    zone: "top lane",
    xy: [4400, 13800],
    z: 0.02,
    events: [{ kind: "plate", team: "ally", detail: "top outer" }],
  },
  {
    at: 1190,
    zone: "dragon pit",
    xy: DRAGON_PIT,
    z: 0.5,
    me: true,
    events: [
      kill(0, "aJ", "eJ", ["aM"]),
      kill(4, "aB", "eB", ["aM", "aS"]),
      kill(9, "aM", "eM"),
      objective("dragon", "ally", "Mountain", 20),
    ],
  },
  { at: 1230, zone: "mid lane", xy: [6800, 6800], z: -0.3, events: [kill(0, "eJ", "aM", ["eB"])] },
  {
    at: 1290,
    zone: "top lane",
    xy: [1300, 9000],
    z: -0.1,
    events: [tower("enemy", "ally_top_outer", "top outer")],
  },
  {
    at: 1330,
    zone: "mid lane",
    xy: [7600, 7200],
    z: 0.78,
    me: true,
    events: [
      kill(0, "aM", "eM", ["aJ"]),
      kill(3, "aM", "eB", ["aS"]),
      kill(6, "aB", "eS"),
      kill(9, "aJ", "eJ", ["aM"]),
      kill(12, "eT", "aS"),
    ],
  },
  {
    at: 1405,
    zone: "baron pit",
    xy: BARON_PIT,
    z: 0.4,
    me: true,
    events: [objective("baron", "ally")],
  },
  {
    at: 1480,
    zone: "mid lane",
    xy: [11300, 11300],
    z: 0.14,
    events: [tower("ally", "enemy_mid_inner", "mid inner")],
  },
  {
    at: 1540,
    zone: "mid lane",
    xy: [11300, 11300],
    z: 0.1,
    me: true,
    events: [tower("ally", "enemy_mid_base", "mid base")],
  },
  {
    at: 1575,
    zone: "enemy base",
    xy: [11660, 11660],
    z: 0.1,
    events: [inhib("ally", "enemy_mid_inhibitor", "mid")],
  },
  {
    at: 1600,
    zone: "baron pit",
    xy: BARON_PIT,
    z: -0.75,
    events: [
      kill(0, "eB", "aB", ["eS"]),
      kill(4, "eT", "aT", ["eJ"]),
      kill(7, "aJ", "eJ"),
      kill(10, "eM", "aJ", ["eB"]),
    ],
  },
  {
    at: 1660,
    zone: "dragon pit",
    xy: DRAGON_PIT,
    z: -0.2,
    events: [objective("dragon", "enemy", "Cloud")],
  },
  {
    at: 1720,
    zone: "bot lane",
    xy: [10800, 1800],
    z: 0.3,
    events: [kill(0, "aM", "eB", ["aB"]), kill(5, "aB", "eS", ["aS"]), kill(11, "eM", "aS")],
  },
  {
    at: 1760,
    zone: "bot lane",
    xy: [13400, 2200],
    z: 0.1,
    events: [tower("ally", "enemy_bot_outer", "bot outer")],
  },
  {
    at: 1800,
    zone: "enemy base",
    xy: [12200, 12400],
    z: 0.55,
    me: true,
    events: [kill(0, "aM", "eM", ["aJ"]), kill(3, "aB", "eT"), kill(7, "aT", "eJ", ["aM"])],
  },
  {
    at: 1850,
    zone: "enemy base",
    xy: [12700, 12600],
    z: 0.3,
    events: [
      tower("ally", "enemy_nexus_tower_1", "nexus", 0),
      tower("ally", "enemy_nexus_tower_2", "nexus", 6),
    ],
  },
];

const Z_SCALE = 1.5;
const sigmoid = (z: number) => 1 / (1 + Math.exp(-z));
const smooth = (x: number) => x * x * (3 - 2 * x);

function toGrade(delta: number): Grade | null {
  if (delta >= 0.1) return "!!";
  if (delta >= 0.05) return "!";
  if (delta <= -0.1) return "??";
  if (delta <= -0.05) return "?";
  return null;
}

function titleFor(events: GameEvent[]): string {
  const kills = events.filter((e) => e.kind === "kill");
  const parts: string[] = [];
  if (kills.length === 1) {
    const e = kills[0];
    const killer = ROSTER.find((r) => r.id === e.killer)!;
    const victim = ROSTER.find((r) => r.id === e.victim)!;
    if (victim.ref === ME) {
      const helpers = [e.killer, ...(e.assists ?? [])].map(
        (id) => ROSTER.find((r) => r.id === id)!.name,
      );
      parts.push(`Died to ${helpers.join(" + ")}`);
    } else if (killer.ref === ME) parts.push(`Killed ${victim.name}`);
    else parts.push(`${killer.name} killed ${victim.name}`);
  } else if (kills.length > 1) {
    const a = kills.filter((e) => e.team === "ally").length;
    const e = kills.length - a;
    parts.push(`${a > e ? "Won" : a < e ? "Lost" : "Traded in"} fight ${a} for ${e}`);
  }
  for (const ev of events) {
    const mine = ev.team === "ally";
    if (ev.kind === "dragon") parts.push(`${mine ? "Took" : "Enemy took"} ${ev.detail} Dragon`);
    else if (ev.kind === "herald") parts.push(`${mine ? "Took" : "Enemy took"} Rift Herald`);
    else if (ev.kind === "baron") parts.push(`${mine ? "Took" : "Enemy took"} Baron`);
    else if (ev.kind === "tower") {
      parts.push(`${mine ? "Took" : "Lost"} ${ev.detail} tower`);
    } else if (ev.kind === "inhibitor")
      parts.push(`${mine ? "Took" : "Lost"} ${ev.detail} inhibitor`);
    else if (ev.kind === "plate") parts.push(`Took ${ev.detail} plate`);
  }
  const unique = [...new Set(parts)];
  if (unique.length === 2 && kills.length > 1) {
    return `${unique[0]}, ${unique[1][0].toLowerCase()}${unique[1].slice(1)}`;
  }
  return unique.join(", ");
}

const level = (t: number, seed: number) =>
  Math.max(
    1,
    Math.min(18, Math.round(1 + 17.2 * (1 - Math.exp(-t / 760)) + ((seed % 3) - 1) * 0.4)),
  );

type Poly = Pt[];
const LANES: Record<"TOP" | "MIDDLE" | "BOTTOM", Poly> = {
  TOP: [
    [800, 2200],
    [700, 6500],
    [1000, 10500],
    [2000, 13200],
    [5500, 14100],
    [9500, 14100],
    [12500, 14100],
  ],
  MIDDLE: [
    [2600, 2600],
    [4800, 4800],
    [7435, 7435],
    [10000, 10000],
    [12300, 12300],
  ],
  BOTTOM: [
    [2200, 800],
    [6500, 700],
    [10500, 800],
    [13300, 2000],
    [14100, 5500],
    [14100, 9500],
    [14100, 12500],
  ],
};
const JUNGLE_A: Pt[] = [
  [3800, 7800],
  [7000, 3500],
  [2600, 6200],
  [5200, 2900],
  [4500, 8800],
  [8200, 4200],
];

function along(poly: Poly, s: number): Pt {
  const lens = poly.slice(1).map((p, i) => Math.hypot(p[0] - poly[i][0], p[1] - poly[i][1]));
  const total = lens.reduce((a, b) => a + b, 0);
  let d = Math.max(0, Math.min(1, s)) * total;
  for (let i = 0; i < lens.length; i++) {
    if (d <= lens[i] || i === lens.length - 1) {
      const f = lens[i] === 0 ? 0 : Math.min(1, d / lens[i]);
      return [
        poly[i][0] + (poly[i + 1][0] - poly[i][0]) * f,
        poly[i][1] + (poly[i + 1][1] - poly[i][1]) * f,
      ];
    }
    d -= lens[i];
  }
  return poly[poly.length - 1];
}

export function makeReview(matchId = "NA1_5300000001", participantId = 4): Review {
  const me = ROSTER.find((r) => r.id === participantId) ?? BY_REF.get(ME)!;

  // Events, in order, with coordinates.
  const events: GameEvent[] = [];
  const buildingOf = new Map<GameEvent, string>();
  const specEvents: GameEvent[][] = SPECS.map((spec, si) => {
    const jitter = rng(si + 11);
    return spec.events.map((e) => {
      const base: Pt = e.building
        ? [BUILDING.get(e.building)!.x, BUILDING.get(e.building)!.y]
        : spec.xy;
      const ev: GameEvent = {
        t: spec.at + (e.dt ?? 0),
        team: e.team,
        kind: e.kind,
        x: Math.round(base[0] + (e.kind === "kill" ? (jitter() - 0.5) * 500 : 0)),
        y: Math.round(base[1] + (e.kind === "kill" ? (jitter() - 0.5) * 500 : 0)),
      };
      if (e.killer) ev.killer = BY_REF.get(e.killer)!.id;
      if (e.victim) ev.victim = BY_REF.get(e.victim)!.id;
      if (e.assists && e.kind === "kill") ev.assists = e.assists.map((a) => BY_REF.get(a)!.id);
      if (e.detail) ev.detail = e.detail;
      if (e.building) buildingOf.set(ev, e.building);
      events.push(ev);
      return ev;
    });
  });
  events.sort((a, b) => a.t - b.t);

  // Win chance: logit moves with each moment, plus a slow drift so the line isn't stepwise.
  const spans = SPECS.map((spec, i) => {
    const ts = specEvents[i].map((e) => e.t);
    return { start: Math.min(...ts) - 8, end: Math.max(...ts) + 4, z: spec.z };
  });
  const zAt = (t: number) => {
    let z = 0.04 * Math.sin(t / 140) + 0.03 * Math.sin(t / 53 + 1);
    for (const s of spans) {
      const f = smooth(Math.max(0, Math.min(1, (t - s.start) / (s.end - s.start))));
      z += s.z * Z_SCALE * f;
    }
    return z;
  };
  const pAt = (t: number) => Math.max(0.02, Math.min(0.98, sigmoid(zAt(t))));

  const curve: CurvePoint[] = [];
  for (let t = 0; t < DURATION; t += STEP) curve.push({ t, p: round4(pAt(t)) });
  curve.push({ t: DURATION, p: 1 });

  const involvesMe = (evs: GameEvent[], spec: Spec) =>
    !!spec.me || evs.some((e) => [e.killer, e.victim, ...(e.assists ?? [])].includes(me.id));

  // Made-up fight damage: each kill's killer and assists hit the victim, victims hit back a little.
  const fightOf = (evs: GameEvent[]): { damage: FightDamage[]; gold: number } => {
    const tally = new Map<number, FightDamage>();
    const add = (id: number, dealt: number, taken: number) => {
      const d = tally.get(id) ?? { participant_id: id, dealt: 0, taken: 0 };
      d.dealt += dealt;
      d.taken += taken;
      tally.set(id, d);
    };
    let gold = 0;
    for (const e of evs.filter((x) => x.kind === "kill")) {
      const helpers = [e.killer!, ...(e.assists ?? [])];
      helpers.forEach((id, j) => {
        const amount = 900 + ((id * 137 + j * 311) % 700);
        add(id, amount, 0);
        add(e.victim!, 0, amount);
      });
      add(e.victim!, 250 + ((e.victim! * 97) % 300), 0);
      add(e.killer!, 0, 250 + ((e.victim! * 97) % 300));
      gold += e.team === "ally" ? 300 : -300;
    }
    return { damage: [...tally.values()].sort((a, b) => b.dealt - a.dealt), gold };
  };

  const moments: Moment[] = SPECS.map((spec, i) => {
    const s = spans[i];
    const fight = fightOf(specEvents[i]);
    const before = pAt(s.start);
    const after = pAt(s.end);
    const delta = after - before;
    return {
      id: `m${String(i + 1).padStart(2, "0")}`,
      t_start: s.start,
      t_end: s.end,
      p_before: round4(before),
      p_after: round4(after),
      delta: round4(delta),
      grade: toGrade(delta),
      title: titleFor(specEvents[i]),
      zone: spec.zone,
      involves_me: involvesMe(specEvents[i], spec),
      events: specEvents[i],
      damage: fight.damage,
      kill_gold: fight.gold,
    };
  });

  // Per-player history derived from the events.
  const deaths = events
    .filter((e) => e.kind === "kill")
    .map((e) => {
      const victim = ROSTER.find((r) => r.id === e.victim)!;
      const lvl = level(e.t, victim.id);
      const base =
        BASE_RESPAWN[lvl - 1] * (1 + Math.min(0.5, Math.max(0, (e.t / 60 - 15) * 0.0085)));
      return { ev: e, victim: e.victim!, from: e.t, until: e.t + Math.round(base) };
    });

  const stateOf = (r: RosterEntry, t: number): PlayerState => {
    const rand = rng(r.id * 100003 + Math.floor(t / 60));
    const lvl = level(t, r.id);
    let k = 0;
    let d = 0;
    let a = 0;
    let kills = 0;
    for (const e of events) {
      if (e.t > t || e.kind !== "kill") continue;
      if (e.killer === r.id) {
        k++;
        kills++;
      }
      if (e.victim === r.id) d++;
      if (e.assists?.includes(r.id)) a++;
    }
    const cs = t < 90 ? 0 : Math.floor(((r.csPerMin * (t - 90)) / 60) * (0.96 + (r.id % 4) * 0.02));
    const passive = t < 110 ? 0 : ((t - 110) / 10) * 20.4;
    const gold = Math.round(500 + passive + cs * 21 + kills * 300 + a * 150);
    const items = r.build.filter((_, idx) => t >= 330 + idx * 300 + (r.id % 3) * 20);
    const slots: (number | null)[] = Array.from({ length: 6 }, (_, idx) => items[idx] ?? null);
    if (items.length === 0) slots[0] = r.starter;
    const trinket = t < 540 ? 3340 : r.role === "UTILITY" ? 3364 : 3363;

    // Position is sampled once a minute, like the timeline.
    const tp = Math.floor(t / 60) * 60;
    const dead = deaths.find((x) => x.victim === r.id && t >= x.from && t < x.until);
    const side = sideOf(r.ref);
    let pos: Pt;
    if (dead) {
      pos = [dead.ev.x!, dead.ev.y!];
    } else {
      pos = positionAt(r, tp, side, rand);
    }
    return {
      participant_id: r.id,
      x: Math.round(pos[0]),
      y: Math.round(pos[1]),
      pos_age_s: dead ? 0 : t - tp,
      level: lvl,
      k,
      d,
      a,
      cs,
      gold,
      items: slots,
      trinket,
      respawn_in_s: dead ? dead.until - t : 0,
    };
  };

  const positionAt = (r: RosterEntry, tp: number, side: Side, rand: () => number): Pt => {
    const j = (n: number): Pt => [(rand() - 0.5) * n, (rand() - 0.5) * n];
    // Fighting: near the kill.
    const fight = events.find(
      (e) =>
        e.kind === "kill" &&
        e.t >= tp - 10 &&
        e.t <= tp + 50 &&
        [e.killer, e.victim, ...(e.assists ?? [])].includes(r.id),
    );
    if (fight) {
      const [dx, dy] = j(700);
      return [fight.x! + dx, fight.y! + dy];
    }
    // Grouping for the next play after 14 minutes.
    const spec = SPECS.find((s) => Math.abs(tp - s.at) <= 45);
    if (spec && tp > 840) {
      const [dx, dy] = j(1100);
      const off = side === "ally" ? -450 : 450;
      return [spec.xy[0] + off + dx, spec.xy[1] + off + dy];
    }
    const phase = r.id * 1.7;
    const wiggle = 0.05 * Math.sin(tp / 70 + phase);
    let base: Pt;
    if (r.role === "JUNGLE") {
      const camp = JUNGLE_A[(Math.floor(tp / 75) + r.id) % JUNGLE_A.length];
      base = side === "ally" ? camp : mirror(camp);
    } else {
      const lane = r.role === "UTILITY" ? "BOTTOM" : r.role;
      const w = Math.max(0, Math.min(1, (tp - 840) / 600));
      const home = side === "ally" ? 0.28 : 0.72;
      const mid = side === "ally" ? 0.42 : 0.62;
      const s = home + wiggle + (mid - home) * w;
      base = along(LANES[lane], s);
      if (w > 0.5 && lane !== "MIDDLE") {
        const m = along(LANES.MIDDLE, s);
        base = [(base[0] + m[0]) / 2, (base[1] + m[1]) / 2];
      }
      if (r.role === "UTILITY") base = [base[0] + 250, base[1] + 150];
    }
    const [dx, dy] = j(300);
    return [base[0] + dx, base[1] + dy];
  };

  const teamState = (team: Side, t: number): TeamState => {
    const mine = events.filter((e) => e.t <= t && e.team === team);
    const ids = ROSTER.filter((r) => sideOf(r.ref) === team).map((r) => r.id);
    const players = ROSTER.filter((r) => ids.includes(r.id)).map((r) => stateOf(r, t));
    const baron = mine.filter((e) => e.kind === "baron").at(-1);
    return {
      kills: mine.filter((e) => e.kind === "kill").length,
      gold: players.reduce((sum, p) => sum + p.gold, 0),
      towers: mine.filter((e) => e.kind === "tower").length,
      dragons: mine.filter((e) => e.kind === "dragon").map((e) => e.detail ?? ""),
      soul: null,
      grubs: mine.filter((e) => e.kind === "grubs").length,
      heralds: mine.filter((e) => e.kind === "herald").length,
      barons: mine.filter((e) => e.kind === "baron").length,
      buff: baron && baron.t + 180 > t ? { kind: "baron", ends_in_s: baron.t + 180 - t } : null,
    };
  };

  const snapshots: Snapshot[] = [];
  for (let t = 0; t <= DURATION; t += STEP) {
    snapshots.push({
      t,
      players: ROSTER.map((r) => stateOf(r, t)),
      teams: { ally: teamState("ally", t), enemy: teamState("enemy", t) },
      buildings_down: events
        .filter((e) => e.t <= t && buildingOf.has(e))
        .map((e) => buildingOf.get(e)!),
      recent_kills: events
        .filter((e) => e.kind === "kill" && e.t <= t && t - e.t < 10)
        .map((e) => ({ x: e.x!, y: e.y!, team: e.team, age_s: t - e.t })),
    });
  }

  const players: Player[] = ROSTER.map((r) => ({
    participant_id: r.id,
    riot_id: r.riotId,
    champion: r.champion,
    champion_name: r.name,
    role: r.role,
    team: sideOf(r.ref),
    is_me: r.id === me.id,
  }));

  const count = (list: Moment[]): GradeCounts => {
    const c: GradeCounts = { "!!": 0, "!": 0, "?": 0, "??": 0 };
    for (const m of list) if (m.grade) c[m.grade]++;
    return c;
  };
  const biggest = moments.reduce((best, m) =>
    Math.abs(m.delta) > Math.abs(best.delta) ? m : best,
  );

  return {
    match: {
      match_id: matchId,
      platform: "NA",
      patch: "26.19",
      ddragon_version: "26.19.1",
      started_at: "2026-09-30T18:20:00Z",
      duration_s: DURATION,
      result: "win",
      surrender: false,
      my_side: "blue",
      tier_used: "GOLD",
      tier_note: null,
      model: { kind: "stub", version: "stub-1" },
      patch_in_training: true,
    },
    players,
    buildings: BUILDINGS,
    curve,
    moments,
    snapshots,
    summary: {
      me: count(moments.filter((m) => m.involves_me)),
      team: count(moments),
      biggest_id: biggest.id,
    },
  };
}

function round4(n: number) {
  return Math.round(n * 10000) / 10000;
}
