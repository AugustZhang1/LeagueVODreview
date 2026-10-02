import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { ErrorBox } from "./ErrorBox";

describe("ErrorBox", () => {
  it("names the player for riot_id_not_found and offers no retry", () => {
    render(
      <ErrorBox
        error={new ApiError("riot_id_not_found", "x", 404)}
        onRetry={() => {}}
        context={{ name: "Name", tag: "TAG", platform: "na" }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("No player called Name#TAG on NA.");
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("shows the retry time for rate limits, with no button", () => {
    render(<ErrorBox error={new ApiError("rate_limited", "x", 429, 8)} onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Riot's rate limit is full, retrying in 8 s.",
    );
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("retries when the Retry button is pressed", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const onRetry = vi.fn();
    render(<ErrorBox error={new ApiError("riot_unavailable", "x", 502)} onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
