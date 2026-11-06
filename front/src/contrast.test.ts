// The colour pairs of the design (DESIGN.md) meet WCAG 2.2 AA: 4.5:1 for text, 3:1 for UI parts
// such as borders and verdict squares. The values are read from index.css, so a colour change is
// measured here before axe ever sees it.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(__dirname, "index.css"), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  const body = css.slice(start, css.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1] ?? "", m[2] ?? ""]));
}

const light = block(":root");
const dark = { ...light, ...block(':root[data-theme="dark"]') };

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

const TEXT: [string, string][] = [
  ["ink", "bg"],
  ["ink", "surface"],
  ["muted", "bg"],
  ["muted", "surface"],
  ["link", "bg"],
  ["link", "surface"],
  ["primary-ink", "primary"],
  ["good", "surface"],
  ["bad", "surface"],
  ["half", "surface"],
  ["good", "good-soft"],
  ["bad", "bad-soft"],
  ["half", "half-soft"],
  ["ink", "good-soft"],
  ["ink", "bad-soft"],
  // The feedback box is tinted with the verdict colour (no side bar).
  ["ink", "half-soft"],
  ["good", "half-soft"],
  ["on-verdict", "good"],
  ["on-verdict", "bad"],
  ["on-verdict", "half"],
  ["isl-ink", "isl"],
  ["isl-muted", "isl"],
  ["mint", "isl"],
  ["isl-bad", "isl"],
  ["isl-half", "isl"],
];
const UI: [string, string][] = [
  ["line-strong", "surface"],
  ["line-strong", "bg"],
  ["focus", "bg"],
  ["focus", "surface"],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme", (_, theme: Record<string, string>) => {
  it.each(TEXT)("text %s on %s is at least 4.5:1", (fg, bg) => {
    expect(ratio(theme[fg] ?? "", theme[bg] ?? "")).toBeGreaterThanOrEqual(4.5);
  });
  it.each(UI)("UI part %s on %s is at least 3:1", (fg, bg) => {
    expect(ratio(theme[fg] ?? "", theme[bg] ?? "")).toBeGreaterThanOrEqual(3);
  });
});
