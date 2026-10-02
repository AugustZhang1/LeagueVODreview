const MINUTE = 60;
const HOUR = 3600;
const DAY = 86400;

const pad = (n: number) => String(n).padStart(2, "0");

/** mm:ss, or h:mm:ss past an hour. */
export function formatTime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / HOUR);
  const m = Math.floor((s % HOUR) / MINUTE);
  const sec = s % MINUTE;
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

/**
 * Win chance (0–1) as a whole percent. Until the game has ended it stays within
 * 1–99% so the graph never claims certainty early.
 */
export function winPercent(p: number, final = false): number {
  const whole = Math.round(p * 100);
  return final ? whole : Math.min(99, Math.max(1, whole));
}

export function formatWinChance(p: number, final = false): string {
  return `${winPercent(p, final)}%`;
}

/** Change in win chance (a fraction) as "+18%" or "−11%" with U+2212; zero is "0%". */
export function formatDelta(delta: number): string {
  const whole = Math.round(delta * 100);
  if (whole === 0) return "0%";
  return `${whole > 0 ? "+" : "−"}${Math.abs(whole)}%`;
}

/** 9100 becomes "9.1k"; under 1000 stays a plain number. */
export function formatGold(gold: number): string {
  const abs = Math.abs(gold);
  if (abs < 1000) return String(Math.round(gold));
  return `${(gold / 1000).toFixed(1)}k`;
}

/** Gold difference with a sign: "+4.1k", "−0.8k". */
export function formatGoldDelta(diff: number): string {
  if (Math.round(diff) === 0) return "0";
  return `${diff > 0 ? "+" : "−"}${formatGold(Math.abs(diff))}`;
}

export function formatKda(k: number, d: number, a: number): string {
  return `${k} / ${d} / ${a}`;
}

const UNITS: [number, string, number][] = [
  [365 * DAY, "year", 365 * DAY],
  [30 * DAY, "month", 30 * DAY],
  [7 * DAY, "week", 7 * DAY],
  [DAY, "day", DAY],
  [HOUR, "hour", HOUR],
  [MINUTE, "minute", MINUTE],
];

/** "2 days ago". `now` is injectable for tests. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Math.max(0, Math.floor((now.getTime() - then) / 1000));
  for (const [threshold, unit, size] of UNITS) {
    if (diff >= threshold) {
      const n = Math.floor(diff / size);
      return `${n} ${unit}${n === 1 ? "" : "s"} ago`;
    }
  }
  return "just now";
}

/** "Oct 1, 2026", shown on hover over a relative date. */
export function formatFullDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "Oct 1", for the footer's model line. */
export function formatMonthDay(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}
