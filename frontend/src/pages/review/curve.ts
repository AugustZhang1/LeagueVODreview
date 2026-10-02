import type { CurvePoint, Moment } from "../../api/models";

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

/** Where selecting a moment puts the clock: whole seconds, the state after it. */
export const momentEnd = (m: Moment, duration: number): number =>
  Math.min(duration, Math.round(m.t_end));

export const capitalize = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1) : s);
