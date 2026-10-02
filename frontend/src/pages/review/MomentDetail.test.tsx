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
