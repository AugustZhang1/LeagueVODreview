import { ApiError } from "../api/client";

export type ErrorContext = { name?: string; tag?: string; platform?: string };

export type DescribedError = {
  message: string;
  /** Retrying by hand can help. */
  canRetry: boolean;
};

export function describeError(error: unknown, ctx: ErrorContext = {}): DescribedError {
  const code = error instanceof ApiError ? error.code : "unknown";
  switch (code) {
    case "riot_id_not_found": {
      const who = ctx.name && ctx.tag ? `${ctx.name}#${ctx.tag}` : "that Riot ID";
      return {
        message: `No player called ${who}${ctx.platform ? ` on ${ctx.platform.toUpperCase()}` : ""}.`,
        canRetry: false,
      };
    }
    case "key_expired":
      return {
        message:
          "Riot API key expired. Paste a new one after RIOT_API_KEY= in .env; it's picked up within a minute.",
        canRetry: false,
      };
    case "rate_limited": {
      const s = error instanceof ApiError ? error.retryAfterS : null;
      return {
        message: `Riot's rate limit is full, retrying${s ? ` in ${s} s` : " soon"}.`,
        canRetry: false,
      };
    }
    case "riot_unavailable":
      return { message: "Riot's API isn't responding.", canRetry: true };
    case "match_not_found":
      return { message: "Match not found.", canRetry: false };
    case "unsupported_queue":
      return { message: "Only ranked solo/duo games can be reviewed.", canRetry: false };
    case "demo_only":
      return { message: (error as ApiError).message, canRetry: false };
    default:
      return { message: "Something went wrong.", canRetry: true };
  }
}
