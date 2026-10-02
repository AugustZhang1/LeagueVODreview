import { describe, expect, it } from "vitest";
import {
  formatDelta,
  formatFullDate,
  formatGold,
  formatGoldDelta,
  formatKda,
  formatMonthDay,
  formatRelative,
  formatTime,
  formatWinChance,
  winPercent,
} from "./format";

describe("formatTime", () => {
  it("is mm:ss under an hour", () => {
    expect(formatTime(0)).toBe("00:00");
    expect(formatTime(59.9)).toBe("00:59");
    expect(formatTime(1902)).toBe("31:42");
  });
  it("is h:mm:ss past an hour", () => {
    expect(formatTime(3600)).toBe("1:00:00");
    expect(formatTime(3725)).toBe("1:02:05");
  });
  it("never goes negative", () => {
    expect(formatTime(-5)).toBe("00:00");
  });
});

describe("win chance", () => {
  it("rounds to a whole percent", () => {
    expect(winPercent(0.634)).toBe(63);
    expect(winPercent(0.635)).toBe(64);
  });
  it("stays within 1-99% until the game ends", () => {
    expect(winPercent(0)).toBe(1);
    expect(winPercent(0.002)).toBe(1);
    expect(winPercent(1)).toBe(99);
    expect(winPercent(0.999)).toBe(99);
    expect(formatWinChance(0.5)).toBe("50%");
  });
  it("allows 0% and 100% at GAME_END", () => {
    expect(formatWinChance(1, true)).toBe("100%");
    expect(formatWinChance(0, true)).toBe("0%");
  });
});

describe("formatDelta", () => {
  it("signs positives with + and negatives with U+2212", () => {
    expect(formatDelta(0.18)).toBe("+18%");
    expect(formatDelta(-0.11)).toBe("−11%");
    expect(formatDelta(-0.11)).not.toContain("-");
  });
  it("shows zero without a sign, including values that round to zero", () => {
    expect(formatDelta(0)).toBe("0%");
    expect(formatDelta(0.004)).toBe("0%");
    expect(formatDelta(-0.004)).toBe("0%");
  });
});

describe("gold", () => {
  it("uses k from a thousand", () => {
    expect(formatGold(9120)).toBe("9.1k");
    expect(formatGold(48200)).toBe("48.2k");
    expect(formatGold(1000)).toBe("1.0k");
  });
  it("keeps small amounts whole", () => {
    expect(formatGold(950)).toBe("950");
    expect(formatGold(0)).toBe("0");
  });
  it("signs a lead", () => {
    expect(formatGoldDelta(4100)).toBe("+4.1k");
    expect(formatGoldDelta(-4100)).toBe("−4.1k");
    expect(formatGoldDelta(-800)).toBe("−800");
    expect(formatGoldDelta(0)).toBe("0");
  });
});

describe("formatKda", () => {
  it("spaces the slashes", () => {
    expect(formatKda(8, 2, 11)).toBe("8 / 2 / 11");
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-10-02T12:00:00Z");
  const ago = (s: number) => new Date(now.getTime() - s * 1000).toISOString();
  it("picks the largest unit and pluralises", () => {
    expect(formatRelative(ago(20), now)).toBe("just now");
    expect(formatRelative(ago(60), now)).toBe("1 minute ago");
    expect(formatRelative(ago(5 * 60), now)).toBe("5 minutes ago");
    expect(formatRelative(ago(3600), now)).toBe("1 hour ago");
    expect(formatRelative(ago(2 * 86400), now)).toBe("2 days ago");
    expect(formatRelative(ago(3 * 7 * 86400), now)).toBe("3 weeks ago");
    expect(formatRelative(ago(60 * 86400), now)).toBe("2 months ago");
    expect(formatRelative(ago(400 * 86400), now)).toBe("1 year ago");
  });
  it("treats future dates as just now and bad input as empty", () => {
    expect(formatRelative(ago(-500), now)).toBe("just now");
    expect(formatRelative("nope", now)).toBe("");
  });
});

describe("dates", () => {
  it("formats the full date and the short month-day in UTC", () => {
    expect(formatFullDate("2026-10-01T23:30:00Z")).toBe("Oct 1, 2026");
    expect(formatMonthDay("2026-10-01T09:30:00Z")).toBe("Oct 1");
    expect(formatFullDate("nope")).toBe("");
  });
});
