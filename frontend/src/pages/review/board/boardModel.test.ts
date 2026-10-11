import { describe, expect, it } from "vitest";
import { makeReview } from "../../../mocks/makeReview";
import { buildHeader, buildObjectives, buildScoreboard } from "./boardModel";

const review = makeReview();
const snap = review.snapshots[88];
const timers = {
  dragon_in_s: 72,
  dragon_kind: "dragon" as const,
  baron_pit_in_s: 0,
  baron_pit_kind: "grubs" as const,
};

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
  it("counts grubs, heralds and barons", () => {
    const h = buildHeader("ally", { ...base, grubs: 2, heralds: 1 }, other);
    expect([h.grubs, h.heralds, h.barons]).toEqual([2, 1, 1]);
  });
});

describe("buildObjectives", () => {
  it("counts the dragon and pit down from the snapshot, then says up", () => {
    const s = { ...snap, t: 100, objectives: timers };
    expect(buildObjectives(s)).toEqual({
      dragon: { label: "Dragon", time: "1:12" },
      pit: { label: "Grubs", time: "up" },
    });
    expect(buildObjectives(s, 115)?.dragon.time).toBe("0:57");
    expect(buildObjectives(s, 200)?.dragon.time).toBe("up");
  });
  it("names an Elder dragon and a Baron pit", () => {
    const s = {
      ...snap,
      t: 100,
      objectives: {
        ...timers,
        dragon_kind: "elder" as const,
        baron_pit_in_s: 40,
        baron_pit_kind: "baron" as const,
      },
    };
    expect(buildObjectives(s)).toEqual({
      dragon: { label: "Elder", time: "1:12" },
      pit: { label: "Baron", time: "0:40" },
    });
  });
  it("is null when the review has no objectives", () => {
    expect(buildObjectives({ ...snap, objectives: null })).toBeNull();
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

  it("counts the timer down between snapshots and never below zero", () => {
    const state = { ...snap.players[0], respawn_in_s: 10 };
    const s = { ...snap, players: [state, ...snap.players.slice(1)] };
    const text = (t: number) => {
      const [ally, enemy] = buildScoreboard(review, s, t);
      return [...ally.rows, ...enemy.rows].find(
        (r) => r.player.participant_id === state.participant_id,
      )!;
    };
    expect(text(s.t).deadText).toBe("dead 0:10");
    expect(text(s.t + 8).deadText).toBe("dead 0:02");
    const done = text(s.t + 12);
    expect(done.dead).toBe(false);
    expect(done.deadText).toBeNull();
  });
});
