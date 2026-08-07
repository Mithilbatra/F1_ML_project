// @ts-check
const { defineConfig, devices } = require("@playwright/test");

const PORT = process.env.PITWALL_PORT || "8199";
const BASE = `http://127.0.0.1:${PORT}`;

/**
 * Frontend smoke tests run against the real app (`f1ml serve`) so they exercise
 * the same JS + API the users get. The first boot self-builds features + models,
 * hence the generous webServer timeout.
 */
module.exports = defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  timeout: 60_000,
  use: {
    baseURL: BASE,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: `uv run f1ml serve --host 127.0.0.1 --port ${PORT}`,
    url: `${BASE}/healthz`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
