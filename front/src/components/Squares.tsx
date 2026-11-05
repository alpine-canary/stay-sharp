// One square per question (task T067). Each has a symbol and a text label, so no information is
// carried by colour alone (FR-033).

export type Grade = 0 | 0.5 | 1;

export interface SquaresProps {
  grades: readonly (number | null | undefined)[];
  decks?: readonly string[];
  /** Index of the question on screen, if any. */
  current?: number | undefined;
  label?: string;
}

const SYMBOL: Record<string, string> = { "1": "✓", "0.5": "½", "0": "✗" };
const WORD: Record<string, string> = { "1": "right", "0.5": "half right", "0": "wrong" };
const CLASS: Record<string, string> = { "1": "s1", "0.5": "s05", "0": "s0" };

export function gradeWord(grade: number | null | undefined): string {
  return grade === null || grade === undefined ? "not answered" : (WORD[String(grade)] ?? "not answered");
}

export function Squares({ grades, decks, current, label = "Your answers" }: SquaresProps) {
  return (
    <ol className="squares" aria-label={label}>
      {Array.from({ length: 5 }, (_, i) => {
        const g = grades[i];
        const key = g === null || g === undefined ? null : String(g);
        const deck = decks?.[i];
        const classes = [key ? CLASS[key] : "", current === i ? "cur" : ""].filter(Boolean).join(" ");
        return (
          <li key={i} className={classes || undefined} aria-current={current === i ? "step" : undefined}>
            <span aria-hidden="true">{key ? SYMBOL[key] : "·"}</span>
            <span className="sr-only">
              Question {i + 1}
              {deck ? ` (${deck})` : ""}: {gradeWord(g)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
