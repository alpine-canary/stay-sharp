// Accounts (M2): sign in without a password, against the local fake sign-in (every code is
// 123456) or, with BASE_URL, a deployed stage (skipped there: real e-mail codes).

import { expect, test } from "@playwright/test";

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
