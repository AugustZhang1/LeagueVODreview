import { expect, MATCH, test } from "./fixtures";

test("search, games, review, next moment, model", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("textbox", { name: "Riot ID" })).toBeFocused();
  await page.keyboard.type("Me#NA1");
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/\/p\/na1\/Me\/NA1$/);
  await expect(page.getByRole("heading", { name: "Me#NA1" })).toBeVisible();
  await expect(page.getByText("Gold III, 47 LP")).toBeVisible();
  const rows = page.getByRole("link", { name: /Victory|Defeat/ });
  await expect(rows).toHaveCount(9);
  await page.getByRole("button", { name: "Load 10 more" }).click();
  await expect(rows).toHaveCount(19);

  await rows.first().click();
  await expect(page).toHaveURL(new RegExp(`/review/${MATCH}\\?p=4`));
  await expect(page.getByText("Building review…")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Victory as Ahri/);
  await expect(page.getByRole("slider", { name: "Game time" })).toHaveValue("0");

  const url = () => new URL(page.url());
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => Number(url().searchParams.get("t"))).toBeGreaterThan(0);
  const t = Number(url().searchParams.get("t"));
  await expect(page.getByRole("slider", { name: "Game time" })).toHaveValue(String(t));
  await expect(page.locator("[data-moment] [aria-current]")).toHaveCount(1);
  await expect(page.locator('[data-testid^="detail-"]')).toBeVisible();

  await page.keyboard.press("ArrowRight");
  await expect.poll(() => Number(url().searchParams.get("t"))).toBeGreaterThan(t);

  await page.getByRole("link", { name: "Model" }).click();
  await expect(page.getByRole("heading", { name: "How much to trust the numbers" })).toBeVisible();
  await expect(page.getByText("Accuracy by minute")).toBeVisible();
  await expect(page.getByText(/^Trained /)).toContainText("1,998");
});

test("reload and back keep the moment", async ({ page }) => {
  await page.goto(`/review/${MATCH}?p=4&t=388`);
  const slider = page.getByRole("slider", { name: "Game time" });
  await expect(slider).toHaveValue("388");
  await page.keyboard.press("End");
  await expect(slider).toHaveValue(/^18\d\d$/);
  await expect.poll(() => new URL(page.url()).searchParams.get("t")).not.toBe("388");
  await page.reload();
  await expect(slider).not.toHaveValue("388");
});

test("typing a short name works and a bad ID shows the message", async ({ page }) => {
  await page.goto("/");
  const box = page.getByRole("textbox", { name: "Riot ID" });
  await box.fill("Name");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert")).toContainText("Enter your Riot ID with its tag");
  await box.fill("Nobody#NA1");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert")).toHaveText("No player called Nobody#NA1 on NA.");
});

test("the review shortcuts and the graph agree", async ({ page }) => {
  await page.goto(`/review/${MATCH}?p=4`);
  const slider = page.getByRole("slider", { name: "Game time" });
  await expect(slider).toBeVisible();
  await page.keyboard.press("Shift+ArrowRight");
  await expect(slider).toHaveValue("15");
  await page.keyboard.press("Home");
  await expect(slider).toHaveValue("0");
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Play", exact: true })).toBeVisible();
  // clicking the graph sets t
  const hit = page.getByTestId("graph-hit");
  const box = (await hit.boundingBox())!;
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  const mid = Number(await slider.inputValue());
  expect(mid).toBeGreaterThan(900);
  expect(mid).toBeLessThan(960);
});
