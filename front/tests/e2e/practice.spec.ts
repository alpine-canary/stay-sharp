// T112 (Story 5): practice past questions from the home screen, with the same feedback as the
// daily; practice never changes the streak.

import { expect, test } from "@playwright/test";

test("practise two past questions, then the streak is unchanged", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("radio", { name: "Senior" }).check();
  // A new browser has no daily yet: the home shows "How it plays" instead of a streak.
  const noStreak = page.getByRole("heading", { name: "Five questions, five minutes" });
  await expect(noStreak).toBeVisible();
  await page.getByRole("link", { name: "Practise past questions" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Practise past questions" })).toBeVisible();

  for (const round of [1, 2]) {
    const title = page.getByRole("heading", { level: 2 }).first();
    await expect(title).toBeFocused();
    const lines = page.getByRole("listbox");
    if (await lines.count()) {
      await lines.focus();
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("Enter");
    }
    await page.locator("form").getByRole("radio").last().check();
    await page.getByRole("button", { name: "Check" }).click();
    const feedback = page.getByRole("status").filter({ hasText: /Right|Half right|Not this time/ });
    await expect(feedback).toBeVisible();
    await expect(page.getByText(`${round} answered in this session.`)).toBeVisible();
    await page.getByRole("button", { name: "Next question" }).click();
  }

  await page.getByRole("link", { name: "Stay Sharp, home" }).click();
  // Practice never starts a streak.
  await expect(noStreak).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your progress" })).toHaveCount(0);
});
