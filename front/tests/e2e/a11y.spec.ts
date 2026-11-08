// T114 (V10, FR-033, SC-006): axe finds no WCAG 2.2 AA violation on any view, in light and dark;
// relaxed mode can be reached by keyboard before and during a play.

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { answerByKeyboard, chooseSeniorAndStart, next } from "./play";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function noViolations(page: Page, where: string): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const found = results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  expect(found, where).toEqual([]);
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`a11y ${scheme}`, () => {
    test.use({ colorScheme: scheme });

    test("home, play, feedback, result, challenge and practice", async ({ page, browser }) => {
      // The longest test: a full daily, a challenge and practice, with axe on each view.
      test.setTimeout(60_000);
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 2, name: /Today's set/ })).toBeVisible();
      await noViolations(page, "home before a level");

      await chooseSeniorAndStart(page);
      await noViolations(page, "first question");
      await answerByKeyboard(page, 0);
      await expect(page.getByRole("status").filter({ hasText: /Right|Half right|Not this time/ })).toBeVisible();
      await noViolations(page, "feedback");
      await next(page, false);
      for (const index of [1, 2, 3, 4]) {
        await answerByKeyboard(page, index);
        await next(page, index === 4);
      }
      await expect(page.getByRole("heading", { name: "Your result", exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Create a challenge link" }).click();
      await expect(page.locator(".link-text")).toBeVisible();
      await noViolations(page, "result with share card and challenge link");

      const path = new URL((await page.locator(".link-text").textContent()) ?? "").pathname;
      const colleague = await (await browser.newContext({ colorScheme: scheme })).newPage();
      await colleague.goto(path);
      await expect(colleague.getByRole("button", { name: "Play this set" })).toBeVisible();
      await noViolations(colleague, "challenge before playing");
      await colleague.context().close();
      await page.goto(path);
      await expect(page.getByRole("heading", { name: "Your challenge" })).toBeVisible();
      await noViolations(page, "challenge, owner");

      await page.goto("/");
      await expect(page.getByRole("heading", { name: "Your progress" })).toBeVisible();
      await noViolations(page, "home with progress");

      await page.goto("/practice");
      await expect(page.getByRole("button", { name: "Check" })).toBeVisible();
      await noViolations(page, "practice");
    });

    test("every account screen (T245, FR-118)", async ({ page }) => {
      test.skip(!!process.env.BASE_URL, "needs the local fake sign-in");
      test.setTimeout(60_000);
      await page.goto("/account");
      await expect(page.getByRole("heading", { level: 1, name: "Are you 16 or older?" })).toBeVisible();
      await noViolations(page, "age question");
      await page.getByRole("button", { name: "No, I am under 16" }).click();
      await expect(page.getByRole("heading", { level: 1, name: "You can keep playing without an account" })).toBeVisible();
      await noViolations(page, "under 16");

      await page.goto("/account");
      await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();
      await expect(page.getByLabel("E-mail address")).toBeVisible();
      await noViolations(page, "e-mail");
      await page.getByRole("button", { name: "Send me a code" }).click();
      await expect(page.getByRole("alert")).toBeVisible();
      await noViolations(page, "e-mail error");
      await page.getByLabel("E-mail address").fill(`a11y-${crypto.randomUUID().slice(0, 8)}@example.test`);
      await page.getByRole("button", { name: "Send me a code" }).click();
      await expect(page.getByRole("heading", { level: 1, name: "Check your e-mail" })).toBeFocused();
      await noViolations(page, "code");

      // Accessible authentication (WCAG 3.3.8): no CAPTCHA, no puzzle, and the code can be
      // pasted or filled in by the phone (one-time-code), never retyped from memory.
      const code = page.getByLabel("Code");
      await expect(code).toHaveAttribute("autocomplete", "one-time-code");
      expect(await page.locator("iframe, [class*=captcha i], [id*=captcha i]").count()).toBe(0);
      await code.fill("000000");
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await expect(page.getByRole("alert")).toBeVisible();
      await noViolations(page, "wrong code");
      await code.fill("");
      await code.focus();
      await page.keyboard.insertText("123 456"); // as pasted, with a space
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await expect(page.getByRole("heading", { level: 1, name: "Your account" })).toBeVisible();
      await noViolations(page, "signed in");

      await page.getByRole("button", { name: "Delete my account" }).click();
      await expect(page.getByRole("heading", { name: "Delete your account for good?" })).toBeFocused();
      await noViolations(page, "delete confirmation");
      await page.getByRole("button", { name: "Keep my account" }).click();

      await page.getByRole("button", { name: "Sign out" }).click();
      await expect(page.getByRole("heading", { level: 1, name: "You are signed out" })).toBeFocused();
      await noViolations(page, "signed out");
    });

    test("privacy, bad challenge link and not found", async ({ page }) => {
      for (const [path, heading] of [
        ["/privacy", "What we keep, and where"],
        ["/c/ABCDEFGHJKMN", "This challenge link does not work"],
        ["/nope", "Page not found"],
      ] as const) {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
        await noViolations(page, path);
      }
    });
  });
}

test("relaxed can be reached by keyboard before and during a play", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("radio", { name: "Senior" }).check();
  const before = page.getByRole("checkbox", { name: /Relaxed mode/ });
  await before.focus();
  await expect(before).toBeFocused();

  await chooseSeniorAndStart(page);
  const during = page.getByRole("button", { name: "Switch to relaxed mode" });
  for (let i = 0; i < 40 && !(await during.evaluate((el) => el === document.activeElement)); i++) {
    await page.keyboard.press("Tab");
  }
  await expect(during).toBeFocused();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Switch to relaxed", exact: true }).press("Enter");
  await expect(page.getByText("Relaxed · no timer")).toBeVisible();
});
