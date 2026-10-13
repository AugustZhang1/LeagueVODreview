import { expect, MATCH, test } from "./fixtures";

const search = async (page: import("@playwright/test").Page, id = "Me#NA1") => {
  await page.getByRole("textbox", { name: "Riot ID" }).fill(id);
  await page.keyboard.press("Enter");
};

test.describe("key expired", () => {
  test("the banner shows on every page and the search says why", async ({ page }) => {
    await page.goto("/?mock=key_expired");
    const banner = page.getByRole("alert").filter({ hasText: "Riot API key expired" });
    await expect(banner).toContainText("Paste a new one after RIOT_API_KEY= in .env");
    // a slim amber banner: amber text on a faint tint, with no bar down its left edge
    await expect(banner.locator("p")).toHaveCSS("color", "rgb(236, 197, 132)");
    await expect(banner).toHaveCSS("border-left-width", "0px");
    await search(page);
    await expect(page.getByRole("alert").last()).toContainText("Riot API key expired");
    await page.getByRole("link", { name: "Model", exact: true }).click();
    await expect(banner).toBeVisible();
  });

  test("the games page and the review show it too", async ({ page }) => {
    await page.goto("/p/na1/Me/NA1?mock=key_expired");
    await expect(page.getByText("Riot API key expired. Paste")).toHaveCount(2);
    await page.goto(`/review/${MATCH}?p=4&mock=key_expired`);
    await expect(page.getByText("Riot API key expired. Paste")).toHaveCount(2);
  });
});

test("rate limited waits and says so", async ({ page }) => {
  await page.goto("/p/na1/Me/NA1?mock=rate_limited");
  await expect(page.getByRole("alert")).toHaveText("Riot's rate limit is full, retrying in 8 s.");
  await page.goto("/?mock=rate_limited");
  await search(page);
  await expect(page.getByRole("alert")).toHaveText("Riot's rate limit is full, retrying in 8 s.");
});

test("Riot unavailable offers Retry", async ({ page }) => {
  await page.goto("/p/na1/Me/NA1?mock=unavailable");
  await expect(page.getByRole("alert")).toContainText("Riot's API isn't responding.", {
    timeout: 15_000,
  });
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  await page.goto(`/review/${MATCH}?p=4&mock=unavailable`);
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible({ timeout: 15_000 });
});

test("an unknown player", async ({ page }) => {
  await page.goto("/");
  await search(page, "Nobody#NA1");
  await expect(page.getByRole("alert")).toHaveText("No player called Nobody#NA1 on NA.");
  await page.goto("/p/na1/Nobody/NA1");
  await expect(page.getByRole("alert")).toHaveText("No player called Nobody#NA1 on NA.");
  await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
});

test("anything else says something went wrong", async ({ page }) => {
  await page.goto("/p/na1/Me/NA1?mock=server_error");
  await expect(page.getByRole("alert")).toHaveText(/Something went wrong\./, { timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("unsupported queue", async ({ page }) => {
  await page.goto(`/review/${MATCH}?p=4&mock=unsupported_queue`);
  await expect(page.getByRole("alert")).toHaveText("Only ranked solo/duo games can be reviewed.");
});

test("empty states", async ({ page }) => {
  await page.goto("/p/na1/Me/NA1?mock=empty");
  await expect(page.getByText("No ranked solo games found.")).toBeVisible();
  await page.goto(`/review/${MATCH}?p=4&mock=empty`);
  await expect(page.getByRole("alert")).toHaveText("Match not found.");
  await page.goto("/model?mock=empty");
  await expect(page.getByText(/No trained model yet/)).toBeVisible();
});

test("loading states keep their size", async ({ page }) => {
  await page.goto("/p/na1/Me/NA1");
  await expect(page.getByLabel("Loading games")).toBeVisible();
  await page.goto(`/review/${MATCH}?p=4`);
  await expect(page.getByText("Building review…")).toBeVisible();
  const skeleton = await page.evaluate(() => document.documentElement.scrollHeight);
  await expect(page.getByRole("slider")).toBeVisible();
  const loaded = await page.evaluate(() => document.documentElement.scrollHeight);
  expect(Math.abs(skeleton - loaded)).toBeLessThanOrEqual(24);
});

test("Open replay: disabled with the reason, enabled when the replay is open", async ({ page }) => {
  await page.goto(`/review/${MATCH}?p=4&t=300`);
  const open = page.getByRole("button", { name: "Open in replay" });
  await expect(open).toBeDisabled();
  await open.hover();
  await expect(page.getByRole("tooltip")).toHaveText(
    "Open this game's replay in the League client",
  );

  await page.goto(`/review/${MATCH}?p=4&t=300&mock=replay_open`);
  await expect(open).toBeEnabled();
  const seek = page.waitForRequest(
    (r) => r.url().endsWith("/api/replay/seek") && r.method() === "POST",
  );
  await page.keyboard.press("o");
  expect((await seek).postDataJSON()).toEqual({ match_id: MATCH, t: 300 });
  const again = page.waitForRequest((r) => r.url().endsWith("/api/replay/seek"));
  await open.click();
  expect((await again).postDataJSON()).toMatchObject({ t: 300 });
});
