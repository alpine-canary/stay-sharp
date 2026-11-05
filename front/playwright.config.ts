import { defineConfig, devices } from "@playwright/test";
import { CLOCK_FILE } from "./tests/e2e/clock";

// Against a deployed stage: BASE_URL=https://... (no local servers, no clock test).
// Locally: starts the API on DynamoDB Local (`make ddb-start`, seeded with
// `python -m staysharp.tools.seed --fixtures --create-table`) and Vite, or reuses running ones.
const remote = process.env.BASE_URL;
const baseURL = remote ?? "http://localhost:5173";

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: { baseURL, trace: "off" },
  projects: [
    { name: "mobile", use: { ...devices["Pixel 7"] }, testIgnore: /midnight/ },
    { name: "desktop", use: { ...devices["Desktop Chrome"] }, testIgnore: /midnight/ },
    // Moves the local server clock, so it runs alone, after the others, and never remotely.
    ...(remote
      ? []
      : [{ name: "clock", use: { ...devices["Desktop Chrome"] }, testMatch: /midnight/, dependencies: ["mobile", "desktop"] }]),
  ],
  ...(remote
    ? {}
    : {
        webServer: [
          {
            command: "uv run --directory ../api python -m staysharp.local",
            url: "http://127.0.0.1:3001/api/v1/health",
            reuseExistingServer: !process.env.CI,
            env: { STAYSHARP_CLOCK_FILE: CLOCK_FILE },
          },
          { command: "corepack pnpm dev --strictPort", url: baseURL, reuseExistingServer: !process.env.CI },
        ],
      }),
});
