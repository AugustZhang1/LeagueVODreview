import { describe, expect, it } from "vitest";
import type { Moment, Review } from "../../api/models";
import reviewFixture from "../../mocks/review.fixture.json";
import { formatImpactPoints, impactCurve, type ImpactPoint } from "./impactCurve";

const baseReview = reviewFixture as unknown as Review;

/** The point at or just before t, or null before the first point. Test-only: reads the curve between points. */
function impactAt(points: ImpactPoint[], t: number): ImpactPoint | null {
  let found: ImpactPoint | null = null;
  for (const p of points) {
    if (p.t > t) break;
    found = p;
  }
  return found;
}

function createTestReview(overrides?: Partial<Review>): Review {
  return {
    ...baseReview,
    match: { ...baseReview.match, duration_s: 1800 },
    curve: [
      { t: 0, p: 0.5 },
      { t: 600, p: 0.55 },
      { t: 1200, p: 0.6 },
      { t: 1800, p: 0.65 },
    ],
    moments: [],
    players: [
      {
        participant_id: 1,
        is_me: true,
        role: "TOP",
        team: "ally",
        champion: "Aatrox",
        champion_name: "Aatrox",
        impact: 0,
        riot_id: "Me#NA1",
      },
      {
        participant_id: 6,
        is_me: false,
        role: "TOP",
        team: "enemy",
        champion: "Darius",
        champion_name: "Darius",
        impact: 0,
        riot_id: "Enemy#NA1",
      },
    ],
    ...overrides,
  };
}

describe("impactCurve", () => {
  it("handles the no-credit case gracefully", () => {
    const review = createTestReview({
      moments: [
        {
          id: "m1",
          t_start: 300,
          t_end: 320,
          title: "Fight",
          delta: 0.05,
          p_before: 0.5,
          p_after: 0.55,
          involves_me: true,
          kill_gold: 300,
          zone: "river",
          grade: "!",
          credit: [],
          damage: [],
          drivers: [],
          events: [],
        },
      ],
    });

    const curve = impactCurve(review);
    expect(curve).not.toBeNull();
    expect(curve!.points.length).toBeGreaterThan(0);

    for (const pt of curve!.points) {
      expect(pt.me).toBe(0);
      expect(pt.opponent).toBe(0);
      expect(pt.hasMyDot).toBe(false);
    }
  });

  it("calculates running sum of my Moment.credit share * 100", () => {
    const review = createTestReview({
      moments: [
        {
          id: "m1",
          t_start: 300,
          t_end: 320,
          title: "First fight",
          delta: 0.05,
          p_before: 0.5,
          p_after: 0.55,
          involves_me: true,
          kill_gold: 300,
          zone: "river",
          grade: "!",
          credit: [{ participant_id: 1, share: 0.05 }],
          damage: [],
          drivers: [],
          events: [],
        },
        {
          id: "m2",
          t_start: 600,
          t_end: 625,
          title: "Dragon fight",
          delta: -0.04,
          p_before: 0.55,
          p_after: 0.51,
          involves_me: true,
          kill_gold: 0,
          zone: "pit",
          grade: "?",
          credit: [{ participant_id: 1, share: -0.02 }],
          damage: [],
          drivers: [],
          events: [],
        },
        {
          id: "m3",
          t_start: 1000,
          t_end: 1030,
          title: "Baron push",
          delta: 0.08,
          p_before: 0.51,
          p_after: 0.59,
          involves_me: true,
          kill_gold: 600,
          zone: "baron",
          grade: "!!",
          credit: [{ participant_id: 1, share: 0.062 }],
          damage: [],
          drivers: [],
          events: [],
        },
      ],
    });

    const curve = impactCurve(review)!;
    expect(curve).not.toBeNull();

    // Before any moment: 0
    expect(impactAt(curve.points, 0)?.me).toBe(0);
    expect(impactAt(curve.points, 299)?.me).toBe(0);

    // After m1 (share +0.05): running sum is +5.0
    expect(impactAt(curve.points, 300)?.me).toBe(5);
    expect(impactAt(curve.points, 450)?.me).toBe(5);

    // After m2 (share -0.02): running sum is 5 - 2 = +3.0
    expect(impactAt(curve.points, 600)?.me).toBe(3);
    expect(impactAt(curve.points, 900)?.me).toBe(3);

    // After m3 (share +0.062): running sum is 3 + 6.2 = +9.2
    expect(impactAt(curve.points, 1000)?.me).toBe(9.2);
    expect(impactAt(curve.points, 1800)?.me).toBe(9.2);
  });

  it("creates steps at moment times with dots only when involved", () => {
    const m1: Moment = {
      id: "m1",
      t_start: 400,
      t_end: 420,
      title: "Fight 1",
      delta: 0.06,
      p_before: 0.5,
      p_after: 0.56,
      involves_me: true,
      kill_gold: 300,
      zone: "river",
      grade: "!",
      credit: [{ participant_id: 1, share: 0.04 }],
      damage: [],
      drivers: [],
      events: [],
    };
    const m2: Moment = {
      id: "m2",
      t_start: 800,
      t_end: 820,
      title: "Fight 2 (opponent only)",
      delta: -0.05,
      p_before: 0.56,
      p_after: 0.51,
      involves_me: false,
      kill_gold: 300,
      zone: "bot",
      grade: null,
      credit: [{ participant_id: 6, share: 0.03 }],
      damage: [],
      drivers: [],
      events: [],
    };

    const review = createTestReview({ moments: [m1, m2] });
    const curve = impactCurve(review)!;

    // Step at 400
    const ptBefore400 = impactAt(curve.points, 399)!;
    expect(ptBefore400.me).toBe(0);

    const ptAt400 = curve.points.find((p) => p.t === 400)!;
    expect(ptAt400).toBeDefined();
    expect(ptAt400.me).toBe(4);
    expect(ptAt400.hasMyDot).toBe(true);
    expect(ptAt400.myShare).toBe(0.04);
    expect(ptAt400.moment?.id).toBe("m1");

    // Between 400 and 800
    expect(impactAt(curve.points, 600)?.me).toBe(4);

    // At 800: I have no credit, so me stays at 4 and hasMyDot is false
    const ptAt800 = curve.points.find((p) => p.t === 800)!;
    expect(ptAt800).toBeDefined();
    expect(ptAt800.me).toBe(4);
    expect(ptAt800.hasMyDot).toBe(false);
    expect(ptAt800.myShare).toBeNull();
  });

  it("builds the opponent line for same role, other team", () => {
    const review = createTestReview({
      moments: [
        {
          id: "m1",
          t_start: 500,
          t_end: 520,
          title: "Fight",
          delta: 0.05,
          p_before: 0.5,
          p_after: 0.55,
          involves_me: true,
          kill_gold: 300,
          zone: "mid",
          grade: "!",
          credit: [
            { participant_id: 1, share: 0.05 },
            { participant_id: 6, share: -0.031 },
          ],
          damage: [],
          drivers: [],
          events: [],
        },
      ],
    });

    const curve = impactCurve(review)!;
    expect(curve.opponent).toMatchObject({
      participant_id: 6,
      role: "TOP",
      team: "enemy",
      champion_name: "Darius",
    });

    // Before 500: opponent is 0
    expect(impactAt(curve.points, 499)?.opponent).toBe(0);

    // At 500: opponent steps by -0.031 * 100 = -3.1
    expect(impactAt(curve.points, 500)?.opponent).toBe(-3.1);
    expect(impactAt(curve.points, 1800)?.opponent).toBe(-3.1);
  });

  it("handles missing opponent when no enemy shares my role", () => {
    const review = createTestReview({
      players: [
        {
          participant_id: 1,
          is_me: true,
          role: "TOP",
          team: "ally",
          champion: "Aatrox",
          champion_name: "Aatrox",
          impact: 0,
          riot_id: "Me#NA1",
        },
        {
          participant_id: 6,
          is_me: false,
          role: "JUNGLE", // different role
          team: "enemy",
          champion: "Sejuani",
          champion_name: "Sejuani",
          impact: 0,
          riot_id: "Enemy#NA1",
        },
      ],
    });

    const curve = impactCurve(review)!;
    expect(curve.opponent).toBeNull();

    for (const pt of curve.points) {
      expect(pt.opponent).toBeNull();
    }
  });

  it("returns null when no me player exists", () => {
    const review = createTestReview({
      players: [
        {
          participant_id: 2,
          is_me: false,
          role: "TOP",
          team: "ally",
          champion: "Aatrox",
          champion_name: "Aatrox",
          impact: 0,
          riot_id: "Other#NA1",
        },
      ],
    });

    expect(impactCurve(review)).toBeNull();
  });

  it("shapes team win chance centered on starting curve p", () => {
    const review = createTestReview({
      curve: [
        { t: 0, p: 0.5 },
        { t: 600, p: 0.64 }, // +14 points
        { t: 1200, p: 0.4 }, // -10 points
      ],
      match: { ...baseReview.match, duration_s: 1200 },
    });

    const curve = impactCurve(review)!;
    expect(impactAt(curve.points, 0)?.team).toBe(0);
    expect(impactAt(curve.points, 600)?.team).toBe(14);
    expect(impactAt(curve.points, 1200)?.team).toBe(-10);
  });

  it("selects the first moment I'm in when several start at the same time", () => {
    const fight = (id: string, credit: Moment["credit"]): Moment => ({
      id,
      t_start: 500,
      t_end: 520,
      title: id,
      delta: 0.02,
      p_before: 0.5,
      p_after: 0.52,
      involves_me: true,
      kill_gold: 0,
      zone: "mid",
      grade: null,
      credit,
      damage: [],
      drivers: [],
      events: [],
    });
    const review = createTestReview({
      moments: [
        fight("enemy only", [{ participant_id: 6, share: 0.03 }]),
        fight("mine", [{ participant_id: 1, share: 0.02 }]),
      ],
    });

    const curve = impactCurve(review)!;
    expect(curve.points.find((p) => p.t === 500)?.moment?.id).toBe("mine");
  });

  it("falls back to the first moment at that time when I'm in none", () => {
    const fight = (id: string): Moment => ({
      id,
      t_start: 500,
      t_end: 520,
      title: id,
      delta: 0.03,
      p_before: 0.5,
      p_after: 0.53,
      involves_me: false,
      kill_gold: 0,
      zone: "mid",
      grade: null,
      credit: [{ participant_id: 6, share: 0.03 }],
      damage: [],
      drivers: [],
      events: [],
    });
    const review = createTestReview({ moments: [fight("first"), fight("second")] });

    const curve = impactCurve(review)!;
    expect(curve.points.find((p) => p.t === 500)?.moment?.id).toBe("first");
  });
});

describe("formatImpactPoints", () => {
  it("formats positive numbers with +", () => {
    expect(formatImpactPoints(9.2)).toBe("+9.2%");
    expect(formatImpactPoints(15)).toBe("+15.0%");
  });

  it("formats negative numbers with minus sign", () => {
    expect(formatImpactPoints(-3.1)).toBe("−3.1%");
  });

  it("formats zero as 0.0%", () => {
    expect(formatImpactPoints(0)).toBe("0.0%");
  });

  it("takes the sign and the digits from the same rounded value", () => {
    // -0.25 rounds to -0.2, so it's -0.2%, not -0.3%
    expect(formatImpactPoints(-0.25)).toBe("−0.2%");
    expect(formatImpactPoints(-0.04)).toBe("0.0%");
  });
});
