import { defineConfig, devices } from "@playwright/test";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const MOCK_PORT = 5174;
const DEMO_PORT = 8000;
const repoRoot = join(import.meta.dirname, "..");
const venvPython = join(repoRoot, ".venv", "bin", "python");

/** Where a preinstalled Chromium lives, if the sandbox has one (CI downloads its own). */
function localChromium(): string | undefined {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  if (!existsSync(root)) return undefined;
  const dir = readdirSync(root).find((d) => /^chromium-\d+$/.test(d));
  const exe = dir && join(root, dir, "chrome-linux", "chrome");
  return exe && existsSync(exe) ? exe : undefined;
}

// The demo run needs the Python venv and a built UI; without them only the mock run is set up.
const demoReady =
  process.env.E2E_DEMO !== "0" &&
  existsSync(venvPython) &&
  existsSync(join(import.meta.dirname, "dist"));

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    launchOptions: { executablePath: localChromium() },
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "mocks",
      testMatch: /.*\.mock\.spec\.ts/,
      use: { baseURL: `http://localhost:${MOCK_PORT}` },
    },
    ...(demoReady
      ? [
          {
            name: "demo",
            testMatch: /.*\.demo\.spec\.ts/,
            workers: 1,
            use: { baseURL: `http://127.0.0.1:${DEMO_PORT}` },
          },
        ]
      : []),
  ],
  webServer: [
    {
      // a production build on the mocks, so timings are real
      command: `npx vite build --mode mock --outDir .e2e-dist --logLevel error && npx vite preview --outDir .e2e-dist --port ${MOCK_PORT} --strictPort`,
      timeout: 120_000,
      url: `http://localhost:${MOCK_PORT}`,
      reuseExistingServer: !process.env.CI,
    },
    ...(demoReady
      ? [
          {
            command: `${venvPython} -m lolreview.app --demo --port ${DEMO_PORT}`,
            cwd: repoRoot,
            env: { OMP_NUM_THREADS: "1" },
            url: `http://127.0.0.1:${DEMO_PORT}/api/health`,
            reuseExistingServer: !process.env.CI,
          },
        ]
      : []),
  ],
});
