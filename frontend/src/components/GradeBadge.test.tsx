import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GradeBadge } from "./GradeBadge";

describe("GradeBadge", () => {
  it.each([
    ["!!", "Great"],
    ["!", "Good"],
    ["?", "Mistake"],
    ["??", "Blunder"],
  ] as const)("announces %s as %s", (grade, name) => {
    render(<GradeBadge grade={grade} />);
    expect(screen.getByRole("img", { name })).toBeInTheDocument();
  });

  it("includes the count in the name when given", () => {
    render(<GradeBadge grade="!!" count={2} />);
    expect(screen.getByRole("img", { name: "Great, 2" })).toBeInTheDocument();
  });

  it("keeps the glyph out of the accessibility tree", () => {
    render(<GradeBadge grade="??" />);
    expect(screen.getByText("??")).toHaveAttribute("aria-hidden", "true");
  });
});
