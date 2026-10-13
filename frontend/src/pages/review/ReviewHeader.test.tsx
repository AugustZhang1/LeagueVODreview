import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { CurvePoint, Player, Review } from "../../api/models";
import { GRADES, gradeName } from "../../lib/grades";
import { makeReview } from "../../mocks/makeReview";
import { HowToRead } from "./HowToRead";
import { ReviewHeader, comebackOf, scoreRank } from "./ReviewHeader";

const review = makeReview();
const me = review.players.find((p) => p.is_me)!;

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

describe("scoreRank", () => {
  const at = (participant_id: number, score: number | null): Player => ({
    ...me,
    participant_id,
    score,
  });

  it("ranks by score, best first", () => {
    const players = [at(1, 5), at(2, 8.3), at(3, 6.2), at(4, 7)];
    expect(scoreRank(players, players[1])).toBe(1);
    expect(scoreRank(players, players[3])).toBe(2);
    expect(scoreRank(players, players[2])).toBe(3);
    expect(scoreRank(players, players[0])).toBe(4);
  });

  it("breaks ties by the lower participant id", () => {
    const players = [at(7, 8), at(3, 8), at(5, 8)];
    expect(scoreRank(players, players[1])).toBe(1);
    expect(scoreRank(players, players[2])).toBe(2);
    expect(scoreRank(players, players[0])).toBe(3);
  });

  it("ranks a player with no score below everyone who has one", () => {
    const players = [at(1, null), at(2, 0.5)];
    expect(scoreRank(players, players[1])).toBe(1);
  });

  it("has no rank when I have no score", () => {
    const players = [at(1, null), at(2, 0.5)];
    expect(scoreRank(players, players[0])).toBeNull();
  });
});

describe("ReviewHeader", () => {
  const renderHeader = (r: Review) =>
    render(
      <MemoryRouter>
        <ReviewHeader review={r} />
      </MemoryRouter>,
    );

  it("shows my score with its MVP tag and rank", () => {
    const players = review.players.map((p) =>
      p.is_me ? { ...p, score: 8.3, badge: "mvp" as const } : { ...p, score: 5 },
    );
    renderHeader({ ...review, players });
    expect(screen.getByRole("img", { name: "Score 8.3 out of 10" })).toBeInTheDocument();
    expect(screen.getByText("MVP")).toBeInTheDocument();
    expect(screen.getByText("Score, 1st of 10")).toBeInTheDocument();
  });

  it("ranks a tie by the lower participant id", () => {
    // everyone ties on 7, so the three players with lower ids (1 to 3) rank above me (id 4)
    const players = review.players.map((p) => ({ ...p, score: 7 }));
    renderHeader({ ...review, players });
    expect(screen.getByText("Score, 4th of 10")).toBeInTheDocument();
  });

  it("shows my grade counts", () => {
    renderHeader(review);
    expect(screen.getByText("Your grades")).toBeInTheDocument();
    for (const g of GRADES) {
      expect(
        screen.getByRole("img", { name: `${gradeName(g)}, ${review.summary.me[g]}` }),
      ).toBeInTheDocument();
    }
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
