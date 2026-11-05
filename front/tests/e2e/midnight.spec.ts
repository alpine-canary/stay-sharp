// T059 (W2, V16), local only: with the server clock moved, a play started at 23:58 and finished
// at 00:03 counts for its start date, and the new day's set is a separate play.

import { expect, test } from "@playwright/test";
import { setServerTime } from "./clock";
import { answerByKeyboard, chooseSeniorAndStart, next } from "./play";

function zurichDate(offsetDays: number): string {
  const now = new Date(Date.now() + offsetDays * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Zurich" }).format(now);
}

function zurichOffset(day: string): string {
  // Winter time is +01:00, summer time +02:00; ask the formatter for that day.
  const name = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Zurich", timeZoneName: "longOffset" })
    .formatToParts(new Date(`${day}T12:00:00Z`))
    .find((p) => p.type === "timeZoneName")?.value;
  return (name ?? "GMT+01:00").replace("GMT", "") || "+00:00";
}

test.afterEach(() => setServerTime(null));

test("a play across midnight counts for its start date", async ({ page }) => {
  const day = zurichDate(0);
  const nextDay = zurichDate(1);
  setServerTime(`${day}T23:58:00${zurichOffset(day)}`);

  await chooseSeniorAndStart(page);
  const startNumber = await page.getByText(/Daily #\d+/).textContent();
  for (const index of [0, 1, 2]) {
    await answerByKeyboard(page, index);
    await next(page, false);
  }

  setServerTime(`${nextDay}T00:03:00${zurichOffset(nextDay)}`);
  for (const index of [3, 4]) {
    await answerByKeyboard(page, index);
    await next(page, index === 4);
  }

  await expect(page).toHaveURL(new RegExp(`/result\\?play=${day}\\.senior\\.daily`));
  await expect(page.getByText(new RegExp(`Daily #\\d+ · ${day}`))).toBeVisible();

  // Home is now on the new day: a new game number and a separate play.
  await page.getByRole("link", { name: "Back to today" }).click();
  await expect(page.getByText(`Daily · ${nextDay}`)).toBeVisible();
  await page.getByRole("link", { name: "Play today's set" }).click();
  await expect(page.getByText(/1\/5/)).toBeVisible();
  const newNumber = await page.getByText(/Daily #\d+/).textContent();
  expect(newNumber).not.toBe(startNumber);
});
