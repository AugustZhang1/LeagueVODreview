import type {
  Objectives,
  Player,
  PlayerState,
  Review,
  Role,
  ScoreParts,
  Side,
  Snapshot,
  TeamState,
} from "../../../api/models";
import { formatGold, formatGoldDelta, formatTime } from "../../../lib/format";
import { respawnAt, secondsPastSnapshot } from "./minimapModel";

/** Formats score parts into the tooltip text, e.g. "Gold/min 8.9 · vs lane 8.9 · KP 5.6 · Impact 9.1 · Fights 8.9" */
export function formatScoreParts(parts: ScoreParts | null | undefined): string | null {
  if (!parts) return null;
  return (
    `Gold/min ${parts.gold_min.toFixed(1)} · ` +
    `vs lane ${parts.vs_lane.toFixed(1)} · ` +
    `KP ${parts.kp.toFixed(1)} · ` +
    `Impact ${parts.impact.toFixed(1)} · ` +
    `Fights ${parts.fights.toFixed(1)}`
  );
}

const ROLE_ORDER: Role[] = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];
const roleRank = (r: Role) => ROLE_ORDER.indexOf(r);

export type Row = {
  player: Player;
  state: PlayerState;
  dead: boolean;
  /** "dead 0:12" while dead, otherwise null. */
  deadText: string | null;
  gold: string;
  /** Six item slots, the trinket, then boots in the Bot Lane quest slot if any; null is empty. */
  slots: (number | null)[];
};

export type TeamHeader = {
  team: Side;
  label: string;
  kills: number;
  gold: string;
  towers: number;
  dragonCount: number;
  /** Dragon types in the order taken, for the hover. */
  dragonTypes: string[];
  /** "Ocean soul", or null. */
  soul: string | null;
  /** "Baron 1:12" as a label and a time, or null. */
  buff: { label: string; time: string } | null;
  /** Gold lead such as "+4.1k" on the leading team only. */
  lead: string | null;
  grubs: number;
  heralds: number;
  barons: number;
};

export type TeamBlock = { header: TeamHeader; rows: Row[] };

/** One objective timer: "Dragon" and "1:12", or "up" once it has run out. */
export type ObjectiveTimer = { label: string; time: string };
export type ObjectiveTimers = { dragon: ObjectiveTimer; pit: ObjectiveTimer };

const PIT_LABEL: Record<Objectives["baron_pit_kind"], string> = {
  grubs: "Grubs",
  herald: "Herald",
  baron: "Baron",
};

/** "0:12": minutes without padding, as the in-game death timer shows it. */
function formatRespawn(seconds: number): string {
  return formatTime(Math.ceil(seconds)).replace(/^0/, "");
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function buildRow(player: Player, state: PlayerState, left = state.respawn_in_s): Row {
  const dead = left > 0;
  return {
    player,
    state,
    dead,
    deadText: dead ? `dead ${formatRespawn(left)}` : null,
    gold: formatGold(state.gold),
    slots: [
      ...state.items.slice(0, 6),
      state.trinket,
      ...(state.quest_item ? [state.quest_item] : []),
    ],
  };
}

export function buildHeader(team: Side, ts: TeamState, other: TeamState): TeamHeader {
  const diff = ts.gold - other.gold;
  return {
    team,
    label: team === "ally" ? "Ally" : "Enemy",
    kills: ts.kills,
    gold: formatGold(ts.gold),
    towers: ts.towers,
    dragonCount: ts.dragons.length,
    dragonTypes: ts.dragons,
    soul: ts.soul ? `${ts.soul} soul` : null,
    buff: ts.buff ? { label: cap(ts.buff.kind), time: formatTime(ts.buff.ends_in_s) } : null,
    lead: Math.round(diff) > 0 ? formatGoldDelta(diff) : null,
    grubs: ts.grubs,
    heralds: ts.heralds,
    barons: ts.barons,
  };
}

/** Dragon and pit timers at `t`, counting down from the snapshot; null without objectives. */
export function buildObjectives(snapshot: Snapshot, t = snapshot.t): ObjectiveTimers | null {
  const o = snapshot.objectives;
  if (!o) return null;
  const timer = (label: string, seconds: number): ObjectiveTimer => {
    const left = Math.max(0, seconds - secondsPastSnapshot(t, snapshot));
    return { label, time: left > 0 ? formatRespawn(left) : "up" };
  };
  return {
    dragon: timer(o.dragon_kind === "elder" ? "Elder" : "Dragon", o.dragon_in_s),
    pit: timer(PIT_LABEL[o.baron_pit_kind], o.baron_pit_in_s),
  };
}

/** Ally team first, then enemy, each in role order. Death timers count down with `t`. */
export function buildScoreboard(review: Review, snapshot: Snapshot, t = snapshot.t): TeamBlock[] {
  const states = new Map(snapshot.players.map((s) => [s.participant_id, s]));
  const { ally, enemy } = snapshot.teams;
  return (["ally", "enemy"] as const).map((team) => {
    const rows = review.players
      .filter((p) => p.team === team && states.has(p.participant_id))
      .sort((a, b) => roleRank(a.role) - roleRank(b.role))
      .map((p) => {
        const state = states.get(p.participant_id)!;
        return buildRow(p, state, respawnAt(state, t, snapshot));
      });
    return {
      header: buildHeader(team, team === "ally" ? ally : enemy, team === "ally" ? enemy : ally),
      rows,
    };
  });
}
