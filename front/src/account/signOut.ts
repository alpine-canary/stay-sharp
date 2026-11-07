// Sign out (T241, US6, FR-113). The account keeps everything; this browser forgets it.
//
// Before forgetting, the browser sends its latest progress (a change made less than 1.5 s ago
// may not have left yet), then ends the session on every device (global sign-out). Both steps
// are best effort and bounded in time: signing out works offline too, and the caller then
// clears the tokens and the local progress.

import type { Progress } from "../storage";
import type { Runtime } from "./runtime";
import { createSync } from "./sync";

const TIMEOUT_MS = 3_000;

function bounded(work: Promise<unknown>, ms: number): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    work.then(
      () => {
        clearTimeout(timer);
        resolve();
      },
      () => {
        clearTimeout(timer);
        resolve();
      },
    );
  });
}

export async function signOut(
  { api, cognito, session }: Pick<Runtime, "api" | "cognito" | "session">,
  current: () => Progress,
  timeoutMs: number = TIMEOUT_MS,
  replace: (progress: Progress) => void = () => undefined,
  storage: Storage | null = null,
): Promise<void> {
  // A refresh may be needed for the token: bounded too.
  let token: string | null = null;
  await bounded(
    session.accessToken().then((found) => {
      token = found;
    }),
    timeoutMs,
  );
  if (!token) return;
  await bounded(createSync({ api, current, replace, storage }).push(), timeoutMs);
  await bounded(cognito.signOut(token), timeoutMs);
}
