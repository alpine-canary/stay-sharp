// Build-time first screens (FR-034, SC-007): each app page is rendered once to static HTML, so the
// browser paints it before the script loads. React then replaces it with the live view
// (createRoot, not hydration: the live view depends on this browser's storage and the server).
// The render is the page's loading state for a new visitor: no level, nothing fetched yet.

import { renderToString } from "react-dom/server";
import type { ApiClient } from "./api/client";
import { App } from "./App";
import { freshProgress, type ProgressStore } from "./storage";

/** Page URL -> file name in dist. infra/stacks/site_router.js serves each path with its file. */
export const PAGES: Record<string, string> = {
  "/": "index.html",
  "/play": "play.html",
  "/result?play=prerender": "result.html",
  "/practice": "practice.html",
  "/privacy": "privacy.html",
  "/c/AAAAAAAAAAAA": "c.html",
};

const NOBODY = "00000000-0000-4000-8000-000000000000";

export function render(url: string): string {
  const where = new URL(url, "https://prerender.invalid");
  // The router and the query reader look at window.location during the first render only.
  const scope = globalThis as { window?: unknown };
  const before = scope.window;
  scope.window = {
    location: { pathname: where.pathname, search: where.search, host: "", origin: "" },
  };
  const store: ProgressStore = {
    load: () => ({ progress: freshProgress(NOBODY), notice: null }),
    save: () => true,
    persistent: true,
  };
  // Every call stays pending: the first screen is the loading state.
  const pending = new Promise<never>(() => undefined);
  const client = new Proxy({}, { get: () => () => pending }) as ApiClient;
  try {
    return renderToString(<App store={store} client={client} />);
  } finally {
    if (before === undefined) delete scope.window;
    else scope.window = before;
  }
}
