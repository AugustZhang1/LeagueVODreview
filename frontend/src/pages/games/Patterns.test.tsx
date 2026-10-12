import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { GameSummary } from "../../api/models";
import patternsJson from "../../mocks/patterns.json";
import playerJson from "../../mocks/player.json";
import { Patterns } from "./Patterns";

const sample = playerJson.games[0] as GameSummary;

/** `total` games, the first `reviewed` of them reviewed. */
function games(reviewed: number, total = reviewed): GameSummary[] {
  return Array.from({ length: total }, (_, i) => ({
    ...sample,
    match_id: `NA1_${i + 1}`,
    reviewed: i < reviewed,
  }));
}

/** Renders with `data` as the /api/patterns answer. */
function renderPatterns(list: GameSummary[], data: unknown = patternsJson) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(data)))),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Patterns games={list} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("Patterns", () => {
  it("renders nothing with fewer than 2 reviewed games", () => {
    const { container } = renderPatterns(games(1, 5));
    expect(container).toBeEmptyDOMElement();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("asks for the reviewed games in match id order and sums up the summary", async () => {
    renderPatterns(games(5));
    expect(
      await screen.findByText(
        "Patterns in your 5 reviewed games: 1.4 mistakes a game, most win chance lost in mid game",
      ),
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/patterns?games=NA1_1:4,NA1_2:4,NA1_3:4,NA1_4:4,NA1_5:4"),
      expect.anything(),
    );
    expect(
      screen.getByText(
        "4 wins, 1 loss · 2 comebacks · 1 thrown lead · Missed windows: 5 (worth ~+21% in total), used 7",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Bot lane")).toBeInTheDocument();
  });

  it("hides a table with no mistakes", async () => {
    renderPatterns(games(5), { ...patternsJson, by_driver: [] });
    expect(await screen.findByText("When")).toBeInTheDocument();
    expect(screen.queryByText("Why")).toBeNull();
  });

  it("shows the lane line only when there is one", async () => {
    renderPatterns(games(5), { ...patternsJson, lane_gold_10: null, lane_cs_10: null });
    await screen.findByText("When");
    expect(screen.queryByText(/At 10:00/)).toBeNull();
  });

  it("leaves out windows when there were none", async () => {
    renderPatterns(games(5), { ...patternsJson, windows_missed: 0, windows_used: 0 });
    expect(
      await screen.findByText("4 wins, 1 loss · 2 comebacks · 1 thrown lead"),
    ).toBeInTheDocument();
  });

  it("shows the lane line with the average", async () => {
    renderPatterns(games(5));
    expect(
      await screen.findByText("At 10:00 vs your lane opponent: +350 gold, +6 CS (average)"),
    ).toBeInTheDocument();
  });
});
