// Shared steps: play the daily by keyboard, without knowing the answers.

import { expect, type Page } from "@playwright/test";

export async function chooseSeniorAndStart(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 2, name: /Today's set #\d+/ })).toBeVisible();
  await page.getByRole("radio", { name: "Senior" }).check();
  await page.getByRole("link", { name: "Play today's set" }).click();
  await expect(page.getByText(/1\/5/)).toBeVisible();
}

/** Pick a line if the question has code lines, pick the first choice, submit. Keyboard only. */
export async function answerByKeyboard(page: Page, index: number): Promise<void> {
  await expect(page.getByText(new RegExp(`${index + 1}/5`))).toBeVisible();
  const title = page.getByRole("heading", { level: 1 });
  await expect(title).toBeFocused();
  const listbox = page.getByRole("listbox");
  if (await listbox.count()) {
    await page.keyboard.press("Tab");
    await expect(listbox).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
  } else if (await page.getByRole("region", { name: /Code/ }).count()) {
    await page.keyboard.press("Tab"); // the scrollable code box
  }
  await page.keyboard.press("Tab");
  await page.keyboard.press("Space");
  await expect(page.getByRole("radio").first()).toBeChecked();
  await page.keyboard.press("Enter");
}

export async function expectFeedback(page: Page): Promise<void> {
  const feedback = page.getByRole("status").filter({ hasText: /Right|Half right|Not this time/ });
  await expect(feedback).toBeVisible();
  // An explanation follows the verdict.
  await expect(feedback.locator("p").nth(1)).not.toBeEmpty();
}

export async function next(page: Page, last: boolean): Promise<void> {
  const button = page.getByRole("button", { name: last ? "See my result" : "Next question" });
  await button.focus();
  await page.keyboard.press("Enter");
}
