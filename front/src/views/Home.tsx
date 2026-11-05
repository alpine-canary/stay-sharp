// Home (task T070): level choice, today's game number from /today, play or see today's result,
// "not ready yet" and service-down states with a retry.

import { useEffect, useState } from "react";
import { ApiError, type ApiClient, type Today } from "../api/client";
import { Link } from "../components/Link";
import { DECK_ORDER, deckName } from "../decks";
import type { Level, Progress } from "../storage";

const LEVEL_LABELS: Record<Level, string> = { senior: "Senior", starter: "Starter (12+)" };

type TodayState = { status: "loading" } | { status: "ready"; today: Today } | { status: "down"; message: string };

export interface HomeProps {
  client: ApiClient;
  progress: Progress;
  onLevel: (level: Level) => void;
  onRelaxed: (relaxed: boolean) => void;
}

export function Home({ client, progress, onLevel, onRelaxed }: HomeProps) {
  const [today, setToday] = useState<TodayState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    client
      .today()
      .then((value) => {
        if (current) setToday({ status: "ready", today: value });
      })
      .catch((error: unknown) => {
        const message =
          error instanceof ApiError && !error.serviceDown ? error.message : "The game is not reachable right now.";
        if (current) setToday({ status: "down", message });
      });
    return () => {
      current = false;
    };
  }, [client, attempt]);

  const retry = () => {
    setToday({ status: "loading" });
    setAttempt((n) => n + 1);
  };

  const level = progress.level;
  const date = today.status === "ready" ? today.today.date : null;
  const ready = today.status === "ready" && level !== null && today.today.levels.some((l) => l.level === level && l.ready);
  const done = level && date ? progress.days[level][date] : undefined;

  return (
    <>
      <section className="card" aria-labelledby="home-title">
        <p className="eyebrow">
          {today.status === "ready" ? `Daily · ${today.today.date}` : "Daily"}
          {level ? ` · ${LEVEL_LABELS[level]}` : ""}
        </p>
        <h1 id="home-title" className="text-4xl">
          {today.status === "ready" ? `Today's set #${today.today.gameNumber}` : "Today's set"}
        </h1>
        <p className="text-lg">Agents write the code. Don't lose your touch.</p>

        <fieldset className="levels">
          <legend className="eyebrow">Level</legend>
          {(Object.keys(LEVEL_LABELS) as Level[]).map((value) => (
            <label key={value} className="pill">
              <input
                type="radio"
                name="level"
                value={value}
                checked={level === value}
                onChange={() => onLevel(value)}
              />
              {LEVEL_LABELS[value]}
            </label>
          ))}
        </fieldset>

        {level && (
          <ol className="decks" aria-label="Today's five questions">
            {DECK_ORDER[level].map((deck, i) => (
              <li key={deck}>
                <span className="n">{i + 1}</span>
                <span>{deckName(deck)}</span>
              </li>
            ))}
          </ol>
        )}

        {today.status === "loading" && <p aria-live="polite">Loading today's set...</p>}
        {today.status === "down" && (
          <div role="alert" className="notice">
            <p>{today.message}</p>
            <div className="row">
              <button type="button" className="btn ghost" onClick={retry}>
                Try again
              </button>
            </div>
          </div>
        )}
        {today.status === "ready" && level === null && <p className="hint">Choose a level to start.</p>}
        {today.status === "ready" && level !== null && !ready && (
          <p role="status">Today's set is not ready yet. Please come back a little later.</p>
        )}

        {ready && level && date && (
          <div className="row">
            {done ? (
              <>
                <Link href={`/result?play=${date}.${level}.daily`} className="btn">
                  See today's result
                </Link>
                <Link href="/play?mode=replay" className="btn ghost">
                  Replay (not scored)
                </Link>
              </>
            ) : (
              <>
                <Link href="/play" className="btn">
                  Play today's set
                </Link>
                <span className="hint">5 questions · about 5 minutes</span>
              </>
            )}
          </div>
        )}

        <label className="check">
          <input type="checkbox" checked={progress.relaxed} onChange={(e) => onRelaxed(e.target.checked)} />
          Relaxed mode: no timer, no speed bonus
        </label>
      </section>
      <p className="foot">No account. Your progress is saved in this browser only.</p>
    </>
  );
}
