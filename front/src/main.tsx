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

// With a first screen: wait until its three fonts are ready (at most 1 s) and it has painted,
// so its text is the largest paint, then load the app. document.fonts.ready alone resolves too
// early: preloaded fonts are not font loads until a text asks for them.
const FIRST_SCREEN_FONTS = ['600 1em "Source Serif 4"', '400 1em "IBM Plex Sans"', '600 1em "IBM Plex Sans"'];
function fontsReady(): Promise<unknown> {
  const fonts = Promise.allSettled(FIRST_SCREEN_FONTS.map((font) => document.fonts.load(font)));
  return Promise.race([fonts, new Promise((resolve) => setTimeout(resolve, 1000))]);
}

if (container.hasChildNodes()) void fontsReady().then(() => requestAnimationFrame(() => setTimeout(load, 0)));
else load();
