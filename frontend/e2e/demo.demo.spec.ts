import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures";

// Runs against `python -m lolreview.app --demo` serving the built UI (see playwright.config.ts).
test("search Me#NA1, open every game, then the model page", async ({ page }) => {
  const problems: string[] = [];
  page.on("response", (r) => {
    // the stub model has no metrics, so /api/model is a 404 by design
    if (r.status() >= 400 && !r.url().endsWith("/api/model"))
      problems.push(`${r.status()} ${r.url()}`);
  });
  page.on("pageerror", (e) => problems.push(e.message));

  await page.goto("/");
  await expect(page.getByRole("textbox", { name: "Riot ID" })).toBeFocused();
  await page.keyboard.type("Me#NA1");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/p\/na1\/Me\/NA1$/);
  await expect(page.getByRole("heading", { name: "Me#NA1" })).toBeVisible();
  await expect(page.getByText("Gold III, 47 LP")).toBeVisible();

  const links = page.getByRole("link", { name: /Victory|Defeat/ });
  await expect(links).toHaveCount(3);
  await expect(page.getByText("Remake")).toBeVisible();
  const hrefs = await links.evaluateAll((els) => els.map((e) => e.getAttribute("href")!));

  for (const href of hrefs) {
    await page.goto(href);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/(Victory|Defeat) as /);
    const slider = page.getByRole("slider", { name: "Game time" });
    await expect(slider).toBeVisible();
    await expect(page.getByText(/^Scoreboard at 00:00$/)).toBeVisible();
    await expect(page.getByRole("img", { name: "Minimap" })).toBeVisible();
    // the lane chart and notes sit below the fold by design; the panels must fit
    const panels = await page.locator('[class*="panels"]').boundingBox();
    expect(panels!.y + panels!.height).toBeLessThanOrEqual(900);

    await page.keyboard.press("ArrowRight");
    await expect(page.locator('[data-testid^="detail-"]')).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.get("t")).not.toBeNull();
    await page.keyboard.press("End");
    await expect(page.getByText(/^Win chance/)).toContainText(/100%|0%/);

    const open = page.getByRole("button", { name: "Open in replay" });
    await expect(open).toBeDisabled();
    const { violations } = await new AxeBuilder({ page }).analyze();
    expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

    // the way back lands on the same player's games
    await page.getByRole("link", { name: "Games" }).click();
    await expect(page).toHaveURL(/\/p\/na1\/Me\/NA1$/);
  }

  await page.getByRole("link", { name: "Model", exact: true }).click();
  await expect(page.getByText(/No trained model yet/)).toBeVisible();
  await expect(page.getByText("Placeholder model")).toBeVisible();
  expect(problems).toEqual([]);
});

test("an unknown Riot ID says so", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Riot ID" }).fill("Nobody#NA1");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert")).toHaveText(/^No player called Nobody#NA1 on NA\./);
});
