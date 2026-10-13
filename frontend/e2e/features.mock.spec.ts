import type { Locator, Page } from "@playwright/test";
import { expect, MATCH, test } from "./fixtures";

// The mock game is a win that never dips under 50%, so the comeback fact can't be shown here;
// the test below checks that it stays off. Its moments and windows are the ones in review.fixture.json.

const openReview = async (page: Page, query = "") => {
  await page.goto(`/review/${MATCH}?p=4${query}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Victory as Ahri/);
};

/** The panel whose heading matches. */
const panel = (page: Page, heading: string | RegExp) =>
  page.locator("section", { has: page.getByRole("heading", { name: heading }) });

/** A row in the Moments list, found by its title. */
const row = (page: Page, title: RegExp) => page.getByRole("button", { name: title });

const scoreboard = (page: Page) => panel(page, /^Scoreboard at/);

/** The fill of a driver bar: the last span in its row. */
const barColor = (driver: Locator) =>
  driver
    .locator("span")
    .last()
    .evaluate((el) => getComputedStyle(el).backgroundColor);

test("How to read this opens and explains the grades", async ({ page }) => {
  await openReview(page);
  const body = page.getByText("The win chance on the graph is the model's estimate");
  await expect(body).toBeHidden();

  await page.getByText("How to read this").click();
  await expect(body).toBeVisible();
  await expect(page.getByText("Blunder (−10% or worse)")).toBeVisible();
  await expect(page.getByText("The model is least sure in the first 5 minutes.")).toBeVisible();
});

test("the Mistakes filter lists the mistakes and jumps to the moment", async ({ page }) => {
  // The header's "Your biggest mistakes" links were removed; the Mistakes filter replaces them.
  await openReview(page);
  const moments = panel(page, "Moments");
  await moments.getByRole("button", { name: "Mistakes", exact: true }).click();
  await expect(row(page, /Won fight 2 for 1/)).toHaveCount(0);

  await row(page, /Lost fight 1 for 3/).click();
  await expect(page.getByRole("slider", { name: "Game time" })).toHaveValue("1011");
  await expect(page.getByTestId("detail-m13")).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.get("t")).toBe("1011");
});

test("no comeback or thrown-lead fact when the curve never dipped under 20%", async ({ page }) => {
  await openReview(page);
  await expect(page.getByText("Comeback", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Thrown lead", { exact: true })).toHaveCount(0);
});

test("Lane vs Zed shows the gold and CS lead at 10:00 and 15:00", async ({ page }) => {
  await openReview(page);
  const lane = panel(page, "Lane vs Zed");
  await expect(lane.locator(".recharts-line-curve")).toBeVisible();
  await expect(lane.getByText("At 10:00: −241 gold, −7 CS")).toBeVisible();
  await expect(lane.getByText("At 15:00: +286 gold, −1 CS")).toBeVisible();
});

test("notes save as you type, Add time inserts the time, and they survive a reload", async ({
  page,
}) => {
  await openReview(page, "&t=388");
  const notes = page.getByRole("textbox", { name: "Your notes on this game" });
  await notes.click();
  await page.keyboard.type("Fed botside");
  await page.getByRole("button", { name: "Add time" }).click();
  await expect(notes).toHaveValue("Fed botside\n06:28 ");

  await notes.click();
  await page.keyboard.press("End");
  await page.keyboard.type("Lost the drag");
  await expect(notes).toHaveValue("Fed botside\n06:28 Lost the drag");

  await page.reload();
  await expect(page.getByRole("textbox", { name: "Your notes on this game" })).toHaveValue(
    "Fed botside\n06:28 Lost the drag",
  );
});

test("typing in the notes leaves the shortcuts alone", async ({ page }) => {
  await openReview(page, "&t=388");
  const slider = page.getByRole("slider", { name: "Game time" });
  const notes = page.getByRole("textbox", { name: "Your notes on this game" });
  await notes.click();
  await page.keyboard.press("Space");
  await page.keyboard.press("Shift+ArrowRight");
  await page.keyboard.press("Home");
  await expect(notes).toHaveValue(" ");
  await expect(slider).toHaveValue("388");
  await expect(page.getByRole("button", { name: "Play", exact: true })).toBeVisible();
});

test("the objective line counts down when time moves", async ({ page }) => {
  await openReview(page);
  const board = scoreboard(page);
  await expect(board.getByText("Dragon 5:00", { exact: true })).toBeVisible();
  await expect(board.getByText("Grubs 8:00", { exact: true })).toBeVisible();

  await page.keyboard.press("Shift+ArrowRight");
  await expect(page.getByRole("slider", { name: "Game time" })).toHaveValue("15");
  await expect(board.getByText("Dragon 4:45", { exact: true })).toBeVisible();
  await expect(board.getByText("Grubs 7:45", { exact: true })).toBeVisible();
});

test("team headers show grubs, herald and baron counts once taken", async ({ page }) => {
  await openReview(page);
  const board = scoreboard(page);
  await expect(board.getByText(/^Grubs \d+$/)).toHaveCount(0);

  await openReview(page, "&t=600");
  await expect(scoreboard(page).getByText("Grubs 3", { exact: true })).toBeVisible();

  await openReview(page, "&t=1050");
  await expect(scoreboard(page).getByText("Herald 1", { exact: true })).toBeVisible();

  await openReview(page, "&t=1865");
  await expect(scoreboard(page).getByText("Baron 1", { exact: true })).toBeVisible();
});

test("the Missed filter shows only the missed windows", async ({ page }) => {
  await openReview(page);
  const moments = panel(page, "Moments");
  await expect(moments.getByRole("img", { name: "Used window" })).toHaveCount(1);
  await expect(moments.getByRole("img", { name: "Missed window" })).toHaveCount(1);

  await moments.getByRole("button", { name: "Missed", exact: true }).click();
  await expect(moments.getByRole("img", { name: "Used window" })).toHaveCount(0);
  await expect(moments.getByRole("img", { name: "Missed window" })).toHaveCount(1);
  await expect(row(page, /Won fight 2 for 1/)).toHaveCount(0);

  await moments.getByRole("button", { name: "All", exact: true }).click();
  await expect(moments.getByRole("img", { name: "Used window" })).toHaveCount(1);
});

test("a missed window lists what happened instead", async ({ page }) => {
  await openReview(page);
  await row(page, /4 enemies dead, Baron up/).click();
  await expect(page.getByRole("slider", { name: "Game time" })).toHaveValue("1320");

  const detail = page.getByTestId("detail-w2");
  await expect(detail.getByRole("heading", { name: "What happened instead" })).toBeVisible();
  // no moment ends inside the window, so the fallback sentence shows
  await expect(
    detail.getByText("Your team didn't take an objective or tower in time."),
  ).toBeVisible();
});

test("a used window says what the team took", async ({ page }) => {
  await openReview(page);
  await row(page, /Enemy Vi dead, Dragon up/).click();

  const detail = page.getByTestId("detail-w1");
  await expect(detail.getByText("Your team took: Dragon")).toBeVisible();
  await expect(detail.getByRole("heading", { name: "What happened instead" })).toHaveCount(0);
});

test("a graded moment shows why it swung, with at most three drivers", async ({ page }) => {
  await openReview(page);
  const why = page.getByRole("heading", { name: "Why", exact: true });
  await row(page, /Won fight 2 for 1/).click();
  await expect(why).toBeVisible();
  const drivers = page.getByTestId("driver-row");
  await expect(drivers).toHaveCount(3);
  await expect(drivers.nth(0)).toContainText("Your dragons");
  await expect(drivers.nth(2)).toContainText("Gold lead");
  const ally = await barColor(drivers.nth(0));

  // a moment that cost me: its drivers point the other way and use the enemy colour
  await row(page, /Lost fight 1 for 3/).click();
  await expect(why).toBeVisible();
  const enemy = await barColor(page.getByTestId("driver-row").nth(0));
  expect(enemy).not.toBe(ally);

  // a moment with no drivers has no Why block
  await row(page, /Took 2 top plates/).click();
  await expect(why).toHaveCount(0);
});

test("a moment before 5:00 carries the early-game note", async ({ page }) => {
  const note = "Early game: the model is least sure in the first 5 minutes.";
  await openReview(page);
  await row(page, /killed Darius/).click();
  await expect(page.getByText(note)).toBeVisible();

  await row(page, /Won fight 2 for 1/).click();
  await expect(page.getByText(note)).toHaveCount(0);
});

test("the games page shows your patterns across reviewed games", async ({ page }) => {
  await page.goto("/p/na1/Me/NA1");
  await expect(page.getByRole("link", { name: /Victory/ }).first()).toBeVisible();
  // always open now, not a collapsed <details>
  await expect(page.getByRole("heading", { name: "Your patterns", exact: true })).toBeVisible();
  await expect(page.getByText("from 5 reviewed games")).toBeVisible();

  await expect(
    page.getByRole("heading", { name: "When you lose win chance", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Where", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Why", exact: true })).toBeVisible();
});
