// The first screen of every page is its loading state for a new visitor (src/prerender.tsx).

import { describe, expect, it } from "vitest";
import { PAGES, render } from "./prerender";

const HEADINGS: Record<string, RegExp> = {
  "/": /Today('|&#x27;)s set/,
  "/play": /Choose a level first/,
  "/result?play=prerender": /Loading your result/,
  "/practice": /Choose a level first/,
  "/privacy": /What we keep, and where/,
  "/account": /<h1[^>]*>Account<\/h1>/,
  "/c/AAAAAAAAAAAA": /Loading the challenge/,
};

describe("prerender", () => {
  it.each(Object.keys(PAGES))("%s renders its own first screen", (url) => {
    const html = render(url);
    expect(html).toMatch(HEADINGS[url] ?? /never/);
    expect(html).toContain("Stay Sharp");
    // No storage notice and no player id in a page every visitor receives.
    expect(html).not.toMatch(/could not be read|does not let the site save/);
    expect(html).not.toContain("00000000-0000-4000-8000-000000000000");
  });

  it("covers every path the site router serves", () => {
    expect(Object.values(PAGES).sort()).toEqual(
      ["account.html", "c.html", "index.html", "play.html", "practice.html", "privacy.html", "result.html"].sort(),
    );
  });
});
