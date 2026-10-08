import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export async function startMocks() {
  await setupWorker(...handlers).start({
    serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
    onUnhandledRequest: "bypass",
    quiet: true,
  });
}
