// Home (tasks T070, T098): level choice, today's game number from /today, play or see today's
// result, "not ready yet" and service-down states with a retry, then the progress card.

import { useEffect, useState } from "react";
import { ApiError, type ApiClient, type Today } from "../api/client";
import { Link } from "../components/Link";
import { ProgressCard, zurichToday } from "../components/ProgressCard";
import { Squares } from "../components/Squares";
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

  // Senior is chosen until the player picks another level, so the first screen always has a
  // Play button (Starter is one tap away).
  const level: Level = progress.level ?? "senior";
  useEffect(() => {
    if (progress.level === null) onLevel("senior");
  }, [progress.level, onLevel]);
  const date = today.status === "ready" ? today.today.date : null;
  const ready = today.status === "ready" && today.today.levels.some((l) => l.level === level && l.ready);
  const done = date ? progress.days[level][date] : undefined;
  const played = Object.keys(progress.days[level]).length > 0;

  return (
    <>
      <div className="hero">
        <h1>Stay Sharp</h1>
        <p className="lead">
          A daily 5-minute game for developers. Agents write more of the code; keep the judgement that is
          left to you in use.
        </p>
      </div>

      <div className="split">
        <section className="card" aria-labelledby="home-title">
          <p className="eyebrow">
            {today.status === "ready" ? `Daily · ${today.today.date}` : "Daily"} · {LEVEL_LABELS[level]}
          </p>
          <h2 id="home-title" className="text-4xl md:text-5xl">
            {today.status === "ready" ? `Today's set #${today.today.gameNumber}` : "Today's set"}
          </h2>

          <ol className="chips" aria-label="Today's five questions">
            {DECK_ORDER[level].map((deck, i) => (
              <li key={deck}>
                <span className="n">{i + 1}</span>
                <span>{deckName(deck)}</span>
              </li>
            ))}
          </ol>

          <fieldset className="seg">
            <legend className="eyebrow">Level</legend>
            <div className="opts-row">
              {(Object.keys(LEVEL_LABELS) as Level[]).map((value) => (
                <label key={value}>
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
            </div>
          </fieldset>

          <label className="check">
            <input type="checkbox" checked={progress.relaxed} onChange={(e) => onRelaxed(e.target.checked)} />
            Relaxed mode: no timer, no speed bonus
          </label>

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
          {today.status === "ready" && !ready && (
            <p role="status">Today's set is not ready yet. Please come back a little later.</p>
          )}

          {ready && date && (
            <div className="row">
              {done ? (
                <>
                  <Link href={`/result?play=${date}.${level}.daily`} className="btn big">
                    See today's result
                  </Link>
                  <Link href="/play?mode=replay" className="btn ghost">
                    Replay (not scored)
                  </Link>
                </>
              ) : (
                <>
                  <Link href="/play" className="btn big">
                    Play today's set
                  </Link>
                  <span className="hint">5 questions · about 5 minutes</span>
                </>
              )}
            </div>
          )}
        </section>

        {played ? (
          <ProgressCard progress={progress} level={level} today={date ?? zurichToday()} />
        ) : (
          <aside className="island" aria-labelledby="how-title">
            <p className="eyebrow">How it plays</p>
            <h2 id="how-title" className="text-3xl">
              Five questions, five minutes
            </h2>
            <ol className="steps">
              <li>Spot the bug, improve working code, reason about a failure, name a tool, follow the week in AI.</li>
              <li>After each answer, a short explanation. Answer fast for a small speed bonus, or play relaxed.</li>
              <li>Share your squares without spoilers, keep a streak, and challenge a colleague to the same set.</li>
            </ol>
            <Squares grades={[1, 1, 0.5, 1, 0]} label="Example result" />
            <p className="hint">No account. Your progress stays in this browser.</p>
          </aside>
        )}
      </div>

      <section className="card" aria-labelledby="practice-title">
        <div className="qhead">
          <div className="grid gap-1">
            <h2 id="practice-title" className="text-2xl">
              Practice
            </h2>
            <p className="hint">Past questions, by deck. The ones you miss come back sooner. No timer, no streak.</p>
          </div>
          <Link href="/practice" className="btn ghost">
            Practise past questions
          </Link>
        </div>
      </section>
    </>
  );
}
