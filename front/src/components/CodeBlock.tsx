// Code with line numbers (task T064). With `onPick`, the lines become a listbox: arrow keys move,
// Enter or Space picks, a click picks. The code scrolls inside its own box; the page never
// scrolls sideways.

import { useId, useState, type KeyboardEvent } from "react";

export interface CodeBlockProps {
  code: string;
  language?: string | undefined;
  /** Picked line, 1-based. */
  picked?: number | null;
  onPick?: ((line: number) => void) | undefined;
  /** After the answer: the right lines and whether the picked one was wrong. */
  correctLines?: readonly number[] | undefined;
  disabled?: boolean;
}

export function lines(code: string): string[] {
  const all = code.split("\n");
  if (all.length > 1 && all[all.length - 1] === "") all.pop();
  return all;
}

export function CodeBlock({ code, language, picked = null, onPick, correctLines, disabled = false }: CodeBlockProps) {
  const id = useId();
  const rows = lines(code);
  const [active, setActive] = useState<number>(picked ?? 1);
  const label = language ? `Code (${language})` : "Code";

  if (!onPick) {
    return (
      // A scrollable region must be reachable by keyboard so it can be scrolled (axe
      // scrollable-region-focusable).
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      <div className="code" role="region" aria-label={label} tabIndex={0}>
        <div className="in">
          {rows.map((text, i) => (
            <div key={i} className={rowClass(i + 1, picked, correctLines)}>
              <span className="g" aria-hidden="true">
                {i + 1}
              </span>
              {text || " "}
            </div>
          ))}
        </div>
      </div>
    );
  }

  const move = (to: number) => {
    const next = Math.min(rows.length, Math.max(1, to));
    setActive(next);
    document.getElementById(`${id}-${next}`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (disabled) return;
    const keys: Record<string, () => void> = {
      ArrowDown: () => move(active + 1),
      ArrowUp: () => move(active - 1),
      Home: () => move(1),
      End: () => move(rows.length),
      Enter: () => onPick(active),
      " ": () => onPick(active),
    };
    const action = keys[event.key];
    if (action) {
      event.preventDefault();
      action();
    }
  };

  return (
    <div
      className="code"
      role="listbox"
      tabIndex={disabled ? -1 : 0}
      aria-label={`${label}: pick the line with the worst defect. Arrow keys move, Enter picks.`}
      aria-activedescendant={disabled ? undefined : `${id}-${active}`}
      aria-disabled={disabled || undefined}
      onKeyDown={onKeyDown}
    >
      <div className="in">
        {rows.map((text, i) => {
          const n = i + 1;
          return (
            // Keyboard handling lives on the listbox (aria-activedescendant pattern).
            // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/interactive-supports-focus
            <div
              key={n}
              id={`${id}-${n}`}
              role="option"
              aria-selected={picked === n}
              className={`${rowClass(n, picked, correctLines)}${!disabled && active === n ? " active" : ""}`}
              onClick={() => {
                if (disabled) return;
                setActive(n);
                onPick(n);
              }}
            >
              <span className="g" aria-hidden="true">
                {n}
              </span>
              <span className="sr-only">Line {n}: </span>
              {text || " "}
              {correctLines?.includes(n) && <span className="sr-only"> (right line)</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function rowClass(n: number, picked: number | null, correct: readonly number[] | undefined): string {
  if (!correct) return "ln";
  if (correct.includes(n)) return "ln ok";
  if (picked === n) return "ln ko";
  return "ln";
}
