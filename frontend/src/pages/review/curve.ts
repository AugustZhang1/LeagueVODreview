import type { CurvePoint, Moment } from "../../api/models";
import { formatWinChance } from "../../lib/format";

/** Win chance (0–1) at time `t`, by linear interpolation along the curve. */
export function winAt(curve: CurvePoint[], t: number): number {
  if (curve.length === 0) return 0.5;
  if (t <= curve[0].t) return curve[0].p;
  const last = curve[curve.length - 1];
  if (t >= last.t) return last.p;
  let lo = 0;
  let hi = curve.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (curve[mid].t <= t) lo = mid;
    else hi = mid;
  }
  const a = curve[lo];
  const b = curve[hi];
  return a.p + ((b.p - a.p) * (t - a.t)) / (b.t - a.t || 1);
}

/**
 * Win chance (0–1) on the scrubber clock. The final point sits a moment after the
 * whole-second duration, so the end of the scrubber reads the curve's last point.
 */
export function winAtClock(curve: CurvePoint[], t: number, duration: number): number {
  if (curve.length > 0 && t >= duration) return curve[curve.length - 1].p;
  return winAt(curve, t);
}

/** The win chance shown at scrubber time `t`: 100% / 0% once the game is over. */
export function winLabel(curve: CurvePoint[], t: number, duration: number): string {
  return formatWinChance(winAtClock(curve, t, duration), t >= duration);
}

/** Where selecting a moment puts the clock: whole seconds, the state after it. */
export const momentEnd = (m: Moment, duration: number): number =>
  Math.min(duration, Math.round(m.t_end));

export const capitalize = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1) : s);

/** Plain words for a win chance (0-1), so the number isn't read on its own. */
export function winWord(p: number): string {
  if (p >= 0.85) return "Winning";
  if (p >= 0.65) return "Ahead";
  if (p > 0.55) return "Slightly ahead";
  if (p >= 0.45) return "Even";
  if (p > 0.35) return "Slightly behind";
  if (p > 0.15) return "Behind";
  return "Losing";
}
