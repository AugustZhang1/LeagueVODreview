import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const renders = vi.hoisted(() => ({ count: 0 }));
vi.mock("../../components/ChampIcon", () => ({
  ChampIcon: () => {
    renders.count++;
    return null;
  },
}));

import { makeReview } from "../../mocks/makeReview";
import { Scoreboard } from "./Scoreboard";

const review = makeReview();

describe("Scoreboard", () => {
  it("renders both teams and marks your row", () => {
    const { container } = render(
      <Scoreboard review={review} snapshot={review.snapshots[88]} t={1320} />,
    );
    expect(screen.getByText("Ally")).toBeInTheDocument();
    expect(screen.getByText("Enemy")).toBeInTheDocument();
    expect(container.querySelectorAll("tr")).toHaveLength(10);
    expect(screen.getByText("Me")).toBeInTheDocument();
  });

  it("re-renders on a new snapshot but not when only the parent updates", async () => {
    function Harness() {
      const [tick, setTick] = useState(0);
      const [idx, setIdx] = useState(10);
      return (
        <>
          <button onClick={() => setTick(tick + 1)}>tick {tick}</button>
          <button onClick={() => setIdx(idx + 1)}>next</button>
          <Scoreboard review={review} snapshot={review.snapshots[idx]} t={idx * 15} />
        </>
      );
    }
    renders.count = 0;
    render(<Harness />);
    const base = renders.count;
    expect(base).toBe(10);
    await userEvent.click(screen.getByText("tick 0"));
    await userEvent.click(screen.getByText("tick 1"));
    expect(renders.count).toBe(base);
    await userEvent.click(screen.getByText("next"));
    expect(renders.count).toBe(base + 10);
  });
});
