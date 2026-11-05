// Skill view (FR-015): per deck, correct answers (half-right counts as half) out of answered
// questions, daily and practice combined, weakest deck first. Decks not played yet come last, in
// the deck order. Ties keep the deck order.

import type { DeckStat } from "../storage";

export interface SkillRow {
  deck: string;
  answered: number;
  correct: number;
  /** correct / answered, or null when nothing was answered yet. */
  share: number | null;
}

export function skills(stats: Record<string, DeckStat>, decks: readonly string[]): SkillRow[] {
  const rows = decks.map((deck, order) => {
    const { answered, correct } = stats[deck] ?? { answered: 0, correct: 0 };
    return { order, row: { deck, answered, correct, share: answered > 0 ? correct / answered : null } };
  });
  const rank = (share: number | null) => (share === null ? Infinity : share);
  rows.sort((a, b) => rank(a.row.share) - rank(b.row.share) || a.order - b.order);
  return rows.map(({ row }) => row);
}
