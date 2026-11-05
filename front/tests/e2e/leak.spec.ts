// T058 (FR-003, SC-002, V2): before each answer, nothing the browser holds reveals it. Checked
// after the fact: once the answer arrives we know its explanation and source, and look for them
// (and for any answer field name) in what the browser held just before submitting.

import { expect, test, type Page, type Response } from "@playwright/test";
import { answerByKeyboard, chooseSeniorAndStart, next } from "./play";

const ANSWER_FIELDS = ["correctChoiceId", "answerChoiceId", "correctLines", "answerLines", "explanation", "sourceUrl"];

interface Snapshot {
  html: string;
  scripts: string;
  storage: string;
  caches: string;
  network: string;
}

async function snapshot(page: Page, bodies: string[]): Promise<Snapshot> {
  const browser = await page.evaluate(async () => {
    const scripts = await Promise.all(
      [...document.scripts].map(async (s) => (s.src ? fetch(s.src).then((r) => r.text()) : s.textContent ?? "")),
    );
    const cached: string[] = [];
    if ("caches" in window) {
      for (const name of await caches.keys()) {
        const cache = await caches.open(name);
        for (const request of await cache.keys()) {
          const response = await cache.match(request);
          cached.push(request.url, response ? await response.text() : "");
        }
      }
    }
    return {
      html: document.documentElement.outerHTML,
      scripts: scripts.join("\n"),
      storage: JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }),
      caches: cached.join("\n"),
    };
  });
  return { ...browser, network: bodies.join("\n") };
}

test("no answer, explanation or source before each answer", async ({ page }) => {
  const bodies: string[] = [];
  page.on("response", async (response: Response) => {
    if (!response.url().includes("/api/")) return;
    try {
      bodies.push(await response.text());
    } catch {
      // Redirects and aborted requests have no body.
    }
  });

  await chooseSeniorAndStart(page);

  for (let index = 0; index < 5; index++) {
    await expect(page.getByText(new RegExp(`${index + 1}/5`))).toBeVisible();
    const before = await snapshot(page, bodies);
    const answered = page.waitForResponse((r) => r.url().endsWith(`/questions/${index}/answer`));
    await answerByKeyboard(page, index);
    const result = (await (await answered).json()) as { explanation: string; sourceUrl?: string };

    for (const [where, text] of Object.entries(before)) {
      // The app's own code names these fields to read them after an answer; look for values there.
      for (const field of where === "scripts" ? [] : ANSWER_FIELDS) {
        expect(text, `${where} held "${field}" before answer ${index + 1}`).not.toContain(`"${field}"`);
      }
      expect(text, `${where} held the explanation before answer ${index + 1}`).not.toContain(
        result.explanation.slice(0, 60),
      );
      if (result.sourceUrl) {
        expect(text, `${where} held the source before answer ${index + 1}`).not.toContain(result.sourceUrl);
      }
    }
    // Earlier answers are allowed to be known: watch only what arrives for the next question.
    bodies.length = 0;
    await next(page, index === 4);
  }
});
