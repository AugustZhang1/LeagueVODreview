import { describe, expect, it } from "vitest";
import openapi from "../../openapi.json";
import { formatTime } from "../lib/format";
import healthJson from "./health.json";
import modelJson from "./model.json";
import reviewFixture from "./review.fixture.json";
import { makeReview } from "./makeReview";
import playerJson from "./player.json";
import { validate } from "./schemaCheck";

const schema = (name: string) => ({ $ref: `#/components/schemas/${name}` });
const check = (value: unknown, name: string) => validate(openapi, schema(name), value);

describe("mocks match the API schema", () => {
  it("health", () => expect(check(healthJson, "Health")).toEqual([]));
  it("player", () => expect(check(playerJson, "PlayerGames")).toEqual([]));
  it("model", () => expect(check(modelJson, "ModelMetrics")).toEqual([]));
  it("review", () => expect(check(makeReview(), "Review")).toEqual([]));
  it("backend-made review fixture", () => expect(check(reviewFixture, "Review")).toEqual([]));
  it("the checker catches mistakes", () => {
    expect(
      check({ riot_key: "nope", model: { kind: "trained", version: "1" } }, "Health"),
    ).not.toEqual([]);
    expect(check({ riot_key: "ok" }, "Health")).not.toEqual([]);
  });
});

describe("makeReview", () => {
  const review = makeReview();
  it("is deterministic", () => {
    expect(makeReview()).toEqual(review);
  });
  it("is a 31:42 win with Ahri mid as participant 4", () => {
    expect(formatTime(review.match.duration_s)).toBe("31:42");
    const me = review.players.find((p) => p.is_me)!;
    expect(me).toMatchObject({ participant_id: 4, champion: "Ahri", role: "MIDDLE", team: "ally" });
    expect(review.players).toHaveLength(10);
  });
  it("has a curve every 15 s ending at GAME_END", () => {
    const { curve } = review;
    expect(curve[1].t - curve[0].t).toBe(15);
    expect(curve.at(-1)).toEqual({ t: 1902, p: 1 });
    expect(curve.slice(0, -1).every((c) => c.p > 0 && c.p < 1)).toBe(true);
  });
  it("has about 25 moments with every grade present", () => {
    expect(review.moments.length).toBeGreaterThanOrEqual(24);
    expect(review.moments.length).toBeLessThanOrEqual(30);
    const grades = new Set(review.moments.map((m) => m.grade));
    for (const g of ["!!", "!", "?", "??", null]) expect(grades.has(g as never)).toBe(true);
  });
  it("has a snapshot every 15 s, indexed by floor(t / 15), for 10 players", () => {
    review.snapshots.forEach((s, i) => {
      expect(s.t).toBe(i * 15);
      expect(s.players).toHaveLength(10);
    });
    expect(review.snapshots).toHaveLength(Math.floor(1902 / 15) + 1);
  });
  it("shows deaths with respawn timers", () => {
    const dead = review.snapshots.flatMap((s) => s.players).filter((p) => p.respawn_in_s > 0);
    expect(dead.length).toBeGreaterThan(5);
  });
  it("points the summary at the biggest swing", () => {
    const biggest = review.moments.find((m) => m.id === review.summary.biggest_id)!;
    const max = Math.max(...review.moments.map((m) => Math.abs(m.delta)));
    expect(Math.abs(biggest.delta)).toBe(max);
  });
  it("has 30 buildings and only knocks down ones that exist", () => {
    const ids = new Set(review.buildings.map((b) => b.id));
    expect(ids.size).toBe(30);
    const down = review.snapshots.at(-1)!.buildings_down;
    expect(down.length).toBeGreaterThan(5);
    expect(down.every((id) => ids.has(id))).toBe(true);
  });
  it("keeps positions inside the map", () => {
    for (const s of review.snapshots)
      for (const p of s.players) {
        expect(p.x).toBeGreaterThan(-120);
        expect(p.x).toBeLessThan(14870);
        expect(p.y).toBeGreaterThan(-120);
        expect(p.y).toBeLessThan(14870);
      }
  });
});
