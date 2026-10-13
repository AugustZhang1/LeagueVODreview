import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Review } from "../../api/models";
import { makeReview } from "../../mocks/makeReview";
import { LaneChart } from "./LaneChart";

const review = makeReview();

/** The review with the reviewed player's lane result set to `lane`. */
const withLane = (lane: number | null): Review => ({
  ...review,
  players: review.players.map((p) => (p.is_me ? { ...p, lane } : p)),
});

const title = () => screen.getByRole("heading", { name: /^Lane vs / });

describe("LaneChart title", () => {
  it("shows the lane result at 14:00 with a plus sign", () => {
    render(<LaneChart review={withLane(0.062)} />);
    expect(title()).toHaveTextContent("Lane vs Zed · +6.2% at 14:00");
  });

  it("uses a real minus sign for a lane loss", () => {
    render(<LaneChart review={withLane(-0.021)} />);
    expect(title()).toHaveTextContent("Lane vs Zed · −2.1% at 14:00");
  });

  it("shows 0.0% with no sign at a zero lane", () => {
    render(<LaneChart review={withLane(0)} />);
    expect(title()).toHaveTextContent("Lane vs Zed · 0.0% at 14:00");
  });

  it("leaves the lane result out when there is none", () => {
    render(<LaneChart review={withLane(null)} />);
    expect(title()).toHaveTextContent(/^Lane vs Zed$/);
  });
});
