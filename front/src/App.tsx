// Front-end shell: one place that owns local progress, the API client and the view for the
// current path (tasks T049, T068 to T070).

import { useCallback, useMemo, useState } from "react";
import { createClient, type ApiClient, type PlayState } from "./api/client";
import { Link } from "./components/Link";
import { levelOfDeck } from "./decks";
import { navigate, useRoute } from "./router";
import {
  createStore,
  recordAnswer,
  recordDay,
  type Level,
  type Notice,
  type Progress,
  type ProgressStore,
} from "./storage";
import { Challenge } from "./views/Challenge";
import { Home } from "./views/Home";
import { Play } from "./views/Play";
import { Result } from "./views/Result";

export interface AppProps {
  store?: ProgressStore;
  client?: ApiClient;
}

function search(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name);
}

export function App({ store: givenStore, client: givenClient }: AppProps = {}) {
  const store = useMemo(() => givenStore ?? createStore(), [givenStore]);
  const [{ progress: initial, notice: initialNotice }] = useState(() => store.load());
  const [progress, setProgress] = useState<Progress>(initial);
  const [notice, setNotice] = useState<Notice>(initialNotice);
  const client = useMemo(
    () => givenClient ?? createClient({ playerId: () => store.load().progress.playerId }),
    [givenClient, store],
  );
  const route = useRoute();

  const update = useCallback(
    (change: (p: Progress) => Progress) => {
      setProgress((current) => {
        const next = change(current);
        store.save(next);
        return next;
      });
    },
    [store],
  );

  const finished = useCallback(
    (play: PlayState) => {
      // Keyed by the play's server date: a play finished after midnight counts for its own day.
      if (play.mode === "daily" && play.finished) update((p) => recordDay(p, play));
      navigate(`/result?play=${play.playId}`);
      window.scrollTo(0, 0);
    },
    [update],
  );

  const answered = useCallback(
    (level: Level, playMode: "daily" | "replay", deck: string, grade: number, duplicate: boolean) => {
      // Replays are not scored, so they do not count in the skill view either.
      if (playMode === "daily") update((p) => recordAnswer(p, { level, deck, grade, duplicate }));
    },
    [update],
  );

  const challengeFinished = useCallback(
    (play: PlayState) => {
      if (play.mode === "daily" && play.finished) update((p) => recordDay(p, play));
    },
    [update],
  );

  const mode = search("mode") === "replay" ? "replay" : "daily";

  return (
    <div className="wrap">
      <header className="top">
        <Link href="/" className="mark" aria-label="Stay Sharp, home">
          <i aria-hidden="true" />
          Stay Sharp
        </Link>
      </header>
      {notice && <StorageNotice notice={notice} onDismiss={() => setNotice(null)} />}
      <main id="main" className="grid gap-5">
        {route.view === "home" && (
          <Home
            client={client}
            progress={progress}
            onLevel={(level: Level) => update((p) => ({ ...p, level }))}
            onRelaxed={(relaxed) => update((p) => ({ ...p, relaxed }))}
          />
        )}
        {route.view === "play" &&
          (progress.level ? (
            <Play
              key={`${progress.level}-${mode}`}
              client={client}
              level={progress.level}
              mode={mode}
              relaxed={progress.relaxed}
              onFinished={finished}
              onAnswered={({ mode: playMode, deck, grade, duplicate }) => {
                if (progress.level) answered(progress.level, playMode, deck, grade, duplicate);
              }}
            />
          ) : (
            <ChooseLevelFirst />
          ))}
        {route.view === "result" && <Result key={search("play")} client={client} playId={search("play")} progress={progress} />}
        {route.view === "challenge" && route.challengeId && (
          <Challenge
            key={route.challengeId}
            client={client}
            challengeId={route.challengeId}
            relaxed={progress.relaxed}
            onFinished={challengeFinished}
            onAnswered={({ mode: playMode, deck, grade, duplicate }) => {
              // The level of a challenge is the challenge's, whatever level this browser chose.
              answered(levelOfDeck(deck), playMode, deck, grade, duplicate);
            }}
          />
        )}
        {route.view === "not-found" && <NotFound />}
        {(route.view === "practice" || route.view === "privacy") && <ComingSoon />}
      </main>
    </div>
  );
}

function StorageNotice({ notice, onDismiss }: { notice: Exclude<Notice, null>; onDismiss: () => void }) {
  const text =
    notice === "reset"
      ? "Your saved progress on this browser could not be read, so it was reset."
      : "This browser does not let the site save your progress, so it will be lost when you close the page.";
  return (
    <div role="status" className="notice">
      <p>{text}</p>
      <div>
        <button type="button" className="link-btn" onClick={onDismiss}>
          OK
        </button>
      </div>
    </div>
  );
}

function ChooseLevelFirst() {
  return (
    <section className="card">
      <h1 className="text-2xl">Choose a level first</h1>
      <p>
        <Link href="/">Go to today's set</Link> and pick Senior or Starter.
      </p>
    </section>
  );
}

function NotFound() {
  return (
    <section className="card">
      <h1 className="text-2xl">Page not found</h1>
      <p>
        <Link href="/">Go to today's set</Link>
      </p>
    </section>
  );
}

function ComingSoon() {
  return (
    <section className="card">
      <h1 className="text-2xl">Coming soon</h1>
      <p>
        <Link href="/">Go to today's set</Link>
      </p>
    </section>
  );
}
