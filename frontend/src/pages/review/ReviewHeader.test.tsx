import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CurvePoint, Moment, Review } from "../../api/models";
import { makeReview } from "../../mocks/makeReview";
import { HowToRead } from "./HowToRead";
import { comebackOf } from "./ReviewHeader";
import { TopMistakes } from "./TopMistakes";

const review = makeReview();
const me = review.players.find((p) => p.is_me)!;
const base = review.moments[0];

const mistake = (id: string, delta: number, patch: Partial<Moment> = {}): Moment => ({
  ...base,
  id,
  title: `Mistake ${id.toUpperCase()}`,
  involves_me: true,
  grade: "?",
  delta,
  ...patch,
});

/** A review whose curve is `points` followed by the final result point. */
function withCurve(result: "win" | "loss", points: CurvePoint[], finalP: number): Review {
  return {
    ...review,
    match: { ...review.match, result },
    curve: [...points, { t: 1900, p: finalP }],
  };
}

describe("comebackOf", () => {
  it("finds the low point of a win that dipped under 20%", () => {
    const r = withCurve(
      "win",
      [
        { t: 0, p: 0.5 },
        { t: 1120, p: 0.12 },
        { t: 1500, p: 0.6 },
      ],
      1,
    );
    expect(comebackOf(r)).toEqual({ kind: "comeback", p: 0.12, t: 1120 });
  });

  it("finds the high point of a loss that rose above 80%", () => {
    const r = withCurve(
      "loss",
      [
        { t: 0, p: 0.5 },
        { t: 1330, p: 0.85 },
        { t: 1500, p: 0.3 },
      ],
      0,
    );
    expect(comebackOf(r)).toEqual({ kind: "thrown", p: 0.85, t: 1330 });
  });

  it("returns null when neither applies", () => {
    const win = withCurve(
      "win",
      [
        { t: 0, p: 0.5 },
        { t: 600, p: 0.3 },
      ],
      1,
    );
    const loss = withCurve(
      "loss",
      [
        { t: 0, p: 0.5 },
        { t: 600, p: 0.7 },
      ],
      0,
    );
    expect(comebackOf(win)).toBeNull();
    expect(comebackOf(loss)).toBeNull();
  });

  it("ignores the final result point", () => {
    // The last point (a win ending at 5%) must not count as a comeback.
    const r = withCurve(
      "win",
      [
        { t: 0, p: 0.5 },
        { t: 600, p: 0.6 },
      ],
      0.05,
    );
    expect(comebackOf(r)).toBeNull();
  });
});

describe("TopMistakes", () => {
  it("lists my worst three mistakes, most negative first", () => {
    const moments = [
      mistake("a", -0.05),
      mistake("b", -0.2),
      mistake("c", -0.12),
      mistake("d", -0.08),
      mistake("e", -0.3, { involves_me: false }),
      mistake("f", -0.4, { grade: "!" }),
    ];
    render(
      <TopMistakes
        review={{ ...review, moments }}
        participantId={me.participant_id}
        onJump={vi.fn()}
      />,
    );
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(3);
    expect(links[0]).toHaveTextContent("Mistake B");
    expect(links[0]).toHaveTextContent("−20%");
    expect(links[1]).toHaveTextContent("Mistake C");
    expect(links[2]).toHaveTextContent("Mistake D");
  });

  it("calls onJump with the moment when a mistake is clicked", async () => {
    const onJump = vi.fn();
    const moments = [mistake("b", -0.2)];
    render(
      <TopMistakes
        review={{ ...review, moments }}
        participantId={me.participant_id}
        onJump={onJump}
      />,
    );
    await userEvent.click(screen.getByRole("link"));
    expect(onJump).toHaveBeenCalledWith(moments[0]);
  });

  it("says so when no mistake was graded against me", () => {
    const moments = [mistake("a", 0.1, { grade: "!", involves_me: true })];
    render(
      <TopMistakes
        review={{ ...review, moments }}
        participantId={me.participant_id}
        onJump={vi.fn()}
      />,
    );
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.getByText("No mistakes graded against you in this game.")).toBeInTheDocument();
  });
});

describe("HowToRead", () => {
  it("renders its summary, collapsed", () => {
    render(<HowToRead />);
    const summary = screen.getByText("How to read this");
    expect(summary.tagName).toBe("SUMMARY");
    expect(summary.closest("details")).not.toHaveAttribute("open");
  });
});
