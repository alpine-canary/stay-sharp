// First-screen size check (task T246). After `pnpm build`: the entry script and every chunk the
// app loads at start (the dynamic "start" chunk and its static imports), gzipped, must stay
// within bundle-budget.json plus 1 KB. Account, offer and sync chunks load later and do not count.
//
//   node scripts/bundle-size.mjs           check
//   node scripts/bundle-size.mjs --print   print the sizes only

import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const dist = new URL("../dist/", import.meta.url);
const budget = JSON.parse(readFileSync(new URL("../bundle-budget.json", import.meta.url), "utf8"));
const html = readFileSync(new URL("index.html", dist), "utf8");
const entry = /<script[^>]+src="\/assets\/([^"]+\.js)"/.exec(html)?.[1];
if (!entry) throw new Error("no entry script in dist/index.html");

const read = (name) => readFileSync(new URL(`assets/${name}`, dist), "utf8");
const gz = (name) => gzipSync(read(name), { level: 9 }).length;

const start = /import\(`\.\/(start-[^`]+\.js)`\)/.exec(read(entry))?.[1];
if (!start) throw new Error("the entry does not load a start chunk");
const files = new Set([entry, start]);
for (const name of [...files]) {
  for (const match of read(name).matchAll(/from"\.\/([^"]+\.js)"/g)) files.add(match[1]);
}
const sizes = Object.fromEntries([...files].map((name) => [name, gz(name)]));
const total = Object.values(sizes).reduce((a, b) => a + b, 0);
const limit = budget.firstScreenGzipBytes + budget.toleranceBytes;
console.log(JSON.stringify({ sizes, total, budget: budget.firstScreenGzipBytes, limit }));
if (!process.argv.includes("--print") && total > limit) {
  console.error(`first screen is ${total} B gzipped, over ${limit} B: keep new code out of it or raise the budget on purpose`);
  process.exit(1);
}
