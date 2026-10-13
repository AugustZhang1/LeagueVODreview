import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Moment, ObjectiveWindow } from "../../api/models";
import { makeReview } from "../../mocks/makeReview";
import { WindowDetail } from "./WindowDetail";

const review = makeReview();
const base = review.moments[0];
const win: ObjectiveWindow = {
  id: "w9",
  t_start: 600,
  t_end: 640,
  title: "Enemy Lee Sin dead, Dragon up",
  reason: "Lee Sin dead for 0:31",
  options: [{ what: "Dragon", value: 0.07 }],
  value: 0.07,
  used: false,
  taken: [],
};
const at = (id: string, t_end: number, title: string): Moment => ({
  ...base,
  id,
  t_end,
  title,
  delta: 0.04,
});

describe("WindowDetail", () => {
  it("shows the span, worth and title above the reason", () => {
    render(<WindowDetail window={win} moments={[]} />);
    const detail = screen.getByTestId("detail-w9");
    expect(within(detail).getByText("10:00–10:40")).toBeInTheDocument();
    expect(within(detail).getByText("worth ~+7%")).toBeInTheDocument();
    expect(within(detail).getByRole("heading", { level: 3 })).toHaveTextContent(win.title);
    expect(within(detail).getByText(win.reason)).toBeInTheDocument();
  });

  it("lists the moments that ended in the window or 10 s after it", () => {
    const moments = [
      at("before", 599, "Too early"),
      at("inside", 620, "Bot drake fight"),
      at("grace", 650, "Top tower"),
      at("late", 651, "Too late"),
    ];
    render(<WindowDetail window={win} moments={moments} />);
    expect(screen.getByText("What happened instead")).toBeInTheDocument();
    expect(screen.getByText("Bot drake fight")).toBeInTheDocument();
    expect(screen.getByText("Top tower")).toBeInTheDocument();
    expect(screen.queryByText("Too early")).toBeNull();
    expect(screen.queryByText("Too late")).toBeNull();
    expect(screen.getAllByText("+4%")).toHaveLength(2);
    expect(screen.queryByText(/didn't take/)).toBeNull();
  });

  it("says so when nothing happened in the window", () => {
    render(<WindowDetail window={win} moments={[at("late", 900, "Too late")]} />);
    expect(screen.getByText("What happened instead")).toBeInTheDocument();
    expect(
      screen.getByText("Your team didn't take an objective or tower in time."),
    ).toBeInTheDocument();
  });

  it("names what the team took on a used window, without duplicates", () => {
    const used: ObjectiveWindow = {
      ...win,
      used: true,
      taken: ["Dragon", "bot outer tower", "Dragon"],
    };
    render(<WindowDetail window={used} moments={[at("inside", 620, "Bot drake fight")]} />);
    expect(screen.getByText("Your team took: Dragon, bot outer tower")).toBeInTheDocument();
    expect(screen.queryByText("What happened instead")).toBeNull();
    expect(screen.queryByText("Bot drake fight")).toBeNull();
    expect(within(screen.getByTestId("detail-w9")).getByText("Available")).toBeInTheDocument();
  });
});
