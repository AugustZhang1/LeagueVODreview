import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { makeReview } from "../../mocks/makeReview";

vi.mock("./board/loadImage", () => ({ loadImage: vi.fn(() => Promise.resolve(null)) }));
const draw = vi.fn();
vi.mock("./board/drawMinimap", async (orig) => ({
  ...(await orig<typeof import("./board/drawMinimap")>()),
  drawMinimap: (...a: unknown[]) => draw(...a),
}));

import { Minimap } from "./Minimap";

const review = makeReview();

describe("Minimap", () => {
  beforeEach(() => {
    draw.mockClear();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({})) as never;
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      value: 360,
    });
    globalThis.ResizeObserver = class {
      observe() {}
      disconnect() {}
      unobserve() {}
    } as never;
    globalThis.requestAnimationFrame = (cb) => {
      cb(0);
      return 0;
    };
  });

  it("draws once the images have settled, and again only when inputs change", async () => {
    const snap = review.snapshots[88];
    const { rerender } = render(<Minimap review={review} snapshot={snap} t={snap.t} />);
    expect(screen.getByRole("img", { name: "Minimap" })).toBeInTheDocument();
    await waitFor(() => expect(draw).toHaveBeenCalledTimes(1));
    rerender(<Minimap review={review} snapshot={snap} t={snap.t} />);
    expect(draw).toHaveBeenCalledTimes(1);
    rerender(<Minimap review={review} snapshot={snap} t={snap.t + 5} />);
    await waitFor(() => expect(draw).toHaveBeenCalledTimes(2));
  });
});
