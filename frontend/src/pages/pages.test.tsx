import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import healthJson from "../mocks/health.json";
import modelJson from "../mocks/model.json";
import playerJson from "../mocks/player.json";
import { GamesPage } from "./GamesPage";
import { ModelPage } from "./ModelPage";
import { SearchPage } from "./SearchPage";
import { readMetrics } from "./model/metrics";
import { parseRiotId } from "./search/storage";

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }));
}

function mockFetch(routes: Record<string, () => Promise<Response>>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const hit = Object.keys(routes).find((k) => url.startsWith(k));
      return hit ? routes[hit]() : json({ error: { code: "x", message: "x" } }, 500);
    }),
  );
}

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname}</p>;
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/p/:platform/:name/:tag" element={<GamesPage />} />
          <Route path="/model" element={<ModelPage />} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("parseRiotId", () => {
  it("checks the # and the lengths", () => {
    expect(parseRiotId("Name")).toHaveProperty("error");
    expect(parseRiotId("#NA1")).toHaveProperty("error");
    expect(parseRiotId("A".repeat(17) + "#NA1")).toHaveProperty("error");
    expect(parseRiotId("Me#NA1")).toEqual({ name: "Me", tag: "NA1" });
    expect(parseRiotId("Name#NA")).toHaveProperty("error");
    expect(parseRiotId("Name#NA1234")).toHaveProperty("error");
    expect(parseRiotId(" Name#NA1 ")).toEqual({ name: "Name", tag: "NA1" });
  });
});

describe("SearchPage", () => {
  it("shows a validation message and does not look anything up", async () => {
    mockFetch({});
    renderAt("/");
    await userEvent.type(screen.getByLabelText("Riot ID"), "nohash{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Name#NA1");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("looks the player up, remembers it and goes to the games", async () => {
    mockFetch({ "/api/player/euw1/Mimic/NA1": () => json(playerJson) });
    renderAt("/");
    await userEvent.selectOptions(screen.getByLabelText("Server"), "euw1");
    await userEvent.type(screen.getByLabelText("Riot ID"), "Mimic#NA1{Enter}");
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/p/euw1/Mimic/NA1"));
    expect(localStorage.getItem("lvr.platform")).toBe("euw1");
    expect(localStorage.getItem("lvr.recent")).toContain("Mimic");
  });

  it("shows the lookup error under the input", async () => {
    mockFetch({
      "/api/player": () => json({ error: { code: "riot_id_not_found", message: "" } }, 404),
    });
    renderAt("/");
    await userEvent.type(screen.getByLabelText("Riot ID"), "Nobody#NA1{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No player called Nobody#NA1 on NA.",
    );
  });

  it("lists recent searches as links", () => {
    localStorage.setItem(
      "lvr.recent",
      JSON.stringify([{ platform: "na1", name: "Me", tag: "NA1" }]),
    );
    renderAt("/");
    expect(screen.getByRole("link", { name: "Me#NA1" })).toHaveAttribute("href", "/p/na1/Me/NA1");
  });
});

describe("GamesPage", () => {
  it("links games to the review and leaves remakes unlinked", async () => {
    mockFetch({ "/api/player": () => json({ ...playerJson, next_start: 10 }) });
    renderAt("/p/na1/Me/NA1");
    const links = await screen.findAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "/review/NA1_5300000001?p=4");
    expect(screen.getByText("Remake").closest("a")).toBeNull();
    expect(screen.getByText("Gold III, 47 LP")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load 10 more" })).toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    mockFetch({
      "/api/player": () => json({ ...playerJson, games: [], next_start: null }),
    });
    renderAt("/p/na1/Me/NA1");
    expect(await screen.findByText("No ranked solo games found.")).toBeInTheDocument();
  });

  it("offers Retry when Riot is unavailable", async () => {
    mockFetch({
      "/api/player": () => json({ error: { code: "riot_unavailable", message: "" } }, 502),
    });
    renderAt("/p/na1/Me/NA1");
    expect(
      await screen.findByRole("button", { name: "Retry" }, { timeout: 8000 }),
    ).toBeInTheDocument();
  }, 10000);
});

describe("ModelPage", () => {
  it("writes the summary in words", async () => {
    mockFetch({ "/api/model": () => json(modelJson), "/api/health": () => json(healthJson) });
    renderAt("/model");
    expect(await screen.findByText(/1,998/)).toBeInTheDocument();
    expect(screen.getByText("Accuracy by minute")).toBeInTheDocument();
    expect(screen.getAllByText("Numbers")).toHaveLength(3);
    expect(screen.getByText("your tier")).toBeInTheDocument();
  });

  it("shows the no-model panel", async () => {
    mockFetch({
      "/api/model": () => json({ error: { code: "model_missing", message: "" } }, 404),
      "/api/health": () => json(healthJson),
    });
    renderAt("/model");
    expect(await screen.findByText(/No trained model yet/)).toBeInTheDocument();
  });
});

describe("readMetrics", () => {
  it("reads the shape training/train.py writes", () => {
    const lgb = (acc: number) => ({ accuracy: acc, log_loss: 0.5, brier: 0.2 });
    const view = readMetrics({
      trained_at: "2026-10-01T09:30:00+00:00",
      games: 10,
      patches: ["26.19"],
      models: {
        lightgbm: {
          overall: lgb(0.7),
          by_minute: [
            { bucket: "5-10", ...lgb(0.6), rows: 1 },
            { bucket: "10-15", ...lgb(0.66), rows: 1 },
          ],
          by_tier: [{ tier: "Gold", games: 4, accuracy: 0.7, log_loss: 0.5 }],
        },
        baseline: {
          overall: { accuracy: 0.5, log_loss: 0.69, brier: 0.25 },
          by_minute: [
            { bucket: "5-10", ...lgb(0.5), rows: 1 },
            { bucket: "10-15", ...lgb(0.52), rows: 1 },
          ],
        },
      },
      calibration: [
        { bin: 6, predicted: 0.66, actual: 0.7, count: 5 },
        { bin: 7, predicted: 0.72, actual: 0.7, count: 5 },
      ],
      feature_importance: [{ feature: "gold_diff", gain: 3 }],
    });
    expect(view.accuracyAt10).toBe(0.66);
    expect(view.baselineLogLoss).toBe(0.69);
    expect(view.minutes[1]).toEqual({ label: "10–15", lightgbm: 0.66, baseline: 0.52 });
    expect(view.nearest70?.predicted).toBe(0.72);
    expect(view.tiers).toHaveLength(1);
    expect(view.features[0].share).toBe(1);
  });
});
