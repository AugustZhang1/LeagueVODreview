import { describe, expect, it } from "vitest";
import { makeReview } from "../../../mocks/makeReview";
import { buildHeader, buildScoreboard } from "./boardModel";

const review = makeReview();
const snap = review.snapshots[88];

describe("buildScoreboard", () => {
  const [ally, enemy] = buildScoreboard(review, snap);
  it("lists ally then enemy, five each, in role order", () => {
    expect(ally.header.team).toBe("ally");
    expect(enemy.header.team).toBe("enemy");
    expect(ally.rows.map((r) => r.player.role)).toEqual([
      "TOP",
      "JUNGLE",
      "MIDDLE",
      "BOTTOM",
      "UTILITY",
    ]);
    expect(enemy.rows).toHaveLength(5);
    expect(ally.rows.filter((r) => r.player.is_me)).toHaveLength(1);
  });
  it("gives each row six items plus the trinket", () => {
    expect(ally.rows[0].slots).toHaveLength(7);
  });
  it("copies team totals from the snapshot", () => {
    expect(ally.header.kills).toBe(snap.teams.ally.kills);
    expect(enemy.header.towers).toBe(snap.teams.enemy.towers);
  });
});

describe("buildHeader", () => {
  const base = {
    kills: 3,
    gold: 48200,
    towers: 5,
    dragons: ["Ocean", "Infernal"],
    soul: null,
    grubs: 0,
    heralds: 0,
    barons: 1,
    buff: null,
  };
  const other = { ...base, gold: 44100 };
  it("shows the gold lead only on the leading team", () => {
    expect(buildHeader("ally", base, other).lead).toBe("+4.1k");
    expect(buildHeader("enemy", other, base).lead).toBeNull();
  });
  it("writes out dragons, soul and the buff time", () => {
    const h = buildHeader(
      "ally",
      { ...base, soul: "Ocean", buff: { kind: "baron", ends_in_s: 72 } },
      other,
    );
    expect(h.dragonCount).toBe(2);
    expect(h.dragonTypes).toEqual(["Ocean", "Infernal"]);
    expect(h.soul).toBe("Ocean soul");
    expect(h.buff).toEqual({ label: "Baron", time: "01:12" });
  });
});

describe("rows", () => {
  it("marks a dead player with the respawn time", () => {
    const state = { ...snap.players[0], respawn_in_s: 11.4 };
    const s = { ...snap, players: [state, ...snap.players.slice(1)] };
    const [ally, enemy] = buildScoreboard(review, s);
    const row = [...ally.rows, ...enemy.rows].find(
      (r) => r.player.participant_id === state.participant_id,
    )!;
    expect(row.dead).toBe(true);
    expect(row.deadText).toBe("dead 0:12");
  });
});
