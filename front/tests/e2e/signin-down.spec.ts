// A14 (FR-121): when the sign-in service is down, the game keeps working anonymously and the
// account page says plainly that sign-in is not available.

import { expect, test } from "@playwright/test";
import { answerByKeyboard, chooseSeniorAndStart, next } from "./play";

test.skip(!!process.env.BASE_URL, "needs the local fake sign-in");

test("sign-in service down: the game plays on, the account page says so", async ({ page }) => {
  await page.route("**/cognito", (route) => route.fulfill({ status: 503, body: "" }));
  await page.route("**/api/v1/me**", (route) => route.fulfill({ status: 503, body: "" }));

  await page.goto("/account");
  await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();
  await page.getByLabel("E-mail address").fill("down@example.test");
  await page.getByRole("button", { name: "Send me a code" }).click();
  await expect(page.getByRole("alert")).toHaveText("Sign-in is not available right now. You can keep playing. Try again later.");

  // The daily still plays and scores without an account.
  await page.goto("/");
  await chooseSeniorAndStart(page);
  for (const index of [0, 1, 2, 3, 4]) {
    await answerByKeyboard(page, index);
    await next(page, index === 4);
  }
  await expect(page.getByRole("heading", { name: "Your result", exact: true })).toBeVisible();
});

test("sign-in settings missing: the account page says sign-in is not available", async ({ page }) => {
  await page.route("**/auth.json", (route) => route.fulfill({ status: 503, body: "" }));
  await page.goto("/account");
  await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Sign-in is not available right now" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Go to today's set" })).toBeVisible();
});
