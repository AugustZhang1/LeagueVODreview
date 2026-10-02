import { expect, MATCH, test } from "./fixtures";

test("the review renders within 300 ms of its data arriving", async ({ page }) => {
  await page.addInitScript(() => {
    const w = window as unknown as { __dataAt?: number; __shownAt?: number };
    const realFetch = window.fetch.bind(window);
    window.fetch = async (...args: Parameters<typeof fetch>) => {
      const res = await realFetch(...args);
      const url = String(args[0] instanceof Request ? args[0].url : args[0]);
      if (url.includes("/api/review/")) {
        await res.clone().json();
        w.__dataAt = performance.now();
      }
      return res;
    };
    new MutationObserver((_, obs) => {
      if (document.querySelector("input[type=range]")) {
        w.__shownAt = performance.now();
        obs.disconnect();
      }
    }).observe(document, { childList: true, subtree: true });
  });
  await page.goto(`/review/${MATCH}?p=4`);
  await expect(page.getByRole("slider")).toBeVisible();
  const { dataAt, shownAt } = await page.evaluate(() => {
    const w = window as unknown as { __dataAt: number; __shownAt: number };
    return { dataAt: w.__dataAt, shownAt: w.__shownAt };
  });
  expect(shownAt - dataAt).toBeGreaterThan(0);
  console.log(`first render ${Math.round(shownAt - dataAt)} ms`);
  expect(shownAt - dataAt).toBeLessThan(300);
});

test("scrubbing end to end keeps up", async ({ page }) => {
  await page.goto(`/review/${MATCH}?p=4`);
  const slider = page.getByRole("slider", { name: "Game time" });
  await expect(slider).toBeVisible();
  // 120 input events across every snapshot, each followed by a frame, as a drag would send
  const ms = await slider.evaluate(async (el: HTMLInputElement) => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    const start = performance.now();
    for (let i = 0; i <= 120; i++) {
      set.call(el, String(Math.round((Number(el.max) * i) / 120)));
      el.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise((done) => setTimeout(done, 0));
    }
    return performance.now() - start;
  });
  await expect(slider).toHaveValue(String((await slider.getAttribute("max")) ?? ""));
  console.log(`scrub: ${Math.round(ms / 121)} ms per tick`);
  expect(ms / 121).toBeLessThan(16);
});
