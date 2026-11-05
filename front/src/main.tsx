// Entry: tiny on purpose (FR-034). A prerendered first screen (src/prerender.tsx) is painted
// before the app's code is even requested; the app then loads and replaces it. The dev server
// has no first screen, so it loads the app at once.

import "./index.css";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");
const container = root;

function load(): void {
  void import("./start").then(({ start }) => start(container));
}

if (container.hasChildNodes()) requestAnimationFrame(() => setTimeout(load, 0));
else load();
