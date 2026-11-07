// The age question itself (FR-116), in the main bundle: it is also the prerendered first screen
// of /account, so the page paints its real content before the account code loads. An answer
// given before that code arrives is kept (takeEarlyAnswer) and acted on as soon as it does.

export type AgeAnswer = "adult" | "under16";

let early: AgeAnswer | null = null;
const listeners = new Set<() => void>();

function setEarly(answer: AgeAnswer | null): void {
  early = answer;
  for (const listener of listeners) listener();
}

/** The answer given on the first screen; null when there was none (useSyncExternalStore). */
export function earlyAnswer(): AgeAnswer | null {
  return early;
}

export function subscribeEarlyAnswer(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Forget it when the player leaves /account (a later visit asks again). */
export function clearEarlyAnswer(): void {
  if (early !== null) setEarly(null);
}

export function AgeAsk({ onAnswer = setEarly }: { onAnswer?: (answer: AgeAnswer) => void }) {
  return (
    <section className="card narrow">
      <h1 className="text-3xl">Are you 16 or older?</h1>
      <p>An account keeps your streak on all your devices. Accounts are for players aged 16 and over.</p>
      <div className="actions">
        <button type="button" className="btn" onClick={() => onAnswer("adult")}>
          Yes, I am 16 or older
        </button>
        <button type="button" className="btn ghost" onClick={() => onAnswer("under16")}>
          No, I am under 16
        </button>
      </div>
    </section>
  );
}
