import type { Player, Review } from "../../api/models";

export type LanePoint = { t: number; gold: number; cs: number };

/** My lane opponent and my gold and CS minus theirs, one point per snapshot. */
export type LaneDiff = { opponent: Player; points: LanePoint[] };

/** Null when there's no me or no enemy with my role. */
export function laneDiff(review: Review): LaneDiff | null {
  const me = review.players.find((p) => p.is_me);
  if (!me) return null;
  const opponent = review.players.find((p) => p.role === me.role && p.team !== me.team);
  if (!opponent) return null;
  const points = review.snapshots.flatMap((sn) => {
    const mine = sn.players.find((p) => p.participant_id === me.participant_id);
    const theirs = sn.players.find((p) => p.participant_id === opponent.participant_id);
    if (!mine || !theirs) return [];
    return [{ t: sn.t, gold: mine.gold - theirs.gold, cs: mine.cs - theirs.cs }];
  });
  return { opponent, points };
}

/** The point at or just before t, or null before the first snapshot. Points are in time order. */
export function diffAt(points: LanePoint[], t: number): LanePoint | null {
  let found: LanePoint | null = null;
  for (const p of points) {
    if (p.t > t) break;
    found = p;
  }
  return found;
}
