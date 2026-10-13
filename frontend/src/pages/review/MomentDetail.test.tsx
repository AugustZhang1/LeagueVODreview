import { render, screen, within } from "@testing-library/react";
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

describe("MomentDetail your part", () => {
  const second = review.players.filter((p) => p.team === "ally" && !p.is_me)[1]!;
  const fight = (mine: number, mate: number, other = 0) =>
    withFight({
      damage: [
        { participant_id: ally.participant_id, dealt: mate, taken: 0 },
        { participant_id: me.participant_id, dealt: mine, taken: 0 },
        { participant_id: second.participant_id, dealt: other, taken: 0 },
        { participant_id: enemy.participant_id, dealt: 900, taken: 0 },
      ],
    });

  it("tags top damage on my team", () => {
    render(<MomentDetail moment={fight(3000, 1000)} review={review} />);
    expect(screen.getByTestId("your-part")).toHaveTextContent(
      "You 3,000, 75% of your team's · Top damage on your team",
    );
  });

  it("tags low damage under 15% of my team's", () => {
    render(<MomentDetail moment={fight(100, 1000, 900)} review={review} />);
    expect(screen.getByTestId("your-part")).toHaveTextContent("5% of your team's · Low damage");
  });

  it("has no tag in between, and no line when I did no fight damage", () => {
    const { rerender } = render(<MomentDetail moment={fight(500, 1000)} review={review} />);
    expect(screen.getByTestId("your-part")).toHaveTextContent(/^You 500, 33% of your team's$/);
    rerender(
      <MomentDetail
        moment={withFight({
          damage: [{ participant_id: ally.participant_id, dealt: 5, taken: 0 }],
        })}
        review={review}
      />,
    );
    expect(screen.queryByTestId("your-part")).not.toBeInTheDocument();
  });
});

describe("MomentDetail header", () => {
  it("shows the grade, time, zone and win chance change above the title", () => {
    const moment = withFight({
      grade: "??",
      t_end: 1000,
      zone: "baron pit",
      p_before: 0.76,
      p_after: 0.67,
      delta: -0.09,
      title: "Lost fight at Baron",
    });
    render(<MomentDetail moment={moment} review={review} />);
    const detail = screen.getByTestId(`detail-${moment.id}`);
    expect(within(detail).getByRole("img", { name: "Blunder" })).toBeInTheDocument();
    expect(within(detail).getByText("16:40")).toBeInTheDocument();
    expect(within(detail).getByText("Baron pit")).toBeInTheDocument();
    expect(within(detail).getByText("76% to 67%")).toBeInTheDocument();
    expect(within(detail).getByRole("heading", { level: 3 })).toHaveTextContent(
      "Lost fight at Baron",
    );
  });
});

describe("MomentDetail better play", () => {
  it("shows the tip when there is one", () => {
    const tip = "Fought 2v3: back off until your team can join.";
    const { rerender } = render(<MomentDetail moment={withFight({ tip })} review={review} />);
    expect(screen.getByTestId("tip")).toHaveTextContent(`Better play: ${tip}`);
    rerender(<MomentDetail moment={withFight({ tip: null })} review={review} />);
    expect(screen.queryByTestId("tip")).not.toBeInTheDocument();
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

describe("MomentDetail credit share", () => {
  it("renders negative share formatted with minus sign", () => {
    const moment = withFight({
      credit: [
        { participant_id: me.participant_id, share: -0.042 },
        { participant_id: ally.participant_id, share: 0.1 },
      ],
    });
    render(<MomentDetail moment={moment} review={review} />);
    expect(screen.getByTestId("your-share")).toHaveTextContent("Your share: −4.2%");
  });

  it("renders positive share formatted with plus sign", () => {
    const moment = withFight({
      credit: [{ participant_id: me.participant_id, share: 0.062 }],
    });
    render(<MomentDetail moment={moment} review={review} />);
    expect(screen.getByTestId("your-share")).toHaveTextContent("Your share: +6.2%");
  });

  it("hides share line when it rounds to 0.0%", () => {
    render(
      <MomentDetail
        moment={withFight({ credit: [{ participant_id: me.participant_id, share: 0.0003 }] })}
        review={review}
      />,
    );
    expect(screen.queryByTestId("your-share")).not.toBeInTheDocument();
  });

  it("hides share line when share is zero or credit is missing", () => {
    const { rerender } = render(
      <MomentDetail
        moment={withFight({ credit: [{ participant_id: me.participant_id, share: 0 }] })}
        review={review}
      />,
    );
    expect(screen.queryByTestId("your-share")).not.toBeInTheDocument();

    rerender(<MomentDetail moment={withFight({ credit: [] })} review={review} />);
    expect(screen.queryByTestId("your-share")).not.toBeInTheDocument();

    rerender(
      <MomentDetail
        moment={withFight({ credit: undefined } as unknown as Partial<Moment>)}
        review={review}
      />,
    );
    expect(screen.queryByTestId("your-share")).not.toBeInTheDocument();
  });
});
