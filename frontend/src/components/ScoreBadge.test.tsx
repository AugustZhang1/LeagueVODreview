import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";
import { ScoreBadge } from "./ScoreBadge";

/** The class of the score box, so colour bands can be compared without reading CSS. */
function boxClass(props: ComponentProps<typeof ScoreBadge>) {
  const { container, unmount } = render(<ScoreBadge {...props} />);
  const className = container.querySelector('[role="img"]')?.className ?? "";
  unmount();
  return className;
}

describe("ScoreBadge", () => {
  it("shows the score to one decimal", () => {
    render(<ScoreBadge score={8} />);
    expect(screen.getByRole("img", { name: "Score 8.0 out of 10" })).toHaveTextContent("8.0");
  });

  it("colours the score by band, rounding first", () => {
    const great = boxClass({ score: 8.3 });
    const good = boxClass({ score: 6.2 });
    const neutral = boxClass({ score: 4.5 });
    const blunder = boxClass({ score: 3.9 });
    expect(new Set([great, good, neutral, blunder]).size).toBe(4);
    expect(boxClass({ score: 7.96 })).toBe(great);
    expect(boxClass({ score: 6 })).toBe(good);
    expect(boxClass({ score: 3.96 })).toBe(neutral);
  });

  it("shows a dash of the same size when there is no score", () => {
    render(<ScoreBadge score={null} />);
    expect(screen.getByRole("img", { name: "No score" })).toHaveTextContent("–");
  });

  it("tags the MVP or ACE", () => {
    const { unmount } = render(<ScoreBadge score={8.3} badge="mvp" />);
    expect(screen.getByText("MVP")).toBeInTheDocument();
    unmount();
    render(<ScoreBadge score={3.9} badge="ace" />);
    expect(screen.getByText("ACE")).toBeInTheDocument();
  });

  it("gives the rank on md, with the label", () => {
    render(<ScoreBadge score={8.3} rank={1} label="Score" />);
    expect(screen.getByText("Score, 1st of 10")).toBeInTheDocument();
  });

  it.each([
    [2, "2nd"],
    [3, "3rd"],
    [4, "4th"],
    [10, "10th"],
  ])("ends rank %i with %s", (rank, word) => {
    render(<ScoreBadge score={5} rank={rank} />);
    expect(screen.getByText(`${word} of 10`)).toBeInTheDocument();
  });

  it("leaves the rank off on sm but keeps the tag", () => {
    render(<ScoreBadge score={8.3} rank={1} label="Score" badge="mvp" size="sm" />);
    expect(screen.queryByText(/of 10/)).not.toBeInTheDocument();
    expect(screen.getByText("MVP")).toBeInTheDocument();
  });
});
