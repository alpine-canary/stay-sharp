// Merge two progress values per level (task T227, FR-110, FR-111). Pure.
//
// - Days: union; one result per date and level. On the same date the account's copy wins: it
//   holds the result that was synced first (the server kept the first finished daily too).
// - Longest streak: the larger of both, and of the streak recomputed from the merged days.
// - Freeze: used days combined, a freeze held if either side holds one, the later earning week.
// - Skill counts and practice: "sum" when two separate histories meet for the first time (a
//   second device joins the account); "max" when a sync meets a newer copy of the same history
//   (a 409), so nothing already shared is counted twice.

import { streak } from "../progress/streak";
import type { PracticeState } from "../progress/boxes";
import { LEVELS, type DeckStat, type Freeze, type Level, type Progress } from "../storage";

export type Combine = "sum" | "max";

function mergeDays(local: Progress["days"][Level], account: Progress["days"][Level]) {
  return { ...local, ...account };
}

function mergeFreeze(a: Freeze, b: Freeze): Freeze {
  const weeks = [a.earnedWeek, b.earnedWeek].filter((w): w is string => w !== null).sort();
  return {
    held: Math.max(a.held, b.held),
    earnedWeek: weeks.at(-1) ?? null,
    usedOn: [...new Set([...a.usedOn, ...b.usedOn])].sort(),
  };
}

function mergeStats(a: Record<string, DeckStat>, b: Record<string, DeckStat>, how: Combine): Record<string, DeckStat> {
  const out: Record<string, DeckStat> = { ...a };
  for (const [deck, stat] of Object.entries(b)) {
    const mine = out[deck];
    if (!mine) out[deck] = stat;
    else if (how === "sum") out[deck] = { answered: mine.answered + stat.answered, correct: mine.correct + stat.correct };
    else out[deck] = stat.answered > mine.answered ? stat : mine;
  }
  return out;
}

function mergePractice(a: PracticeState, b: PracticeState, how: Combine): PracticeState {
  const cards = { ...a.cards };
  for (const [qid, card] of Object.entries(b.cards)) {
    const mine = cards[qid];
    // The lower box is the safer guess: the question comes back sooner.
    if (!mine || card.box < mine.box || (card.box === mine.box && card.due < mine.due)) cards[qid] = card;
  }
  return { seen: how === "sum" ? a.seen + b.seen : Math.max(a.seen, b.seen), cards };
}

/** ``local`` keeps its player id, level choice and relaxed setting. */
export function mergeProgress(local: Progress, account: Progress, how: Combine): Progress {
  const out: Progress = { ...local, level: local.level ?? account.level };
  out.days = { ...local.days };
  out.freeze = { ...local.freeze };
  out.longest = { ...local.longest };
  out.deckStats = { ...local.deckStats };
  out.practice = { ...local.practice };
  for (const level of LEVELS) {
    const days = mergeDays(local.days[level], account.days[level]);
    out.days[level] = days;
    out.freeze[level] = mergeFreeze(local.freeze[level], account.freeze[level]);
    const dates = Object.keys(days).sort();
    const recomputed = dates.length ? streak(dates, dates.at(-1) as string).longest : 0;
    out.longest[level] = Math.max(local.longest[level], account.longest[level], recomputed);
    out.deckStats[level] = mergeStats(local.deckStats[level], account.deckStats[level], how);
    out.practice[level] = mergePractice(local.practice[level], account.practice[level], how);
  }
  return out;
}

/** The copy sent to the account: everything but this browser's player id. */
export function toCopy(progress: Progress): Omit<Progress, "playerId"> {
  const { playerId: _drop, ...copy } = progress;
  void _drop;
  return copy;
}

/** A copy from the account, as this browser's progress (null when it is not a valid one). */
export function fromCopy(body: unknown, playerId: string, isProgress: (v: unknown) => v is Progress): Progress | null {
  const candidate = { ...(body as object), playerId };
  return isProgress(candidate) ? candidate : null;
}
