// Four choices as a native radio group (task T065). Enter submits the surrounding form; the
// group is disabled while submitting, so a double click sends one request.

export interface Choice {
  id: string;
  text: string;
}

export interface ChoicesProps {
  name: string;
  legend: string;
  choices: readonly Choice[];
  value: string | null;
  onChange: (id: string) => void;
  disabled?: boolean;
  /** After the answer: the right choice id. */
  correctId?: string | undefined;
}

const KEYS = ["A", "B", "C", "D"];

export function Choices({ name, legend, choices, value, onChange, disabled = false, correctId }: ChoicesProps) {
  return (
    <fieldset className="opts" disabled={disabled}>
      <legend className="sr-only">{legend}</legend>
      {choices.map((choice, i) => {
        const state = correctId === undefined ? "" : choice.id === correctId ? " ok" : value === choice.id ? " ko" : "";
        return (
          <label key={choice.id} className={`opt${state}`}>
            <input
              type="radio"
              name={name}
              value={choice.id}
              checked={value === choice.id}
              onChange={() => onChange(choice.id)}
            />
            <span className="k" aria-hidden="true">
              {KEYS[i]}
            </span>
            <span>
              {choice.text}
              {state === " ok" && <span className="tag">Right answer</span>}
              {state === " ko" && <span className="tag">Your answer</span>}
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}
