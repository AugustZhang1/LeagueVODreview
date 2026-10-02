import { describe, expect, it } from "vitest";
import { MAP_MAX, MAP_MIN, toCanvas } from "./map";

describe("toCanvas", () => {
  it("puts the game's bottom-left corner at the canvas bottom-left", () => {
    expect(toCanvas(MAP_MIN, MAP_MIN, 360)).toEqual({ cx: 0, cy: 360 });
  });
  it("puts the top-right corner at the canvas top-right (y flips)", () => {
    const { cx, cy } = toCanvas(MAP_MAX, MAP_MAX, 360);
    expect(cx).toBeCloseTo(360);
    expect(cy).toBeCloseTo(0);
  });
  it("maps the other two corners", () => {
    const tl = toCanvas(MAP_MIN, MAP_MAX, 100);
    expect(tl.cx).toBeCloseTo(0);
    expect(tl.cy).toBeCloseTo(0);
    const br = toCanvas(MAP_MAX, MAP_MIN, 100);
    expect(br.cx).toBeCloseTo(100);
    expect(br.cy).toBeCloseTo(100);
  });
  it("puts the middle of the map in the middle", () => {
    const mid = (MAP_MIN + MAP_MAX) / 2;
    const { cx, cy } = toCanvas(mid, mid, 360);
    expect(cx).toBeCloseTo(180);
    expect(cy).toBeCloseTo(180);
  });
  it("moves up the screen as game y grows", () => {
    expect(toCanvas(5000, 9000, 360).cy).toBeLessThan(toCanvas(5000, 3000, 360).cy);
  });
});
