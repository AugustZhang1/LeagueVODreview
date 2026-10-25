import { delay, http, HttpResponse } from "msw";
import type {
  Health,
  ModelMetrics,
  Patterns,
  PlayerGames,
  ReplayStatus,
  Review,
} from "../api/models";
import healthJson from "./health.json";
import modelJson from "./model.json";
import patternsJson from "./patterns.json";
import playerJson from "./player.json";
import reviewFixture from "./review.fixture.json";
import showcase from "./showcase.json";

/**
 * `?mock=` with one of the `MODES` below on the page URL picks a state to
 * look at. It is read once per page load, so later in-app navigation keeps it.
 */
export type MockMode =
  | "key_expired"
  | "rate_limited"
  | "unavailable"
  | "unsupported_queue"
  | "server_error"
  | "empty"
  | "replay_open"
  | null;

const MODES: MockMode[] = [
  "key_expired",
  "rate_limited",
  "unavailable",
  "unsupported_queue",
  "server_error",
  "empty",
  "replay_open",
];

function readMode(): MockMode {
  if (typeof location === "undefined") return null;
  const v = new URLSearchParams(location.search).get("mock");
  return MODES.find((m) => m === v) ?? null;
}

const mode = readMode();

function errorResponse(code: string, message: string, status: number, retryAfterS?: number) {
  return HttpResponse.json(
    { error: { code, message, ...(retryAfterS ? { retry_after_s: retryAfterS } : {}) } },
    { status, headers: retryAfterS ? { "Retry-After": String(retryAfterS) } : undefined },
  );
}

function failure() {
  switch (mode) {
    case "key_expired":
      return errorResponse("key_expired", "Riot API key expired.", 401);
    case "rate_limited":
      return errorResponse("rate_limited", "Rate limit reached.", 429, 8);
    case "unavailable":
      return errorResponse("riot_unavailable", "Riot's API isn't responding.", 502);
    case "server_error":
      return errorResponse("internal_error", "Something broke.", 500);
    default:
      return null;
  }
}

/**
 * The GitHub Pages build (`--mode pages`) serves real games from the trained
 * model instead, exported from the local cache with names and match ids
 * replaced. Tests and `dev:mock` keep the fixtures above.
 */
const real = import.meta.env.MODE === "pages";
const player = (real ? showcase.player : playerJson) as PlayerGames;
const health = (
  real
    ? { ...showcase.health, demo_player: { riot_id: player.riot_id, platform: "na1" } }
    : healthJson
) as Health;
const fixture = reviewFixture as unknown as Review;
const reviews = showcase.reviews as unknown as Record<string, Review>;
const modelMetrics = (real ? showcase.model : modelJson) as unknown as ModelMetrics;
const patterns = (real ? showcase.patterns : patternsJson) as Patterns;

function reviewFor(matchId: string): Review {
  if (real) return reviews[matchId] ?? Object.values(reviews)[0];
  return { ...fixture, match: { ...fixture.match, match_id: matchId } };
}
const replayReason = "Open this game's replay in the League client";

export const handlers = [
  http.get("/api/health", async () => {
    await delay(150);
    if (mode === "key_expired") return HttpResponse.json({ ...health, riot_key: "expired" });
    return HttpResponse.json(health);
  }),

  http.get("/api/player/:platform/:name/:tag", async ({ params, request }) => {
    await delay(400);
    const bad = failure();
    if (bad) return bad;
    if (String(params.name).toLowerCase() === "nobody") {
      return errorResponse("riot_id_not_found", "Riot ID not found.", 404);
    }
    if (real && `${params.name}#${params.tag}`.toLowerCase() !== player.riot_id.toLowerCase()) {
      return errorResponse(
        "demo_only",
        `This demo only has ${player.riot_id}'s games. Looking up other players needs the full app with a Riot API key.`,
        404,
      );
    }
    const url = new URL(request.url);
    const start = Number(url.searchParams.get("start") ?? 0);
    const count = Number(url.searchParams.get("count") ?? 10);
    const games = mode === "empty" ? [] : player.games.slice(start, start + count);
    const next = start + count < player.games.length && mode !== "empty" ? start + count : null;
    return HttpResponse.json({
      ...player,
      riot_id: real ? player.riot_id : `${params.name}#${params.tag}`,
      platform: String(params.platform).toUpperCase(),
      games,
      next_start: next,
    });
  }),

  http.get("/api/review/:matchId", async ({ params }) => {
    await delay(600);
    const bad = failure();
    if (bad) return bad;
    if (mode === "unsupported_queue") {
      return errorResponse("unsupported_queue", "Only ranked solo/duo games.", 400);
    }
    if (mode === "empty") return errorResponse("match_not_found", "Match not found.", 404);
    return HttpResponse.json(reviewFor(String(params.matchId)));
  }),

  http.get("/api/worlds/live", () => HttpResponse.json({ games: [] })),
  http.get("/api/worlds/matches", () => HttpResponse.json({ matches: [] })),
  http.get("/api/worlds/match/:id", () => HttpResponse.json({ games: [] })),

  http.get("/api/replay/status", async () => {
    const status: ReplayStatus = { available: false, reason: replayReason };
    if (mode === "replay_open") return HttpResponse.json({ available: true, reason: null });
    return HttpResponse.json(status);
  }),

  http.post("/api/replay/seek", () => HttpResponse.json({ ok: true })),

  http.get("/api/model", async () => {
    await delay(300);
    if (mode === "empty") return errorResponse("model_missing", "No trained model yet.", 404);
    return HttpResponse.json(modelMetrics);
  }),

  http.get("/api/patterns", async () => {
    await delay(200);
    return HttpResponse.json(patterns);
  }),
];
