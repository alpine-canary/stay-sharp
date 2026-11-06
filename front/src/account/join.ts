// After sign-in (task T229, FR-109, FR-110): the account takes this browser's history.
// - First sign-in ever: the account is created with this browser's player id and progress.
// - Another browser: the server merges this browser's plays into the account's player id, this
//   browser switches to that id, and both progress copies are merged here ("sum": two separate
//   histories), then stored on the account.

import { isProgress, type Progress } from "../storage";
import type { AccountApi } from "./api";
import { fromCopy, mergeProgress, toCopy } from "./merge";

export interface Joined {
  created: boolean;
  /** Two histories were put together: say so to the player. */
  combined: boolean;
  version: number;
}

function hasDays(p: Progress): boolean {
  return Object.values(p.days).some((days) => Object.keys(days).length > 0);
}

export async function joinAccount(api: AccountApi, current: () => Progress, replace: (p: Progress) => void): Promise<Joined> {
  const local = current();
  const adopted = await api.adopt(local.playerId);
  const remote = await api.getProgress();
  const primary = adopted.primaryPlayerId;
  // Same id: this browser already was the account's (signed in again). Else, two histories.
  const how = local.playerId === primary ? "max" : "sum";
  let next: Progress = { ...local, playerId: primary };
  const theirs = remote.version > 0 ? fromCopy(remote.body, primary, isProgress) : null;
  if (theirs) next = mergeProgress(next, theirs, how);
  replace(next);
  const { stored, conflict } = await api.putProgress(remote.version, toCopy(next));
  let version = stored.version;
  if (conflict) {
    // Someone wrote in between: merge once more and store.
    const again = fromCopy(stored.body, primary, isProgress);
    if (again) next = mergeProgress(next, again, "max");
    replace(next);
    version = (await api.putProgress(stored.version, toCopy(next))).stored.version;
  }
  const combined = how === "sum" && !adopted.created && (adopted.merged.plays > 0 || (hasDays(local) && theirs !== null && hasDays(theirs)));
  return { created: adopted.created, combined, version };
}
