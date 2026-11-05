// What the player sees after an answer (tasks T068, T112): the verdict, the right answer when
// they missed it, the explanation and the source. Shared by the daily and practice.

import { forwardRef } from "react";
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
        {result.bonus > 0 ? " · +0.2 speed bonus" : ""}
      </p>
      {conflict && <p className="hint">You had already answered this question. This is the answer that counts.</p>}
      {result.grade < 1 && correctText && (
        <p>
          <strong>Right answer:</strong> {correctText}
          {result.correctLines?.length ? ` (line ${result.correctLines.join(", ")})` : ""}
        </p>
      )}
      <p>{result.explanation}</p>
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

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
