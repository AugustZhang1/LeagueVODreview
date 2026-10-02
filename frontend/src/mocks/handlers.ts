import { delay, http, HttpResponse } from "msw";
import type { Health, ModelMetrics, PlayerGames, Review } from "../api/models";
import healthJson from "./health.json";
import modelJson from "./model.json";
import playerJson from "./player.json";
import { makeReview } from "./makeReview";

/**
 * `?mock=key_expired | rate_limited | unavailable | empty` on the page URL picks a state to
 * look at. It is read once per page load, so later in-app navigation keeps it.
 */
export type MockMode = "key_expired" | "rate_limited" | "unavailable" | "empty" | null;

function readMode(): MockMode {
  if (typeof location === "undefined") return null;
  const v = new URLSearchParams(location.search).get("mock");
  return v === "key_expired" || v === "rate_limited" || v === "unavailable" || v === "empty"
    ? v
    : null;
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
    default:
      return null;
  }
}

const health = healthJson as Health;
const player = playerJson as PlayerGames;
const reviews = new Map<string, Review>();

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
    const url = new URL(request.url);
    const start = Number(url.searchParams.get("start") ?? 0);
    const count = Number(url.searchParams.get("count") ?? 10);
    const games = mode === "empty" ? [] : player.games.slice(start, start + count);
    const next = start + count < player.games.length && mode !== "empty" ? start + count : null;
    return HttpResponse.json({
      ...player,
      riot_id: `${params.name}#${params.tag}`,
      platform: String(params.platform).toUpperCase(),
      games,
      next_start: next,
    });
  }),

  http.get("/api/review/:matchId", async ({ params, request }) => {
    await delay(600);
    const bad = failure();
    if (bad) return bad;
    if (mode === "empty") return errorResponse("match_not_found", "Match not found.", 404);
    const p = Number(new URL(request.url).searchParams.get("p") ?? 4);
    const key = `${params.matchId}:${p}`;
    if (!reviews.has(key)) reviews.set(key, makeReview(String(params.matchId), p));
    return HttpResponse.json(reviews.get(key));
  }),

  http.get("/api/model", async () => {
    await delay(300);
    if (mode === "empty") return errorResponse("no_model", "No trained model yet.", 404);
    return HttpResponse.json(modelJson as ModelMetrics);
  }),
];
