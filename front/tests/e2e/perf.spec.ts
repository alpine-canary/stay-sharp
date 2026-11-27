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

// The emulated latency adds to the real one, so a runner far from the stage (GitHub's are in the
// US, the stage in Zurich) would measure a phone much slower than Slow 4G. Measure the runner's
// own round trip to the API (best of five, after a warm-up) and emulate only what is missing.
async function realRttMs(baseUrl: string): Promise<number> {
  const url = new URL("/api/health", baseUrl).toString();
  await fetch(url);
  let best = Number.POSITIVE_INFINITY;
  for (let i = 0; i < 5; i += 1) {
    const t = performance.now();
    await fetch(url);
    best = Math.min(best, performance.now() - t);
  }
  return best;
}
const BUDGET_MS = 2000;

test.skip(!process.env.BASE_URL, "measured on a deployed stage only (BASE_URL)");

test("first question interactive under 2 s on a throttled phone", async ({ browser, browserName }) => {
  test.skip(browserName !== "chromium", "throttling uses the Chrome DevTools Protocol");

  // A new player who has chosen a level, then a cold browser cache for the measured load.
  const setup = await browser.newContext();
  const home = await setup.newPage();
  await home.goto("/");
  await home.getByRole("radio", { name: "Senior" }).check();
  // Senior is preselected: wait until the app has saved it (the Play button shows then).
  await expect(home.getByRole("link", { name: "Play today's set" })).toBeVisible();
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
  const rtt = await realRttMs(process.env.BASE_URL ?? "");
  const latency = Math.max(0, SLOW_4G.latency - Math.round(rtt));
  console.log(`runner round trip ${Math.round(rtt)} ms, emulated latency ${latency} ms`);
  await cdp.send("Network.emulateNetworkConditions", { ...SLOW_4G, latency });
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
