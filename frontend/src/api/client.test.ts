import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet, parseError } from "./client";
import { retryDelay, shouldRetry } from "./queries";

const json = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("parseError", () => {
  it("reads the backend's error body", async () => {
    const err = await parseError(
      json({ error: { code: "rate_limited", message: "Slow down", retry_after_s: 8 } }, 429),
    );
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("rate_limited");
    expect(err.message).toBe("Slow down");
    expect(err.retryAfterS).toBe(8);
    expect(err.status).toBe(429);
  });
  it("leaves retryAfterS null when absent", async () => {
    const err = await parseError(json({ error: { code: "key_expired", message: "Expired" } }, 401));
    expect(err.retryAfterS).toBeNull();
  });
  it("falls back to http_error for other bodies", async () => {
    const err = await parseError(new Response("<html>bad gateway</html>", { status: 502 }));
    expect(err.code).toBe("http_error");
    expect(err.status).toBe(502);
    const odd = await parseError(json({ detail: "nope" }, 422));
    expect(odd.code).toBe("http_error");
  });
});

describe("apiGet", () => {
  it("returns parsed JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ riot_key: "ok" }, 200)));
    await expect(apiGet("/api/health")).resolves.toEqual({ riot_key: "ok" });
  });
  it("throws ApiError for error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ error: { code: "match_not_found", message: "No" } }, 404)),
    );
    await expect(apiGet("/api/review/x")).rejects.toMatchObject({
      code: "match_not_found",
      status: 404,
    });
  });
  it("turns a network failure into network_error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiGet("/api/health")).rejects.toMatchObject({ code: "network_error", status: 0 });
  });
});

describe("retry rules", () => {
  const rate = new ApiError("rate_limited", "", 429, 8);
  it("retries rate limits after retry_after_s", () => {
    expect(shouldRetry(5, rate)).toBe(true);
    expect(retryDelay(0, rate)).toBe(8000);
  });
  it("does not retry other 4xx errors", () => {
    expect(shouldRetry(0, new ApiError("riot_id_not_found", "", 404))).toBe(false);
    expect(shouldRetry(0, new ApiError("key_expired", "", 401))).toBe(false);
  });
  it("retries server and network errors a couple of times", () => {
    expect(shouldRetry(0, new ApiError("riot_unavailable", "", 502))).toBe(true);
    expect(shouldRetry(2, new ApiError("riot_unavailable", "", 502))).toBe(false);
    expect(shouldRetry(0, new ApiError("network_error", "", 0))).toBe(true);
  });
});
