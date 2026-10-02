import { test as base, expect } from "@playwright/test";

// 1x1 transparent PNG: Data Dragon is not reachable from tests, so images load from this.
const PIXEL = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

export const test = base.extend({
  page: async ({ page }, provide) => {
    await page.route("https://ddragon.leagueoflegends.com/**", (route) =>
      route.fulfill({ status: 200, contentType: "image/png", body: PIXEL }),
    );
    await provide(page);
  },
});

export { expect };

export const MATCH = "NA1_5300000001";
