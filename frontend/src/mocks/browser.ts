import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export async function startMocks() {
  await setupWorker(...handlers).start({
    onUnhandledRequest: "bypass",
    quiet: true,
  });
}
