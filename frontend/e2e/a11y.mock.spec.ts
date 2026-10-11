import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, MATCH, test } from "./fixtures";

const serious = async (page: Page) => {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`);
};

test.describe("axe finds nothing serious", () => {
  test("search", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("textbox", { name: "Riot ID" })).toBeVisible();
    expect(await serious(page)).toEqual([]);
  });

  test("search with an error", async ({ page }) => {
    await page.goto("/?mock=key_expired");
    await page.getByRole("textbox", { name: "Riot ID" }).fill("x");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("alert").first()).toBeVisible();
    expect(await serious(page)).toEqual([]);
  });

  test("games", async ({ page }) => {
    await page.goto("/p/na1/Me/NA1");
    await expect(page.getByRole("link", { name: /Victory/ }).first()).toBeVisible();
    expect(await serious(page)).toEqual([]);
  });

  test("review", async ({ page }) => {
    await page.goto(`/review/${MATCH}?p=4`);
    await expect(page.getByRole("slider")).toBeVisible();
    expect(await serious(page)).toEqual([]);
    await page.keyboard.press("ArrowRight");
    await expect(page.locator('[data-testid^="detail-"]')).toBeVisible();
    expect(await serious(page)).toEqual([]);
  });

  test("model", async ({ page }) => {
    await page.goto("/model");
    await expect(page.getByText("Accuracy by minute")).toBeVisible();
    expect(await serious(page)).toEqual([]);
    for (const summary of await page.locator("summary").all()) await summary.click();
    expect(await serious(page)).toEqual([]);
  });
});

/** Presses Tab until `stop` matches the focused element, returning what took focus on the way. */
async function tabUntil(page: Page, stop: RegExp, max = 60) {
  const seen: string[] = [];
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement;
      const cs = getComputedStyle(el);
      const name =
        el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 30) ?? el.tagName;
      return { name, ring: cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) >= 2 };
    });
    expect(info.ring, `focus ring on "${info.name}"`).toBe(true);
    seen.push(info.name);
    if (stop.test(info.name)) break;
  }
  return seen;
}

test.describe("keyboard only", () => {
  test("search: input, server, button, then Enter finds games", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("textbox", { name: "Riot ID" })).toBeFocused();
    await page.keyboard.type("Me#NA1");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("combobox", { name: "Server" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Find games" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/p\/na1\/Me\/NA1/);
  });

  test("games: refresh, then rows in order, Enter opens the review", async ({ page }) => {
    await page.goto("/p/na1/Me/NA1");
    await expect(page.getByRole("link", { name: /Victory/ }).first()).toBeVisible();
    const seen = await tabUntil(page, /Victory/);
    expect(seen.slice(0, 4)).toEqual(["LeagueVODreview", "Search", "Model", "Refresh"]);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(new RegExp(`/review/${MATCH}`));
  });

  test("review: controls in order, shortcuts, Escape closes a tooltip", async ({ page }) => {
    await page.goto(`/review/${MATCH}?p=4`);
    const slider = page.getByRole("slider", { name: "Game time" });
    await expect(slider).toBeVisible();
    const seen = await tabUntil(page, /^Open in replay$/);
    expect(seen).toEqual([
      "LeagueVODreview",
      "Search",
      "Model",
      "16:50−9%",
      "16:50Lost fight 1 for 3, then ",
      "How to read this",
      "Games",
      "Previous moment",
      "Next moment",
      "Play",
      "Game time",
      "Open in replay",
    ]);
    // a focused disabled-looking button still explains itself, and Escape closes it
    await expect(page.getByRole("tooltip")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("tooltip")).toHaveCount(0);

    // rows of the moments list are reachable and Enter selects one (past Graded, Missed, Mine)
    await tabUntil(page, /^All$/);
    for (let i = 0; i < 4; i++) await page.keyboard.press("Tab");
    await page.keyboard.press("Enter");
    await expect(page.locator("[data-moment] [aria-current]")).toHaveCount(1);
    await expect(page.locator('[data-testid^="detail-"]')).toBeVisible();
  });

  test("model: every Numbers table opens with Enter", async ({ page }) => {
    await page.goto("/model");
    await expect(page.getByText("Accuracy by minute")).toBeVisible();
    await expect(page.locator("details[open]")).toHaveCount(0);
    await tabUntil(page, /^Numbers$/);
    await page.keyboard.press("Enter");
    await expect(page.locator("details[open]")).toHaveCount(1);
  });
});
