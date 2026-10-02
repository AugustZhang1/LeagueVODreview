import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { ApiError, apiGet } from "./client";
import type { Health, ModelMetrics, PlayerGames, Review } from "./models";

const PAGE_SIZE = 10;

/** Rate limits wait `retry_after_s` and try again; other 4xx errors are final. */
export function retryDelay(failureCount: number, error: unknown): number {
  if (error instanceof ApiError && error.code === "rate_limited") {
    return (error.retryAfterS ?? 5) * 1000;
  }
  return Math.min(1000 * 2 ** failureCount, 8000);
}

export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError) {
    if (error.code === "rate_limited") return true;
    if (error.status >= 400 && error.status < 500) return false;
  }
  return failureCount < 2;
}

const retryOptions = { retry: shouldRetry, retryDelay } as const;

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiGet<Health>("/api/health", signal),
    refetchInterval: 60_000,
    ...retryOptions,
  });
}

export function usePlayerGames(platform: string, name: string, tag: string) {
  return useInfiniteQuery({
    queryKey: ["player", platform, name, tag],
    queryFn: ({ pageParam, signal }) =>
      apiGet<PlayerGames>(
        `/api/player/${encodeURIComponent(platform)}/${encodeURIComponent(name)}/${encodeURIComponent(tag)}?start=${pageParam}&count=${PAGE_SIZE}`,
        signal,
      ),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_start ?? undefined,
    ...retryOptions,
  });
}

export function useReview(matchId: string, p: number) {
  return useQuery({
    queryKey: ["review", matchId, p],
    queryFn: ({ signal }) =>
      apiGet<Review>(`/api/review/${encodeURIComponent(matchId)}?p=${p}`, signal),
    staleTime: Infinity,
    ...retryOptions,
  });
}

export function useModel() {
  return useQuery({
    queryKey: ["model"],
    queryFn: ({ signal }) => apiGet<ModelMetrics>("/api/model", signal),
    ...retryOptions,
  });
}
