// The result of a play (task T069): squares, score out of 5, speed bonus or "relaxed", time
// taken. A replay is marked "not scored". A finished daily offers the share card (task T100).

import { useEffect, useState } from "react";
import { ApiError, type ApiClient, type PlayState } from "../api/client";
import { ChallengeLink } from "../components/ChallengeLink";
import { Link } from "../components/Link";
import { ShareCard } from "../components/ShareCard";
import { Squares } from "../components/Squares";
import { formatSeconds } from "../components/Timer";
import { DECK_ORDER, deckName, LEVEL_NAMES } from "../decks";
import { streak } from "../progress/streak";
import type { Progress } from "../storage";

export interface ResultProps {
  client: ApiClient;
  playId: string | null;
  /** Local progress, for the streak on the share card. */
  progress: Progress;
}

type State = { status: "loading" } | { status: "ready"; play: PlayState } | { status: "failed"; message: string };

export function formatScore(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function Result({ client, playId, progress }: ResultProps) {
  const [state, setState] = useState<State>(
    playId ? { status: "loading" } : { status: "failed", message: "No result to show." },
  );
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!playId) return;
    let current = true;
    client
      .getPlay(playId)
      .then((play) => {
        if (current) setState({ status: "ready", play });
      })
      .catch((err: unknown) => {
        if (!current) return;
        const message =
          err instanceof ApiError && !err.serviceDown ? "No result to show." : "The game is not reachable right now.";
        setState({ status: "failed", message });
      });
    return () => {
      current = false;
    };
  }, [client, playId, attempt]);

  if (state.status === "loading") return <p aria-live="polite">Loading your result...</p>;
  if (state.status === "failed") {
    return (
      <section className="card" role="alert">
        <p>{state.message}</p>
        <div className="row">
          {playId && (
            <button
              type="button"
              className="btn"
              onClick={() => {
                setState({ status: "loading" });
                setAttempt((n) => n + 1);
              }}
            >
              Try again
            </button>
          )}
          <Link href="/" className="btn ghost">
            Back to today
          </Link>
        </div>
      </section>
    );
  }

  const { play } = state;
  const replay = play.mode === "replay";
  const decks = DECK_ORDER[play.level].map(deckName);
  const levelName = LEVEL_NAMES[play.level];

  const time = formatSeconds((play.elapsedMs ?? 0) / 1000);
  return (
    <div className="split">
      <section className="island" aria-labelledby="result-title">
        <span className="eyebrow">
          {replay ? "Replay" : "Daily"} #{play.gameNumber} · {play.date} · {levelName}
          {replay ? " · not scored" : ""}
        </span>
        <h1 id="result-title" className="text-3xl">
          {play.finished ? "Your result" : "Not finished yet"}
        </h1>
        <Squares grades={play.grades} decks={decks} label="Your answers, question by question" large />
        <div className="score">
          <div className="big">{formatScore(play.score)}/5</div>
          <div className="lab">
            score{replay ? " (not scored)" : ""} ·{" "}
            {play.relaxed ? "relaxed, no bonus" : `speed bonus +${formatScore(play.bonus)}`} · time {time}
          </div>
        </div>
        {!play.finished && (
          <div className="row">
            <Link href={replay ? "/play?mode=replay" : "/play"} className="btn big">
              Continue
            </Link>
          </div>
        )}
      </section>

      <div className="stack">
        {play.finished && !replay && (
          <div className="card">
            <ShareCard
              gameNumber={play.gameNumber}
              level={play.level}
              grades={play.grades}
              score={play.score}
              bonus={play.bonus}
              relaxed={play.relaxed}
              elapsedMs={play.elapsedMs ?? 0}
              streak={streak(Object.keys(progress.days[play.level]), play.date).current}
              address={window.location.host}
            />
          </div>
        )}
        {play.finished && !replay && (
          <div className="card">
            <ChallengeLink client={client} playId={play.playId} />
          </div>
        )}
        <nav className="row" aria-label="What next">
          {play.finished && !replay && <Link href="/play?mode=replay">Replay (not scored)</Link>}
          <Link href="/">Back to today</Link>
        </nav>
      </div>
    </div>
  );
}

