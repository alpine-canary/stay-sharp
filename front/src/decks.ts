// Deck names shown to players (spec FR-001).

export const DECK_NAMES: Record<string, string> = {
  spot: "Spot the bug",
  better: "Could do better",
  fail: "What if it fails?",
  acronym: "Acronym or tool",
  news: "AI this week",
  logic: "Logic puzzle",
  readcode: "Read the code",
  whatif: "What happens if…",
  words: "Tech words",
  aisense: "AI sense",
};

export const DECK_ORDER = {
  senior: ["spot", "better", "fail", "acronym", "news"],
  starter: ["logic", "readcode", "whatif", "words", "aisense"],
} as const;

/** Decks where the player also picks a line. */
export const LINE_DECKS = new Set(["spot"]);

export function deckName(deck: string): string {
  return DECK_NAMES[deck] ?? deck;
}
