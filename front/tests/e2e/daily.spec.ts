// T057 (V1): the daily played by keyboard only; feedback after each answer; a reload resumes at
// the first unanswered question; a finished daily shows the recorded result.

import { expect, test } from "@playwright/test";
import { answerByKeyboard, chooseSeniorAndStart, expectFeedback, next } from "./play";

test("full daily by keyboard, with resume after a reload", async ({ page }) => {
  await chooseSeniorAndStart(page);

  for (const index of [0, 1]) {
    await answerByKeyboard(page, index);
    await expectFeedback(page);
    await next(page, false);
  }

  // Question 3 is open: a reload resumes there, not at question 1.
  await expect(page.getByText(/3\/5/)).toBeVisible();
  await page.reload();
  await expect(page.getByText(/3\/5/)).toBeVisible();

  for (const index of [2, 3, 4]) {
    await answerByKeyboard(page, index);
    await expectFeedback(page);
    await next(page, index === 4);
  }

  await expect(page).toHaveURL(/\/result\?play=\d{4}-\d{2}-\d{2}\.senior\.daily/);
  await expect(page.getByRole("heading", { name: "Your result" })).toBeVisible();
  const squares = page.getByRole("list", { name: /question by question/ }).getByRole("listitem");
  await expect(squares).toHaveCount(5);
  for (const square of await squares.all()) await expect(square).not.toContainText("not answered");
  const score = await page.locator(".score .big").first().textContent();
  expect(score).toMatch(/^\d(\.5)?\/5$/);

  // Home now offers the result, and /play goes back to the same recorded result.
  await page.getByRole("link", { name: "Back to today" }).click();
  await page.getByRole("link", { name: "See today's result" }).click();
  await expect(page.locator(".score .big").first()).toHaveText(score ?? "");
  await page.goto("/play");
  await expect(page).toHaveURL(/\/result\?play=/);
  await expect(page.locator(".score .big").first()).toHaveText(score ?? "");
});

test("the code box scrolls inside itself; the page never scrolls sideways", async ({ page }) => {
  await chooseSeniorAndStart(page);
  const sideways = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(sideways).toBeLessThanOrEqual(0);
});
