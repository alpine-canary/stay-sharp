// T103 (V6): challenge a colleague with two browser contexts. The owner finishes and creates a
// link; the colleague sees only the score, plays, then both see both results. A colleague who
// already finished sees both at once; bad links get a plain message.

import { expect, test, type Browser, type Page } from "@playwright/test";
import { answerByKeyboard, chooseSeniorAndStart, next } from "./play";

async function finishDaily(page: Page): Promise<void> {
  await chooseSeniorAndStart(page);
  for (const index of [0, 1, 2, 3, 4]) {
    await answerByKeyboard(page, index);
    await next(page, index === 4);
  }
  await expect(page.getByRole("heading", { name: "Your result", exact: true })).toBeVisible();
}

async function createLink(page: Page): Promise<string> {
  await page.getByRole("button", { name: "Create a challenge link" }).click();
  const link = page.locator(".link-text");
  await expect(link).toHaveText(/\/c\/[A-Z2-7]{12}$/);
  return new URL((await link.textContent()) ?? "").pathname;
}

async function newPlayer(browser: Browser, like: Page): Promise<Page> {
  const viewport = like.viewportSize();
  const context = await browser.newContext(viewport ? { viewport } : {});
  return context.newPage();
}

test("a colleague plays the same set, then both see both results", async ({ page, browser }) => {
  await finishDaily(page);
  const path = await createLink(page);

  const colleague = await newPlayer(browser, page);
  await colleague.goto(path);
  await expect(colleague.getByRole("heading", { name: /^A colleague scored \d(\.5)?\/5$/ })).toBeVisible();
  // The owner's squares stay hidden until the colleague finishes.
  await expect(colleague.getByRole("list", { name: /answers, question by question/ })).toHaveCount(0);

  await colleague.getByRole("button", { name: "Play this set" }).click();
  for (const index of [0, 1, 2, 3, 4]) {
    await answerByKeyboard(colleague, index);
    await next(colleague, index === 4);
  }
  await expect(colleague.getByRole("heading", { name: /came out ahead|A draw/ })).toBeVisible();
  await expect(colleague.getByRole("list", { name: "You: answers, question by question" })).toBeVisible();
  await expect(colleague.getByRole("list", { name: "Your colleague: answers, question by question" })).toBeVisible();

  // The owner opens the same link: their result and the colleague's, no second play.
  await page.goto(path);
  await expect(page.getByRole("heading", { name: "Your challenge" })).toBeVisible();
  await expect(page.getByText("1 colleague has finished it.")).toBeVisible();
  await expect(page.getByRole("list", { name: "Colleague 1: answers, question by question" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Play this set" })).toHaveCount(0);
  await colleague.context().close();
});

test("a colleague who already finished today sees both results at once", async ({ page, browser }) => {
  await finishDaily(page);
  const path = await createLink(page);

  const colleague = await newPlayer(browser, page);
  await finishDaily(colleague);
  await colleague.goto(path);
  await expect(colleague.getByRole("list", { name: "You: answers, question by question" })).toBeVisible();
  await expect(colleague.getByRole("button", { name: "Play this set" })).toHaveCount(0);
  await colleague.context().close();
});

test("an unknown link gets a plain message and today's daily", async ({ page }) => {
  await page.goto("/c/ABCDEFGHJKMN");
  await expect(page.getByRole("heading", { name: "This challenge link does not work" })).toBeVisible();
  await page.getByRole("link", { name: "Play today's daily" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Today's set #\d+/ })).toBeVisible();
});
