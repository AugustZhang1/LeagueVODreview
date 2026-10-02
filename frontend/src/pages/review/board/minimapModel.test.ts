import { describe, expect, it } from "vitest";
import { makeReview } from "../../../mocks/makeReview";
import {
  HIT_RADIUS,
  buildingMarks,
  championMarks,
  hitTest,
  killMarks,
  positionOpacity,
} from "./minimapModel";

const review = makeReview();
const snap = review.snapshots[88];
// The blue-side top outer tower, from the game's building list.
const TOWER = review.buildings.find((b) => b.x === 981 && b.y === 10441)!;

describe("buildingMarks", () => {
  it("places known buildings with the shared coordinate mapping", () => {
    const marks = buildingMarks(review.buildings, [], 360);
    const outer = marks.find((m) => m.id === TOWER.id)!;
    // game (981, 10441): near the left edge, upper half
    expect(outer.cx).toBeCloseTo(((981 + 120) / 14990) * 360, 3);
    expect(outer.cy).toBeCloseTo((1 - (10441 + 120) / 14990) * 360, 3);
    expect(outer.cx).toBeLessThan(40);
    expect(outer.cy).toBeLessThan(120);
  });
  it("marks destroyed buildings as down", () => {
    const marks = buildingMarks(review.buildings, [TOWER.id], 360);
    expect(marks.filter((m) => m.down).map((m) => m.id)).toEqual([TOWER.id]);
  });
});

describe("championMarks", () => {
  it("draws enemies first, allies next and you last", () => {
    const marks = championMarks(review.players, snap, snap.t, 360);
    expect(marks).toHaveLength(10);
    expect(marks.at(-1)!.isYou).toBe(true);
    const teams = marks.slice(0, -1).map((m) => m.team);
    expect(teams.indexOf("ally")).toBe(5);
    expect(teams.slice(0, 5).every((t) => t === "enemy")).toBe(true);
  });
  it("greys out the dead at 40% with respawn seconds", () => {
    const state = { ...snap.players[0], respawn_in_s: 11.2, pos_age_s: 0 };
    const s = { ...snap, players: [state, ...snap.players.slice(1)] };
    const dead = championMarks(review.players, s, s.t, 360).find(
      (m) => m.player.participant_id === state.participant_id,
    )!;
    expect(dead.dead).toBe(true);
    expect(dead.opacity).toBe(0.4);
    expect(dead.respawn).toBe(12);
  });
  it("counts the respawn down with t and revives the icon at zero", () => {
    const state = { ...snap.players[0], respawn_in_s: 10, pos_age_s: 0 };
    const s = { ...snap, players: [state, ...snap.players.slice(1)] };
    const mark = (t: number) =>
      championMarks(review.players, s, t, 360).find(
        (m) => m.player.participant_id === state.participant_id,
      )!;
    expect(mark(s.t + 8).respawn).toBe(2);
    expect(mark(s.t + 8).dead).toBe(true);
    expect(mark(s.t + 12).dead).toBe(false);
  });
  it("fades with position age", () => {
    expect(positionOpacity(0)).toBe(1);
    expect(positionOpacity(30)).toBeCloseTo(0.75);
    expect(positionOpacity(60)).toBe(0.5);
    expect(positionOpacity(200)).toBe(0.5);
  });
});

describe("killMarks", () => {
  it("keeps only kills from the last 10 seconds, counting time past the snapshot", () => {
    const s = {
      ...snap,
      recent_kills: [
        { x: 7000, y: 7000, team: "ally" as const, age_s: 4 },
        { x: 8000, y: 8000, team: "enemy" as const, age_s: 9 },
      ],
    };
    expect(killMarks(s, s.t, 360)).toHaveLength(2);
    expect(killMarks(s, s.t + 3, 360)).toHaveLength(1);
  });
});

describe("hitTest", () => {
  it("finds the topmost icon under the pointer", () => {
    const marks = championMarks(review.players, snap, snap.t, 360);
    const top = marks.at(-1)!;
    expect(hitTest(marks, top.cx + 1, top.cy)).toBe(top);
    expect(hitTest(marks, -50, -50)).toBeNull();
    expect(hitTest(marks, top.cx + HIT_RADIUS + 200, top.cy)).not.toBe(top);
  });
});
