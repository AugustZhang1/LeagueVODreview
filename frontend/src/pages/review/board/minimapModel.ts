import type { Building, Player, PlayerState, Review, Side, Snapshot } from "../../../api/models";
import { toCanvas } from "../../../lib/map";

/** Icon diameter and ring widths in CSS pixels. */
export const ICON_SIZE = 26;
export const RING = 2;
export const BUILDING_SIZE = 6;
export const HIT_RADIUS = ICON_SIZE / 2 + RING;
const KILL_MARK_SECONDS = 10;
const STALE_SECONDS = 60;

export type BuildingMark = { id: string; team: Side; cx: number; cy: number; down: boolean };

export type ChampionMark = {
  player: Player;
  state: PlayerState;
  cx: number;
  cy: number;
  team: Side;
  isYou: boolean;
  dead: boolean;
  /** Whole seconds until respawn, shown under a dead icon. */
  respawn: number;
  opacity: number;
};

export type KillMark = { cx: number; cy: number; team: Side };

/** 100% for a fresh position, falling linearly to 50% at 60 s old. */
export function positionOpacity(ageSeconds: number): number {
  const age = Math.min(STALE_SECONDS, Math.max(0, ageSeconds));
  return 1 - 0.5 * (age / STALE_SECONDS);
}

export const DEAD_OPACITY = 0.4;

/** Seconds the scrubber is past the snapshot it is showing (0 when the two agree). */
export function secondsPastSnapshot(t: number, snapshot: Snapshot): number {
  return Math.max(0, t - snapshot.t);
}

/** Respawn seconds still to go at time `t`, counting down from the snapshot's value. */
export function respawnAt(state: PlayerState, t: number, snapshot: Snapshot): number {
  return Math.max(0, state.respawn_in_s - secondsPastSnapshot(t, snapshot));
}

export function buildingMarks(
  buildings: Building[],
  buildingsDown: string[],
  size: number,
): BuildingMark[] {
  const down = new Set(buildingsDown);
  return buildings.map((b) => ({
    id: b.id,
    team: b.team,
    ...toCanvas(b.x, b.y, size),
    down: down.has(b.id),
  }));
}

/** Kills in the last 10 s, as of time `t`, at the kill spot. */
export function killMarks(snapshot: Snapshot, t: number, size: number): KillMark[] {
  const extra = secondsPastSnapshot(t, snapshot);
  return snapshot.recent_kills
    .filter((k) => k.age_s + extra <= KILL_MARK_SECONDS)
    .map((k) => ({ team: k.team, ...toCanvas(k.x, k.y, size) }));
}

/**
 * One mark per player in draw order: enemies, then allies, then you last so
 * your icon sits on top.
 */
export function championMarks(
  players: Player[],
  snapshot: Snapshot,
  t: number,
  size: number,
): ChampionMark[] {
  const states = new Map(snapshot.players.map((s) => [s.participant_id, s]));
  const extra = secondsPastSnapshot(t, snapshot);
  const marks: ChampionMark[] = [];
  for (const player of players) {
    const state = states.get(player.participant_id);
    if (!state) continue;
    const left = respawnAt(state, t, snapshot);
    const dead = left > 0;
    marks.push({
      player,
      state,
      ...toCanvas(state.x, state.y, size),
      team: player.team,
      isYou: player.is_me,
      dead,
      respawn: dead ? Math.ceil(left) : 0,
      opacity: dead ? DEAD_OPACITY : positionOpacity(state.pos_age_s + extra),
    });
  }
  const rank = (m: ChampionMark) => (m.isYou ? 2 : m.team === "ally" ? 1 : 0);
  return marks.sort((a, b) => rank(a) - rank(b));
}

/** The topmost icon under a pointer position, or null. */
export function hitTest(marks: ChampionMark[], px: number, py: number): ChampionMark | null {
  for (let i = marks.length - 1; i >= 0; i--) {
    const m = marks[i];
    if (Math.hypot(m.cx - px, m.cy - py) <= HIT_RADIUS) return m;
  }
  return null;
}

/** Seconds of position age as the tooltip words it: "position 0:42 old". */
export function positionAge(mark: ChampionMark, t: number, snapshot: Snapshot): number {
  return mark.state.pos_age_s + secondsPastSnapshot(t, snapshot);
}

/** Lane lines for the offline background: three lanes as polylines in canvas fractions. */
export const LANE_LINES: [number, number][][] = [
  [
    [0.07, 0.93],
    [0.07, 0.07],
    [0.93, 0.07],
  ],
  [
    [0.07, 0.93],
    [0.93, 0.07],
  ],
  [
    [0.07, 0.93],
    [0.93, 0.93],
    [0.93, 0.07],
  ],
];

/** The debug overlay: a quadrant grid, since reviews carry no zone data. */
export function debugGrid(size: number): { x1: number; y1: number; x2: number; y2: number }[] {
  const mid = size / 2;
  return [
    { x1: mid, y1: 0, x2: mid, y2: size },
    { x1: 0, y1: mid, x2: size, y2: mid },
  ];
}

export function reviewMarks(review: Review, snapshot: Snapshot, t: number, size: number) {
  return {
    buildings: buildingMarks(review.buildings, snapshot.buildings_down, size),
    kills: killMarks(snapshot, t, size),
    champions: championMarks(review.players, snapshot, t, size),
  };
}
