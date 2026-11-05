// Practice boxes, Leitner style (task T111, FR-022, research R7). Pure functions over the local
// practice state of one level.
//
// A miss or a half-right answer sends a question to box 1; each right answer moves it up one box.
// A question is "due" again after a number of practice answers that grows with its box, and due
// questions are sent to the server as `prefer` (at most 5, most overdue first). Box 5 is no longer
// preferred. The server honours a preferred id only when it is a past question of that level and
// deck (C4), so this list can never reach a future question.

export const MAX_PREFERRED = 5;
export const TOP_BOX = 5;

/** Practice answers to wait before a box comes back. A miss comes back on the second next
 * question, so always within the next 5. Box 5 is not scheduled. */
const WAIT: Record<number, number> = { 1: 1, 2: 4, 3: 9, 4: 19 };

export interface Card {
  box: number;
  /** Due once `seen` reaches this. */
  due: number;
  deck: string;
}

export interface PracticeState {
  /** Practice answers counted so far (duplicates excluded). */
  seen: number;
  cards: Record<string, Card>;
}

export interface PracticeAnswer {
  qid: string;
  deck: string;
  grade: number;
  /** The server already had this answer: it was counted the first time (W13). */
  duplicate: boolean;
}

export function freshPractice(): PracticeState {
  return { seen: 0, cards: {} };
}

export function recordPractice(state: PracticeState, answer: PracticeAnswer): PracticeState {
  if (answer.duplicate) return state;
  const seen = state.seen + 1;
  const before = state.cards[answer.qid];
  const box = answer.grade < 1 ? 1 : Math.min(TOP_BOX, (before?.box ?? 1) + 1);
  const due = box >= TOP_BOX ? Number.MAX_SAFE_INTEGER : seen + (WAIT[box] ?? 1);
  return { seen, cards: { ...state.cards, [answer.qid]: { box, due, deck: answer.deck } } };
}

/** Due questions to ask for first, most overdue first, then lowest box. */
export function preferred(state: PracticeState, filter: { deck?: string | undefined }): string[] {
  return Object.entries(state.cards)
    .filter(([, card]) => card.box < TOP_BOX && card.due <= state.seen)
    .filter(([, card]) => !filter.deck || card.deck === filter.deck)
    .sort(([a, x], [b, y]) => x.due - y.due || x.box - y.box || a.localeCompare(b))
    .slice(0, MAX_PREFERRED)
    .map(([qid]) => qid);
}
