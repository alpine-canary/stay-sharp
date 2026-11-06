// Accounts (M2): sign in without a password, against the local fake sign-in (every code is
// 123456) or, with BASE_URL, a deployed stage (skipped there: real e-mail codes).

import { expect, test, type Browser, type Page } from "@playwright/test";
import { answerByKeyboard, chooseSeniorAndStart, next } from "./play";

test.skip(!!process.env.BASE_URL, "needs the local fake sign-in");

function email(): string {
  return `player-${crypto.randomUUID().slice(0, 8)}@example.test`;
}

test("create an account with an e-mail code, after the age question (US2, US5)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Site" }).getByRole("link", { name: "Account" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Are you 16 or older?" })).toBeVisible();
  await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();

  const address = email();
  await page.getByLabel("E-mail address").fill(address);
  await page.getByRole("button", { name: "Send me a code" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Check your e-mail" })).toBeFocused();
  await page.getByLabel("Code").fill("123456");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "Your account" })).toBeVisible();
  await expect(page.getByText(`Signed in as ${address}.`)).toBeVisible();
});

test("a wrong code is refused in plain words (A9)", async ({ page }) => {
  await page.goto("/account");
  await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();
  await page.getByLabel("E-mail address").fill(email());
  await page.getByRole("button", { name: "Send me a code" }).click();
  await page.getByLabel("Code").fill("000000");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toHaveText("That code did not work. Check it, or ask for a new one.");
});

test("under 16: no request leaves the page (A3)", async ({ page }) => {
  await page.goto("/account");
  await expect(page.getByRole("heading", { level: 1, name: "Are you 16 or older?" })).toBeVisible();
  const stored = () => page.evaluate(() => [Object.keys(localStorage).sort(), Object.keys(sessionStorage).sort()]);
  const before = await stored();
  const requests: string[] = [];
  page.on("request", (request) => requests.push(new URL(request.url()).pathname));
  await page.getByRole("button", { name: "No" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "You can keep playing without an account" })).toBeVisible();
  expect(requests.filter((path) => path.startsWith("/cognito") || path.startsWith("/api/"))).toEqual([]);
  expect(await stored()).toEqual(before);
});

test("no sign-up prompt on a fresh browser's first screens (A1)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 2, name: /Today's set/ })).toBeVisible();
  await expect(page.getByText(/create an account|sign up/i)).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Site" }).getByRole("link", { name: "Account" })).toBeVisible();
});

// --- US1: the streak follows the player (T230, A5, A6) ----------------------------------------


function shift(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);
}

/** A browser that has played Senior dailies on these days (local progress only). */
async function browserWithDays(browser: Browser, days: string[]): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 2, name: /Today's set/ })).toBeVisible();
  await page.evaluate((played) => {
    const progress = JSON.parse(localStorage.getItem("staysharp.v1") ?? "{}");
    progress.level = "senior";
    progress.days.senior = Object.fromEntries(played.map((d) => [d, { score: 4, bonus: 0, relaxed: false }]));
    localStorage.setItem("staysharp.v1", JSON.stringify(progress));
  }, days);
  await page.reload();
  return page;
}

async function signIn(page: Page, address: string) {
  await page.goto("/account");
  await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();
  await page.getByLabel("E-mail address").fill(address);
  await page.getByRole("button", { name: "Send me a code" }).click();
  await page.getByLabel("Code").fill("123456");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your account" })).toBeVisible();
}

const streakOf = (page: Page) => page.getByRole("term").filter({ hasText: "Streak" }).locator("+ dd .big");

test("a second device joins: both show the combined streak, and today's game follows", async ({ browser, request }) => {
  test.setTimeout(60_000);
  const today = ((await (await request.get("/api/v1/today")).json()) as { date: string }).date;
  const address = email();

  const a = await browserWithDays(browser, [shift(today, -3), shift(today, -2), shift(today, -1)]);
  await expect(streakOf(a)).toHaveText("3");
  await signIn(a, address);
  await expect(a.getByText(/Your streak and progress are saved to your account/)).toBeVisible();

  const b = await browserWithDays(browser, [shift(today, -4)]);
  await expect(streakOf(b)).toHaveText("0");
  await signIn(b, address);
  await expect(b.getByText("We put this device's games together with your account's. Each day counts once.")).toBeVisible();
  await b.goto("/");
  await expect(streakOf(b)).toHaveText("4");

  // Play today on B; A picks it up when it is opened again.
  await chooseSeniorAndStart(b);
  for (const index of [0, 1, 2, 3, 4]) {
    await answerByKeyboard(b, index);
    await next(b, index === 4);
  }
  await expect(b.getByRole("heading", { name: "Your result", exact: true })).toBeVisible();
  await expect(streakOf(b)).toHaveCount(0);
  await b.waitForTimeout(2_500); // the change is sent 1.5 s after it happens

  await a.goto("/");
  await expect(streakOf(a)).toHaveText("5");
  await expect(a.getByRole("link", { name: "See today's result" })).toBeVisible();
  await a.context().close();
  await b.context().close();
});
