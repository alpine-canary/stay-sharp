// Write one HTML file per app page with its first screen inside #root (see src/prerender.tsx).
// Run after `vite build` and `vite build --ssr src/prerender.tsx --outDir dist-ssr`.

import { readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const front = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(front, "dist");
const ssr = join(front, "dist-ssr");
const { PAGES, render } = await import(pathToFileURL(join(ssr, "prerender.js")).href);

const template = readFileSync(join(dist, "index.html"), "utf8");
const empty = '<div id="root"></div>';
if (!template.includes(empty)) throw new Error("dist/index.html has no empty #root");

// og:url names the home page; another page (a challenge link above all) must not claim it.
const ogUrl = /\s*<meta property="og:url" content="[^"]*" \/>/;
if (!ogUrl.test(template)) throw new Error("dist/index.html has no og:url");

for (const [url, file] of Object.entries(PAGES)) {
  const html = render(url);
  if (!html.includes("Stay Sharp")) throw new Error(`prerender of ${url} looks empty`);
  const page = file === "index.html" ? template : template.replace(ogUrl, "");
  writeFileSync(join(dist, file), page.replace(empty, `<div id="root">${html}</div>`));
  console.log(`prerendered ${url} -> ${file} (${html.length} chars)`);
}
rmSync(ssr, { recursive: true, force: true });
