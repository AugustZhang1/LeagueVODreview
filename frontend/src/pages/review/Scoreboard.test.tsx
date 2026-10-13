import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
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

  it("shows the dragon and pit timers and the counts above zero", () => {
    render(<Scoreboard review={review} snapshot={review.snapshots[88]} t={1320} />);
    expect(screen.getByText("3:10")).toBeInTheDocument();
    expect(screen.getByText("up")).toBeInTheDocument();
    expect(screen.getByText("Herald")).toBeInTheDocument();
    expect(screen.queryByText("Grubs")).toBeNull();
  });

  it("counts the objective timers down as the scrubber moves", () => {
    const { rerender } = render(
      <Scoreboard review={review} snapshot={review.snapshots[88]} t={1320} />,
    );
    rerender(<Scoreboard review={review} snapshot={review.snapshots[88]} t={1330} />);
    expect(screen.getByText("3:00")).toBeInTheDocument();
  });

  it("hides the timers when the review has no objectives", () => {
    render(
      <Scoreboard
        review={review}
        snapshot={{ ...review.snapshots[88], objectives: null }}
        t={1320}
      />,
    );
    expect(screen.queryByText("Dragon")).toBeNull();
    expect(screen.queryByText("3:10")).toBeNull();
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

  it("renders the score in its own column after the name, with one decimal and its parts tooltip", async () => {
    render(<Scoreboard review={review} snapshot={review.snapshots[88]} t={1320} />);
    const score = screen.getByText("8.3");
    const row = score.closest("tr") as HTMLElement;
    const mvp = review.players.find((p) => p.badge === "mvp");
    if (!mvp) throw new Error("no player has the mvp badge");
    expect(within(row).getByText("MVP")).toBeInTheDocument();
    const cells = row.querySelectorAll("td");
    expect(cells).toHaveLength(8);
    expect(cells[1]).toHaveAttribute("title", mvp.riot_id);
    expect(within(cells[1]).getByText(mvp.riot_id.split("#")[0])).toBeInTheDocument();
    expect(cells[2]).toBe(score.closest("td"));
    // the tooltip is on the focusable wrapper around the badge
    await userEvent.hover(score.closest("[tabindex]") as HTMLElement);
    const tip = await screen.findByRole("tooltip");
    expect(tip).toHaveTextContent("Score for the whole game, 0-10");
    expect(tip).toHaveTextContent("Gold/min 8.9 · vs lane 8.9 · KP 5.6 · Impact 9.1 · Fights 8.9");
  });

  it("marks your row with a 'you' after the name", () => {
    render(<Scoreboard review={review} snapshot={review.snapshots[88]} t={1320} />);
    const me = screen.getByText("Me").closest("tr") as HTMLElement;
    expect(within(me).getByText("you")).toBeInTheDocument();
    expect(screen.getAllByText("you")).toHaveLength(1);
  });

  it("renders no score for a player with a null score", () => {
    const noScoreReview = {
      ...review,
      players: review.players.map((p) => ({ ...p, score: null, score_parts: null })),
    };
    render(<Scoreboard review={noScoreReview} snapshot={review.snapshots[88]} t={1320} />);
    expect(screen.queryAllByText("-")).toHaveLength(0);
    expect(screen.queryAllByText(/^\d+\.\d$/)).toHaveLength(0);
    expect(screen.getByText("Me")).toBeInTheDocument();
  });

  it("puts the MVP tag on the mvp player's row and the ACE tag on the ace player's row", () => {
    render(<Scoreboard review={review} snapshot={review.snapshots[88]} t={1320} />);
    const rowOf = (badge: "mvp" | "ace") => {
      const holder = review.players.find((p) => p.badge === badge);
      if (!holder) throw new Error(`no player has the ${badge} badge`);
      return screen.getByText(holder.riot_id.split("#")[0]).closest("tr");
    };
    expect(screen.getByText("MVP").closest("tr")).toBe(rowOf("mvp"));
    expect(screen.getByText("ACE").closest("tr")).toBe(rowOf("ace"));
  });
});
