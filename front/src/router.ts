// Views switched by path, no router library (task T049, research R12).
// The paths must match APP_PATHS in infra/stacks/site_router.js, which serves index.html for them.

import { useEffect, useState } from "react";

export type View = "home" | "play" | "result" | "practice" | "privacy" | "challenge" | "not-found";

export const VIEW_PATHS: Record<Exclude<View, "challenge" | "not-found">, string> = {
  home: "/",
  play: "/play",
  result: "/result",
  practice: "/practice",
  privacy: "/privacy",
};

const CHALLENGE = /^\/c\/([A-Z2-7]{12})\/?$/;

export interface Route {
  view: View;
  challengeId?: string;
}

export function route(pathname: string): Route {
  const path = pathname.length > 1 ? pathname.replace(/\/$/, "") : pathname;
  for (const [view, viewPath] of Object.entries(VIEW_PATHS)) {
    if (viewPath === path) return { view: view as View };
  }
  const challenge = CHALLENGE.exec(pathname);
  if (challenge?.[1]) return { view: "challenge", challengeId: challenge[1] };
  return { view: "not-found" };
}

export function navigate(path: string): void {
  if (path === window.location.pathname) return;
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useRoute(): Route {
  const [current, setCurrent] = useState(() => route(window.location.pathname));
  useEffect(() => {
    const onChange = () => {
      setCurrent(route(window.location.pathname));
    };
    window.addEventListener("popstate", onChange);
    return () => {
      window.removeEventListener("popstate", onChange);
    };
  }, []);
  return current;
}
