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

/** The number above a tile's label, e.g. tile("comebacks") is "2". */
const tile = (label: string) => screen.getByText(label).previousElementSibling;

afterEach(() => vi.unstubAllGlobals());

describe("Patterns", () => {
  it("renders nothing with fewer than 2 reviewed games", () => {
    const { container } = renderPatterns(games(1, 5));
    expect(container).toBeEmptyDOMElement();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("asks for the reviewed games in match id order and shows the tiles", async () => {
    renderPatterns(games(5));
    expect(await screen.findByText("from 5 reviewed games")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/patterns?games=NA1_1:4,NA1_2:4,NA1_3:4,NA1_4:4,NA1_5:4"),
      expect.anything(),
    );
    // (4 "?" + 3 "??") over 5 games
    expect(tile("mistakes a game")).toHaveTextContent("1.4");
    expect(tile("win chance left in missed windows")).toHaveTextContent("21%");
    expect(tile("comebacks")).toHaveTextContent("2");
    expect(tile("thrown lead")).toHaveTextContent("1");
  });

  it("shows each breakdown with its losses and sizes the bars against the biggest", async () => {
    renderPatterns(games(5));
    expect(await screen.findByText("When you lose win chance")).toBeInTheDocument();
    expect(screen.getByText("Where")).toBeInTheDocument();
    expect(screen.getByText("Why")).toBeInTheDocument();
    expect(screen.getByText("−42%")).toBeInTheDocument();
    expect(screen.getByText("Bot lane")).toBeInTheDocument();
    // "Mid game" lost the most win chance, so its bar is full width.
    expect(screen.getByText("Early game")).toBeInTheDocument();
    expect(screen.getByText("Mid game").nextElementSibling).toHaveStyle({ width: "100%" });
  });

  it("hides a breakdown with no mistakes", async () => {
    renderPatterns(games(5), { ...patternsJson, by_driver: [] });
    expect(await screen.findByText("Where")).toBeInTheDocument();
    expect(screen.queryByText("Why")).toBeNull();
  });

  it("shows the lane block only when there is one", async () => {
    renderPatterns(games(5), { ...patternsJson, lane_gold_10: null, lane_cs_10: null });
    await screen.findByText("Where");
    expect(screen.queryByText(/Lane at 10:00/)).toBeNull();
  });

  it("shows the lane gold and CS with signs", async () => {
    renderPatterns(games(5));
    expect(await screen.findByText("Lane at 10:00 vs your opponent")).toBeInTheDocument();
    expect(screen.getByText("+350")).toBeInTheDocument();
    expect(screen.getByText("+6")).toBeInTheDocument();
  });

  it("uses the singular for one comeback", async () => {
    renderPatterns(games(5), { ...patternsJson, comebacks: 1 });
    expect(await screen.findByText("comeback")).toBeInTheDocument();
    expect(tile("comeback")).toHaveTextContent("1");
  });
});
