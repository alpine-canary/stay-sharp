// Screenshots of every view, for design reviews (before/after). Runs only with SHOTS=<label>;
// files go to ../var/shots/<label>/<project>-<scheme>-<view>.png (git-ignored).

import { expect, test, type Page } from "@playwright/test";
import { answerByKeyboard, chooseSeniorAndStart, next } from "./play";

const label = process.env.SHOTS;
test.skip(!label, "set SHOTS=<label> to take screenshots");

for (const scheme of ["light", "dark"] as const) {
  test(`views in ${scheme}`, async ({ page, browser }, info) => {
    test.setTimeout(90_000);
    // Reduced motion: every element in its final state, not half-way through an entrance.
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    // The review widths: 390 px phone, 1440 px desktop.
    await page.setViewportSize(info.project.name === "mobile" ? { width: 390, height: 844 } : { width: 1440, height: 900 });
    const shot = async (p: Page, view: string) =>
      p.screenshot({ path: `../var/shots/${label}/${info.project.name}-${scheme}-${view}.png`, fullPage: true });

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await shot(page, "1-home");

    await chooseSeniorAndStart(page);
    await shot(page, "2-question");
    await answerByKeyboard(page, 0);
    await expect(page.getByRole("status").filter({ hasText: /Right|Half right|Not this time/ })).toBeVisible();
    await shot(page, "3-feedback");
    await next(page, false);
    for (const index of [1, 2, 3, 4]) {
      await answerByKeyboard(page, index);
      await next(page, index === 4);
    }
    await expect(page.getByRole("heading", { name: "Your result", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Create a challenge link" }).click();
    await expect(page.locator(".link-text")).toBeVisible();
    await shot(page, "4-result");

    const path = new URL((await page.locator(".link-text").textContent()) ?? "").pathname;
    const colleague = await (await browser.newContext({ colorScheme: scheme, reducedMotion: "reduce", viewport: page.viewportSize() })).newPage();
    await colleague.goto(path);
    await expect(colleague.getByRole("button", { name: "Play this set" })).toBeVisible();
    await shot(colleague, "5-challenge-invite");
    await colleague.context().close();

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Your progress" })).toBeVisible();
    await shot(page, "6-home-progress");

    await page.goto("/practice");
    await expect(page.getByRole("button", { name: "Check" })).toBeVisible();
    await shot(page, "7-practice");

    // Accounts (M2), with the local fake sign-in.
    if (!process.env.BASE_URL) {
      await page.goto("/account");
      await expect(page.getByRole("heading", { name: "Are you 16 or older?" })).toBeVisible();
      await shot(page, "8-account-age");
      await page.getByRole("button", { name: "Yes, I am 16 or older" }).click();
      await page.getByLabel("E-mail address").fill(`shots-${scheme}-${info.project.name}@example.test`);
      await shot(page, "9-account-email");
      await page.getByRole("button", { name: "Send me a code" }).click();
      await page.getByLabel("Code").fill("000000");
      await page.getByRole("button", { name: "Sign in" }).click();
      await expect(page.getByRole("alert")).toBeVisible();
      await shot(page, "10-account-code-error");
      await page.getByLabel("Code").fill("123456");
      await page.getByRole("button", { name: "Sign in" }).click();
      await expect(page.getByText(/saved to your account/)).toBeVisible();
      await shot(page, "11-account");
      await page.getByRole("button", { name: "Delete my account" }).click();
      await shot(page, "12-account-delete-confirm");
    }
  });
}
