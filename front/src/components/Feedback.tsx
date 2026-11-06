// What the player sees after an answer (tasks T068, T112): the verdict, the right answer when
// they missed it, the explanation and the source. Shared by the daily and practice.

import { forwardRef, type ReactNode } from "react";
import type { AnswerResult, QuestionView } from "../api/client";

export interface FeedbackProps {
  result: AnswerResult;
  question: QuestionView;
  needsLine: boolean;
  line: number | null;
  /** The server had a different answer already: this one is the answer that counts. */
  conflict: boolean;
}

export const Feedback = forwardRef<HTMLDivElement, FeedbackProps>(function Feedback(
  { result, question, needsLine, line, conflict },
  ref,
) {
  const verdict = verdictOf(result, needsLine, line);
  const correctText = question.choices.find((c) => c.id === result.correctChoiceId)?.text;
  return (
    <div className={`fb ${verdict.className}`} role="status" tabIndex={-1} ref={ref}>
      <p className="verdict">
        {verdict.text}
        {result.bonus > 0 && <span className="bonus"> +0.2 speed bonus</span>}
      </p>
      {conflict && <p className="hint">You had already answered this question. This is the answer that counts.</p>}
      {result.grade < 1 && correctText && (
        <p>
          <strong>Right answer:</strong> {withCode(correctText)}
          {result.correctLines?.length ? ` (line ${result.correctLines.join(", ")})` : ""}
        </p>
      )}
      <p>{withCode(result.explanation)}</p>
      {result.sourceUrl && (
        <p className="hint">
          Source:{" "}
          <a href={result.sourceUrl} target="_blank" rel="noopener noreferrer">
            {hostOf(result.sourceUrl)}
          </a>
          {result.sourceDate ? ` · ${result.sourceDate}` : ""}
        </p>
      )}
    </div>
  );
});

export function verdictOf(result: AnswerResult, needsLine: boolean, line: number | null) {
  if (result.grade === 1) return { text: "Right", className: "v1" };
  if (result.grade === 0) return { text: "Not this time", className: "v0" };
  const lineRight = needsLine && line !== null && (result.correctLines ?? []).includes(line);
  return { text: lineRight ? "Half right: right line, wrong problem" : "Half right: right problem, wrong line", className: "v05" };
}

/** Text between backticks is code: shown in the mono font (the content uses `like this`). */
export function withCode(text: string): ReactNode[] {
  const parts = text.split("`");
  if (parts.length % 2 === 0) return [text]; // an unpaired backtick: plain text
  return parts.map((part, i) => (i % 2 === 1 && part ? <code key={i}>{part}</code> : part));
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
