import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../components/ChampIcon", () => ({ ChampIcon: () => null }));

import type { Moment } from "../../api/models";
import { makeReview } from "../../mocks/makeReview";
import { MomentDetail } from "./MomentDetail";

const review = makeReview();
const ally = review.players.find((p) => p.team === "ally" && !p.is_me)!;
const me = review.players.find((p) => p.is_me)!;
const enemy = review.players.find((p) => p.team === "enemy")!;
const base = review.moments[0];

const withFight = (patch: Partial<Moment>): Moment => ({ ...base, ...patch });

describe("MomentDetail damage", () => {
  it("renders a row per champion and the team totals", () => {
    const moment = withFight({
      damage: [
        { participant_id: ally.participant_id, dealt: 2000, taken: 100 },
        { participant_id: me.participant_id, dealt: 1500, taken: 0 },
        { participant_id: enemy.participant_id, dealt: 1000, taken: 3500 },
      ],
      kill_gold: 0,
    });
    render(<MomentDetail moment={moment} review={review} />);
    expect(screen.getAllByTestId("damage-row")).toHaveLength(3);
    expect(screen.getByText("Damage")).toBeInTheDocument();
    expect(screen.getByText(/Your team/)).toHaveTextContent("Your team 3,500 vs enemy 1,000");
    expect(screen.queryByText(/Kill gold/)).not.toBeInTheDocument();
  });

  it("renders no damage section when the field is missing", () => {
    const moment = { ...base, damage: undefined, kill_gold: undefined } as unknown as Moment;
    render(<MomentDetail moment={moment} review={review} />);
    expect(screen.queryByText("Damage")).not.toBeInTheDocument();
    expect(screen.queryByText(/Kill gold/)).not.toBeInTheDocument();
  });

  it("shows signed kill gold", () => {
    const { rerender } = render(
      <MomentDetail moment={withFight({ damage: [], kill_gold: 350 })} review={review} />,
    );
    expect(screen.getByText(/Kill gold/)).toHaveTextContent("Kill gold: +350");
    rerender(<MomentDetail moment={withFight({ damage: [], kill_gold: -350 })} review={review} />);
    expect(screen.getByText(/Kill gold/)).toHaveTextContent("Kill gold: −350");
  });
});

describe("MomentDetail why", () => {
  const drivers = [
    { label: "Baron buff", change: -0.9 },
    { label: "Gold lead", change: 0.3 },
    { label: "Towers", change: 0.16 },
  ];

  it("lists the drivers with a bar each", () => {
    render(<MomentDetail moment={withFight({ drivers })} review={review} />);
    expect(screen.getByText("Why")).toBeInTheDocument();
    const rows = screen.getAllByTestId("driver-row");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Baron buff");
    expect(rows[2]).toHaveTextContent("Towers");
  });

  it("hides the block when there are no drivers or the field is missing", () => {
    const { rerender } = render(
      <MomentDetail moment={withFight({ drivers: [] })} review={review} />,
    );
    expect(screen.queryByText("Why")).not.toBeInTheDocument();
    const old = { ...base, drivers: undefined } as unknown as Moment;
    rerender(<MomentDetail moment={old} review={review} />);
    expect(screen.queryByText("Why")).not.toBeInTheDocument();
  });

  it("shows the early-game note only before 5 minutes", () => {
    const { rerender } = render(
      <MomentDetail moment={withFight({ t_end: 240 })} review={review} />,
    );
    expect(screen.getByText(/Early game/)).toBeInTheDocument();
    rerender(<MomentDetail moment={withFight({ t_end: 400 })} review={review} />);
    expect(screen.queryByText(/Early game/)).not.toBeInTheDocument();
  });

  it("shows the drivers on a graded moment of the mock review", () => {
    const dragon = review.moments.find((m) => m.id === "m02")!;
    render(<MomentDetail moment={dragon} review={review} />);
    expect(screen.getByText("Your dragons")).toBeInTheDocument();
  });
});
