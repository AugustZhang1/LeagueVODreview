import type {
  Player,
  PlayerState,
  Review,
  Role,
  Side,
  Snapshot,
  TeamState,
} from "../../../api/models";
import { formatGold, formatGoldDelta, formatTime } from "../../../lib/format";

const ROLE_ORDER: Role[] = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];
const roleRank = (r: Role) => ROLE_ORDER.indexOf(r);

export type Row = {
  player: Player;
  state: PlayerState;
  dead: boolean;
  /** "dead 0:12" while dead, otherwise null. */
  deadText: string | null;
  gold: string;
  /** Six item slots then the trinket; null is an empty slot. */
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
};

export type TeamBlock = { header: TeamHeader; rows: Row[] };

/** "0:12": minutes without padding, as the in-game death timer shows it. */
function formatRespawn(seconds: number): string {
  return formatTime(Math.ceil(seconds)).replace(/^0/, "");
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function buildRow(player: Player, state: PlayerState): Row {
  const dead = state.respawn_in_s > 0;
  return {
    player,
    state,
    dead,
    deadText: dead ? `dead ${formatRespawn(state.respawn_in_s)}` : null,
    gold: formatGold(state.gold),
    slots: [...state.items.slice(0, 6), state.trinket],
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
  };
}

/** Ally team first, then enemy, each in role order. */
export function buildScoreboard(review: Review, snapshot: Snapshot): TeamBlock[] {
  const states = new Map(snapshot.players.map((s) => [s.participant_id, s]));
  const { ally, enemy } = snapshot.teams;
  return (["ally", "enemy"] as const).map((team) => {
    const rows = review.players
      .filter((p) => p.team === team && states.has(p.participant_id))
      .sort((a, b) => roleRank(a.role) - roleRank(b.role))
      .map((p) => buildRow(p, states.get(p.participant_id)!));
    return {
      header: buildHeader(team, team === "ally" ? ally : enemy, team === "ally" ? enemy : ally),
      rows,
    };
  });
}
