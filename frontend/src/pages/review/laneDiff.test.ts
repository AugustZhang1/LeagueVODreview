import { describe, expect, it } from "vitest";
import type { Review } from "../../api/models";
import reviewFixture from "../../mocks/review.fixture.json";
import { diffAt, laneDiff, type LanePoint } from "./laneDiff";

const review = reviewFixture as unknown as Review;

describe("laneDiff", () => {
  it("pairs me with the enemy player in my role", () => {
    const lane = laneDiff(review)!;
    expect(lane.opponent).toMatchObject({ champion_name: "Zed", role: "MIDDLE", team: "enemy" });
  });

  it("has one point per snapshot, my value minus theirs", () => {
    const lane = laneDiff(review)!;
    expect(lane.points).toHaveLength(review.snapshots.length);
    const sn = review.snapshots[60];
    const mine = sn.players.find((p) => p.participant_id === 4)!;
    const theirs = sn.players.find((p) => p.participant_id === 8)!;
    expect(lane.points[60]).toEqual({
      t: sn.t,
      gold: mine.gold - theirs.gold,
      cs: mine.cs - theirs.cs,
    });
  });

  it("keeps the sign: I am ahead when my gold is higher", () => {
    const edited = structuredClone(review);
    const sn = edited.snapshots[1];
    sn.players.find((p) => p.participant_id === 4)!.gold = 1000;
    sn.players.find((p) => p.participant_id === 8)!.gold = 400;
    sn.players.find((p) => p.participant_id === 4)!.cs = 10;
    sn.players.find((p) => p.participant_id === 8)!.cs = 12;
    expect(laneDiff(edited)!.points[1]).toEqual({ t: sn.t, gold: 600, cs: -2 });
  });

  it("returns null when there is no opponent in my role", () => {
    const solo = {
      ...review,
      players: review.players.map((p) => ({ ...p, team: "ally" as const })),
    };
    expect(laneDiff(solo)).toBeNull();
  });
});

describe("diffAt", () => {
  const points: LanePoint[] = [
    { t: 0, gold: 0, cs: 0 },
    { t: 15, gold: 100, cs: 2 },
    { t: 30, gold: -50, cs: 1 },
  ];

  it("returns the point at t", () => {
    expect(diffAt(points, 30)).toEqual(points[2]);
  });

  it("returns the point just before t", () => {
    expect(diffAt(points, 22)).toEqual(points[1]);
    expect(diffAt(points, 500)).toEqual(points[2]);
  });

  it("returns null before the first point or with no points", () => {
    expect(diffAt(points, -1)).toBeNull();
    expect(diffAt([], 10)).toBeNull();
  });
});
