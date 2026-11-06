// Share card without spoilers (task T100, Story 3, FR-017, FR-033). The text holds the game
// number, level, one square per question, score, speed bonus or "relaxed", time and streak, and
// the site address: never a question, an answer or a deck name.

import { useRef, useState } from "react";
import { LEVEL_NAMES } from "../decks";
import type { Level } from "../storage";
import { gradeWord } from "./Squares";

export interface ShareInput {
  gameNumber: number;
  level: Level;
  grades: readonly (number | null | undefined)[];
  score: number;
  bonus: number;
  relaxed: boolean;
  elapsedMs: number;
  streak: number;
  /** The site address without the scheme, e.g. "stay-sharp.example.org". */
  address: string;
}

// Distinct shapes of colour that screen readers name differently ("green square", "yellow
// square", "red square"), so the card reads without colour.
const SQUARE: Record<string, string> = { "1": "🟩", "0.5": "🟨", "0": "🟥" };

function figure(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function duration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}s`;
}

export function shareText(input: ShareInput): string {
  const level = LEVEL_NAMES[input.level];
  const squares = Array.from({ length: 5 }, (_, i) => SQUARE[String(input.grades[i])] ?? "⬜").join("");
  const speed = input.relaxed ? "relaxed" : `speed +${figure(input.bonus)}`;
  return [
    `Stay Sharp #${input.gameNumber} · ${level}`,
    `${squares}  ${figure(input.score)}/5 · ${speed} · ${duration(input.elapsedMs)} · streak ${input.streak}`,
    input.address,
  ].join("\n");
}

export type CopyStatus = null | "copied" | "manual";

/** Copy to the clipboard; when that is not possible, select the element's text instead
 * (Story 3, scenario 3) and say so. */
export async function copyOrSelect(text: string, element: HTMLElement | null): Promise<CopyStatus> {
  const clipboard = typeof navigator === "undefined" ? undefined : navigator.clipboard;
  if (clipboard?.writeText) {
    try {
      await clipboard.writeText(text);
      return "copied";
    } catch {
      // Refused (no permission, not a secure page): fall through to selecting by hand.
    }
  }
  const selection = window.getSelection();
  if (element && selection) {
    selection.removeAllRanges();
    selection.selectAllChildren(element);
  }
  return "manual";
}

export const MANUAL_COPY = "This browser could not copy it. The text is selected: copy it with your keyboard or a long press.";

export function ShareCard(props: ShareInput) {
  const text = shareText(props);
  const box = useRef<HTMLPreElement>(null);
  const [status, setStatus] = useState<CopyStatus>(null);

  async function copy() {
    setStatus(await copyOrSelect(text, box.current));
  }

  return (
    <section className="share" aria-labelledby="share-title">
      <h2 id="share-title" className="eyebrow">
        Share your result
      </h2>
      <pre ref={box} className="share-text" aria-hidden="true">
        {text}
      </pre>
      <ul className="sr-only" aria-label="Your share card">
        <li>{text.split("\n")[0]}</li>
        {Array.from({ length: 5 }, (_, i) => (
          <li key={i}>
            Question {i + 1}: {gradeWord(props.grades[i])}
          </li>
        ))}
        <li>{text.split("\n")[1]?.split("  ")[1]}</li>
        <li>{props.address}</li>
      </ul>
      <div className="row">
        <button type="button" className="btn" onClick={() => void copy()}>
          Copy result
        </button>
      </div>
      <p role="status" className="hint">
        {status === "copied" && "Copied. Paste it wherever you like."}
        {status === "manual" && MANUAL_COPY}
      </p>
    </section>
  );
}
