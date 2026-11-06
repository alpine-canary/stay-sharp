// Signed-in browsers only: keep the progress in step with the account while playing (T228).
// Loaded by App when the session hint says so; never part of the first screen.

import type { Progress } from "../storage";
import { loadAuthConfig } from "./cognito";
import { localStorageOrNull, makeRuntime } from "./runtime";
import { createSync } from "./sync";

export interface Live {
  /** Call after every change of the local progress. */
  changed: () => void;
  stop: () => void;
}

const DEBOUNCE_MS = 1_500;

export async function connect(current: () => Progress, replace: (p: Progress) => void): Promise<Live | null> {
  const config = await loadAuthConfig();
  if (!config) return null;
  const { session, api } = makeRuntime(config);
  if (!session.signedIn()) return null;
  const sync = createSync({ api, current, replace, storage: localStorageOrNull() });
  const pull = () => void sync.pull().catch(() => undefined);
  const push = () => void sync.push().catch(() => undefined);
  pull();
  const onFocus = () => {
    if (document.visibilityState === "visible") pull();
  };
  document.addEventListener("visibilitychange", onFocus);
  window.addEventListener("online", push);
  let timer: ReturnType<typeof setTimeout> | undefined;
  return {
    changed() {
      clearTimeout(timer);
      timer = setTimeout(push, DEBOUNCE_MS);
    },
    stop() {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onFocus);
      window.removeEventListener("online", push);
    },
  };
}
