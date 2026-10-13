import type { Moment, Player, Review } from "../../api/models";
import { winAt } from "./curve";

export type ImpactPoint = {
  t: number;
  team: number;
  teamP: number;
  me: number;
  opponent: number | null;
  moment: Moment | null;
  myShare: number | null;
  hasMyDot: boolean;
};

export type ImpactCurve = {
  me: Player;
  opponent: Player | null;
  points: ImpactPoint[];
};

/** Finds the enemy player in the same role as `me`, or null. */
export function findLaneOpponent(review: Review, me: Player): Player | null {
  return review.players.find((p) => p.role === me.role && p.team !== me.team) ?? null;
}

/** Formats points of win chance with a sign, e.g. "+9.2%", "−3.1%", "0.0%". */
export function formatImpactPoints(val: number): string {
  const rounded = Math.round(val * 10) / 10;
  const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : "";
  return `${sign}${Math.abs(rounded).toFixed(1)}%`;
}

/**
 * Builds the time-series data for the Impact chart:
 * - team: (p - p0) * 100 as a faint area (centered on 0)
 * - me: running sum of my Moment.credit share * 100 as a step line
 * - opponent: running sum of enemy same-role Moment.credit share * 100
 */
export function impactCurve(review: Review): ImpactCurve | null {
  const me = review.players.find((p) => p.is_me);
  if (!me) return null;

  const opponent = findLaneOpponent(review, me);
  const duration = review.match.duration_s;
  const p0 = review.curve.length > 0 ? review.curve[0].p : 0.5;

  // Filter moments up to match duration and sort by t_start
  const moments = (review.moments ?? [])
    .filter((m) => m.t_start <= duration)
    .sort((a, b) => a.t_start - b.t_start);

  // Group moments by t_start to handle any simultaneous moments
  const momentsByTime = new Map<number, Moment[]>();
  for (const m of moments) {
    const list = momentsByTime.get(m.t_start) ?? [];
    list.push(m);
    momentsByTime.set(m.t_start, list);
  }

  // Collect all unique timestamps: 0, duration, curve points, and moment start times
  const timeSet = new Set<number>();
  timeSet.add(0);
  timeSet.add(duration);
  for (const pt of review.curve) {
    if (pt.t <= duration) {
      timeSet.add(pt.t);
    }
  }
  for (const m of moments) {
    timeSet.add(m.t_start);
  }

  const times = Array.from(timeSet).sort((a, b) => a - b);

  let currentMe = 0;
  let currentOpp = 0;
  const points: ImpactPoint[] = [];

  for (const t of times) {
    const startingMoments = momentsByTime.get(t);
    let momentForPoint: Moment | null = null;
    let myNetShareForPoint = 0;
    let hadMyCredit = false;

    if (startingMoments && startingMoments.length > 0) {
      for (const m of startingMoments) {
        const credits = m.credit ?? [];
        const myCredit = credits.find((c) => c.participant_id === me.participant_id);
        if (myCredit) {
          hadMyCredit = true;
          myNetShareForPoint += myCredit.share;
          currentMe += myCredit.share * 100;
        }

        if (opponent) {
          const oppCredit = credits.find((c) => c.participant_id === opponent.participant_id);
          if (oppCredit) {
            currentOpp += oppCredit.share * 100;
          }
        }
      }
      // The dot's click selects this moment, so prefer one the reviewed player is in
      momentForPoint =
        startingMoments.find((m) =>
          m.credit?.some((c) => c.participant_id === me.participant_id),
        ) ?? startingMoments[0];
    }

    const p = winAt(review.curve, t);
    const team = Math.round((p - p0) * 10000) / 100;
    const roundedMe = Math.round(currentMe * 10000) / 10000;
    const roundedOpp = opponent != null ? Math.round(currentOpp * 10000) / 10000 : null;

    points.push({
      t,
      team,
      teamP: p,
      me: roundedMe,
      opponent: roundedOpp,
      moment: momentForPoint,
      myShare: hadMyCredit ? Math.round(myNetShareForPoint * 10000) / 10000 : null,
      hasMyDot: hadMyCredit && Math.abs(myNetShareForPoint) > 1e-6,
    });
  }

  return { me, opponent, points };
}
