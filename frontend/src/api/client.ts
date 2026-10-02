import type { components } from "./types";

type ErrorResponse = components["schemas"]["ErrorResponse"];

export class ApiError extends Error {
  readonly code: string;
  readonly retryAfterS: number | null;
  readonly status: number;

  constructor(code: string, message: string, status: number, retryAfterS: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryAfterS = retryAfterS;
  }
}

function isErrorResponse(body: unknown): body is ErrorResponse {
  if (typeof body !== "object" || body === null || !("error" in body)) return false;
  const err = (body as { error: unknown }).error;
  return (
    typeof err === "object" && err !== null && typeof (err as { code?: unknown }).code === "string"
  );
}

/** Turns a failed response into an ApiError, reading `{"error": {...}}` when the body has it. */
export async function parseError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // not JSON; fall through to the generic error
  }
  if (isErrorResponse(body)) {
    const { code, message, retry_after_s } = body.error;
    return new ApiError(code, message, res.status, retry_after_s ?? null);
  }
  return new ApiError("http_error", `Request failed with status ${res.status}`, res.status);
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError("network_error", "Can't reach the app's server.", 0);
  }
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("network_error", "Can't reach the app's server.", 0);
  }
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}
