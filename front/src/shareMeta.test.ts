// Link previews on LinkedIn, X and messaging apps (campaign 2026-11): the home page carries
// Open Graph and Twitter tags with absolute URLs, and the image exists in public/ at the size
// and weight the networks accept (1200x630, under 400 KB).

import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const front = join(__dirname, "..");
const html = readFileSync(join(front, "index.html"), "utf8");
const SITE = "https://stay-sharp.lumineth.com";

function meta(attr: "property" | "name", key: string): string | undefined {
  const match = html.match(new RegExp(`<meta\\s+${attr}="${key}"\\s+content="([^"]+)"`));
  return match?.[1];
}

describe("share preview", () => {
  it("has the Open Graph and Twitter tags, with absolute URLs", () => {
    expect(meta("property", "og:title")).toBeTruthy();
    expect(meta("property", "og:description")).toBeTruthy();
    expect(meta("property", "og:type")).toBe("website");
    expect(meta("property", "og:url")).toBe(`${SITE}/`);
    expect(meta("property", "og:image")).toBe(`${SITE}/og.png`);
    expect(meta("property", "og:image:width")).toBe("1200");
    expect(meta("property", "og:image:height")).toBe("630");
    expect(meta("property", "og:image:alt")).toBeTruthy();
    expect(meta("name", "twitter:card")).toBe("summary_large_image");
  });

  it("ships a 1200x630 PNG under 400 KB", () => {
    const file = join(front, "public", "og.png");
    const bytes = readFileSync(file);
    expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
    expect(bytes.readUInt32BE(16)).toBe(1200);
    expect(bytes.readUInt32BE(20)).toBe(630);
    expect(statSync(file).size).toBeLessThan(400 * 1024);
  });
});
