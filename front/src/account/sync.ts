// Keep this browser's progress and the account's copy in step (task T228, FR-111).
//
// - push(progress): send the whole copy with the last version seen. On 409, merge with the
//   stored copy ("max": same history), keep the result here, and try again (3 times at most,
//   with a short backoff). Offline or 5xx: remember that a push is due and retry on the next
//   change, on "online" and when the page gets focus.
// - pull(): read the copy (on open and on focus); a newer one is merged in here.

import type { AccountApi, ProgressCopy } from "./api";
import { AccountApiError } from "./api";
import { fromCopy, mergeProgress, toCopy } from "./merge";
import { isProgress, type Progress } from "../storage";

export const SYNC_KEY = "staysharp.sync";
const ATTEMPTS = 3;

export interface SyncState {
  version: number;
  pending: boolean;
}

export interface SyncOptions {
  api: AccountApi;
  current: () => Progress;
  replace: (progress: Progress) => void;
  storage?: Storage | null;
  sleep?: (ms: number) => Promise<void>;
}

function readState(storage: Storage | null): SyncState {
  try {
    const raw = storage?.getItem(SYNC_KEY);
    const parsed = raw ? (JSON.parse(raw) as Partial<SyncState>) : {};
    return { version: Number(parsed.version) || 0, pending: parsed.pending === true };
  } catch {
    return { version: 0, pending: false };
  }
}

export function createSync({ api, current, replace, storage = null, sleep = (ms) => new Promise((r) => setTimeout(r, ms)) }: SyncOptions) {
  let state = readState(storage);
  let running: Promise<void> = Promise.resolve();

  function save(next: SyncState) {
    state = next;
    try {
      storage?.setItem(SYNC_KEY, JSON.stringify(next));
    } catch {
      // Memory only.
    }
  }

  function adoptRemote(remote: ProgressCopy): Progress {
    const local = current();
    const theirs = fromCopy(remote.body, local.playerId, isProgress);
    if (!theirs) return local;
    const merged = mergeProgress(local, theirs, "max");
    if (JSON.stringify(merged) !== JSON.stringify(local)) replace(merged);
    return merged;
  }

  async function pushNow(): Promise<void> {
    for (let attempt = 0; attempt < ATTEMPTS; attempt++) {
      try {
        const { stored, conflict } = await api.putProgress(state.version, toCopy(current()));
        if (!conflict) {
          save({ version: stored.version, pending: false });
          return;
        }
        adoptRemote(stored);
        save({ version: stored.version, pending: true });
        await sleep(200 * 2 ** attempt);
      } catch (error) {
        save({ ...state, pending: true });
        if (error instanceof AccountApiError && error.transient) return;
        throw error;
      }
    }
  }

  async function pullNow(): Promise<void> {
    try {
      const remote = await api.getProgress();
      if (remote.version > state.version) {
        const merged = adoptRemote(remote);
        const differs = JSON.stringify(toCopy(merged)) !== JSON.stringify(remote.body);
        save({ version: remote.version, pending: state.pending || differs });
      }
      if (state.pending) await pushNow();
    } catch (error) {
      if (!(error instanceof AccountApiError && error.transient)) throw error;
    }
  }

  // One request at a time, in order.
  const queue = (work: () => Promise<void>) => (running = running.then(work, work));

  return {
    state: () => state,
    setVersion: (version: number) => save({ version, pending: state.pending }),
    push: () => queue(pushNow),
    pull: () => queue(pullNow),
  };
}

export type Sync = ReturnType<typeof createSync>;
