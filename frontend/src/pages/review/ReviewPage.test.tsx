import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { makeReview } from "../../mocks/makeReview";
import { ReviewPage } from "./ReviewPage";

const counter = vi.hoisted(() => ({ chart: 0, board: 0 }));

vi.mock("./board/boardModel", async (orig) => {
  const mod = await orig<typeof import("./board/boardModel")>();
  return {
    ...mod,
    buildScoreboard: (...args: Parameters<typeof mod.buildScoreboard>) => {
      counter.board += 1;
      return mod.buildScoreboard(...args);
    },
  };
});

vi.mock("recharts", async (orig) => {
  const mod = await orig<typeof import("recharts")>();
  return {
    ...mod,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) => <div>{children}</div>,
    AreaChart: () => {
      counter.chart += 1;
      return <div data-testid="area-chart" />;
    },
  };
});

const review = makeReview();
const ended = [...review.moments].sort((a, b) => a.t_end - b.t_end);
const end = (i: number) => Math.round(ended[i].t_end);
const graded = ended.filter((m) => m.grade);

function setup(search = "?p=4", data = review) {
  window.history.replaceState(null, "", `/review/${review.match.match_id}${search}`);
  const client = new QueryClient();
  client.setQueryData(["review", review.match.match_id, 4], data);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/review/${review.match.match_id}${search}`]}>
        <Routes>
          <Route path="/review/:matchId" element={<ReviewPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const slider = () => screen.getByRole("slider") as HTMLInputElement;
const urlT = () => new URLSearchParams(window.location.search).get("t");

describe("review page", () => {
  beforeEach(() => {
    counter.chart = 0;
    counter.board = 0;
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.useRealTimers());

  it("reads the final result at the end of the scrubber", async () => {
    const d = review.match.duration_s;
    const curve = [
      ...review.curve.filter((pt) => pt.t < d),
      { t: d - 1, p: 0.85 },
      { t: d + 0.4, p: 1 },
    ];
    setup("?p=4", { ...review, curve });
    const user = userEvent.setup();
    await user.keyboard("{End}");
    expect(slider().value).toBe(String(d));
    expect(slider().getAttribute("aria-valuetext")).toMatch(/win chance 100%$/);
    expect(screen.getAllByText("100%").length).toBeGreaterThan(0);
  });

  it("starts at the t in the URL", () => {
    setup("?p=4&t=300");
    expect(slider().value).toBe("300");
    expect(slider()).toHaveAttribute(
      "aria-valuetext",
      expect.stringMatching(/^05:00, win chance \d+%$/),
    );
  });

  it("writes t to the URL at most every 200 ms", () => {
    vi.useFakeTimers();
    setup();
    const spy = vi.spyOn(window.history, "replaceState");
    fireEvent.change(slider(), { target: { value: "100" } });
    fireEvent.change(slider(), { target: { value: "200" } });
    fireEvent.change(slider(), { target: { value: "300" } });
    expect(spy.mock.calls.length).toBeLessThanOrEqual(1);
    act(() => void vi.advanceTimersByTime(250));
    expect(urlT()).toBe("300");
    expect(spy.mock.calls.length).toBeLessThanOrEqual(2);
  });

  it("steps through moments with the arrow keys and Shift+arrows", async () => {
    const user = userEvent.setup();
    setup();
    await user.keyboard("{ArrowRight}");
    expect(slider().value).toBe(String(end(0)));
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(slider().value).toBe(String(end(2)));
    await user.keyboard("{ArrowLeft}");
    expect(slider().value).toBe(String(end(1)));
    await user.keyboard("{Shift>}{ArrowRight}{/Shift}");
    expect(slider().value).toBe(String(end(1) + 15));
    await user.keyboard("{End}");
    expect(slider().value).toBe(String(Math.floor(review.match.duration_s)));
    await user.keyboard("{Home}");
    expect(slider().value).toBe("0");
  });

  it("reaches every moment by keyboard", async () => {
    const user = userEvent.setup();
    setup();
    for (const m of ended) {
      await user.keyboard("{ArrowRight}");
      expect(document.querySelector(`[data-moment="${m.id}"] [aria-current]`)).not.toBeNull();
    }
  });

  it("ignores shortcuts while typing", async () => {
    const user = userEvent.setup();
    setup();
    const input = document.createElement("input");
    document.body.append(input);
    input.focus();
    await user.keyboard("{ArrowRight}");
    expect(slider().value).toBe("0");
    input.remove();
  });

  it("filters the moments", async () => {
    const user = userEvent.setup();
    setup();
    const list = () => document.querySelectorAll("[data-moment]");
    expect(list()).toHaveLength(review.moments.length);
    await user.click(screen.getByRole("button", { name: "Graded" }));
    expect(list()).toHaveLength(graded.length);
    await user.click(screen.getByRole("button", { name: "Mine" }));
    expect(list()).toHaveLength(review.moments.filter((m) => m.involves_me).length);
  });

  it("seeks when the graph is clicked", () => {
    setup();
    const hit = screen.getByTestId("graph-hit");
    hit.getBoundingClientRect = () => ({ left: 0, width: 1000 }) as DOMRect;
    fireEvent.click(hit, { clientX: 500 });
    expect(slider().value).toBe(String(Math.round(review.match.duration_s / 2)));
  });

  it("shows a tooltip with time and win chance when hovering the graph", () => {
    setup();
    const hit = screen.getByTestId("graph-hit");
    hit.getBoundingClientRect = () => ({ left: 0, width: 1000 }) as DOMRect;
    fireEvent.mouseMove(hit, { clientX: 500 });
    expect(screen.getByRole("status")).toHaveTextContent(/^\d\d:\d\d\d+%/);
  });

  it("does not redraw the chart when only t changes", () => {
    setup();
    const before = counter.chart;
    expect(before).toBeGreaterThan(0);
    fireEvent.change(slider(), { target: { value: "500" } });
    fireEvent.change(slider(), { target: { value: "900" } });
    expect(counter.chart).toBe(before);
  });

  it("does not rebuild the scoreboard while t stays inside one snapshot", () => {
    // a snapshot where nobody is dead, and the same for the next one
    const idx = review.snapshots.findIndex(
      (sn, i) =>
        [sn, review.snapshots[i + 1]].every((x) => x?.players.every((p) => p.respawn_in_s === 0)) &&
        i > 4,
    );
    expect(idx).toBeGreaterThan(0);
    const base = idx * 15;
    setup(`?p=4&t=${base}`);
    const before = counter.board;
    for (let t = base + 1; t < base + 15; t++)
      fireEvent.change(slider(), { target: { value: String(t) } });
    expect(counter.board).toBe(before);
    fireEvent.change(slider(), { target: { value: String(base + 15) } });
    expect(counter.board).toBe(before + 1);
  });

  it("opens a moment's detail and seeks to its end when its row is clicked", async () => {
    const user = userEvent.setup();
    setup();
    const m = graded[0];
    const row = document.querySelector(`[data-moment="${m.id}"]`) as HTMLElement;
    await user.click(within(row).getByRole("button"));
    expect(slider().value).toBe(String(Math.round(m.t_end)));
    const detail = screen.getByTestId(`detail-${m.id}`);
    expect(detail).toHaveTextContent("%");
    expect(detail).toHaveTextContent(m.zone.slice(1));
    expect(detail.querySelectorAll("li")).toHaveLength(m.events.length);
    expect(screen.getByTestId(`marker-${m.id}`)).toHaveAttribute("data-grown");
  });

  it("shows the header facts and a link back to the games", () => {
    setup();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /^(Victory|Defeat) as Ahri/,
    );
    expect(screen.getByText("Length")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Games/ })).toHaveAttribute("href", "/p/na/Me/NA1");
  });

  it("shows the building skeleton while loading", () => {
    window.history.replaceState(null, "", "/review/x?p=4");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/review/x?p=4"]}>
          <Routes>
            <Route path="/review/:matchId" element={<ReviewPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("Building review…")).toBeInTheDocument();
  });

  describe("Open replay", () => {
    const stubFetch = (available: boolean, reason: string | null) => {
      const calls: { url: string; body?: string }[] = [];
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string, init?: RequestInit) => {
          calls.push({ url, body: init?.body as string | undefined });
          const body = url.includes("/api/replay/status") ? { available, reason } : { ok: true };
          return new Response(JSON.stringify(body), { status: 200 });
        }),
      );
      return calls;
    };
    const button = () => screen.getByRole("button", { name: "Open in replay" });

    it("is disabled and does nothing while no replay is open", async () => {
      const calls = stubFetch(false, "Replays only exist for the current patch");
      const user = userEvent.setup();
      setup("?p=4&t=300");
      await waitFor(() => expect(calls.length).toBeGreaterThan(0));
      expect(button()).toHaveAttribute("aria-disabled", "true");
      await user.hover(button());
      expect(await screen.findByRole("tooltip")).toHaveTextContent(
        "Replays only exist for the current patch",
      );
      await user.click(button());
      await user.keyboard("o");
      expect(calls.some((c) => c.url.includes("/api/replay/seek"))).toBe(false);
    });

    it("seeks the replay to t from the button and from the O key", async () => {
      const calls = stubFetch(true, null);
      const user = userEvent.setup();
      setup("?p=4&t=300");
      await waitFor(() => expect(button()).toHaveAttribute("aria-disabled", "false"));
      await user.click(button());
      await user.keyboard("o");
      await waitFor(() =>
        expect(calls.filter((c) => c.url.endsWith("/api/replay/seek"))).toHaveLength(2),
      );
      for (const c of calls.filter((c) => c.url.endsWith("/api/replay/seek"))) {
        expect(JSON.parse(c.body!)).toEqual({ match_id: review.match.match_id, t: 300 });
      }
    });
  });
});
