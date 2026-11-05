// T112 (Story 5): practice past questions from the home screen, with the same feedback as the
// daily; practice never changes the streak.

import { expect, test } from "@playwright/test";

test("practise two past questions, then the streak is unchanged", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("radio", { name: "Senior" }).check();
  const streak = await page.locator(".stats > div").first().textContent();
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
  await expect(page.locator(".stats > div").first()).toHaveText(streak ?? "");
});
