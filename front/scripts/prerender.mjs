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

for (const [url, file] of Object.entries(PAGES)) {
  const html = render(url);
  if (!html.includes("Stay Sharp")) throw new Error(`prerender of ${url} looks empty`);
  writeFileSync(join(dist, file), template.replace(empty, `<div id="root">${html}</div>`));
  console.log(`prerendered ${url} -> ${file} (${html.length} chars)`);
}
rmSync(ssr, { recursive: true, force: true });
