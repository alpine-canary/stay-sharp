// T115 (V17, SC-007): on a mid-range phone over Slow 4G, the first question is interactive in
// under 2 s, from a cold page load of /play to the first answer choice being usable. Runs against
// a deployed stage only (BASE_URL): the Vite dev server serves unbundled modules, which says
// nothing about the real site. A cold Lambda is included when the stage has been idle.

import { expect, test } from "@playwright/test";

// Lighthouse's mobile defaults (Moto G Power class): 4x CPU slowdown, 150 ms RTT, 1.6 Mbps down,
// 750 kbps up.
const SLOW_4G = {
  offline: false,
  latency: 150,
  downloadThroughput: (1.6 * 1024 * 1024) / 8,
  uploadThroughput: (750 * 1024) / 8,
};
const CPU_SLOWDOWN = 4;
const BUDGET_MS = 2000;

test.skip(!process.env.BASE_URL, "measured on a deployed stage only (BASE_URL)");

test("first question interactive under 2 s on a throttled phone", async ({ browser, browserName }) => {
  test.skip(browserName !== "chromium", "throttling uses the Chrome DevTools Protocol");

  // A new player who has chosen a level, then a cold browser cache for the measured load.
  const setup = await browser.newContext();
  const home = await setup.newPage();
  await home.goto("/");
  await home.getByRole("radio", { name: "Senior" }).check();
  const storageState = await setup.storageState();
  await setup.close();

  const context = await browser.newContext({
    storageState,
    viewport: { width: 412, height: 823 },
    deviceScaleFactor: 1.75,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", SLOW_4G);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU_SLOWDOWN });

  const started = Date.now();
  await page.goto("/play");
  await expect(page.getByRole("radio").first()).toBeEnabled({ timeout: 15_000 });
  const elapsed = Date.now() - started;
  test.info().annotations.push({ type: "first question interactive (ms)", description: String(elapsed) });
  console.log(`first question interactive: ${elapsed} ms`);
  expect(elapsed).toBeLessThan(BUDGET_MS);
  await context.close();
});
