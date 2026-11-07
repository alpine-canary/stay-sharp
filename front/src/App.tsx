// Front-end shell: one place that owns local progress, the API client and the view for the
// current path (tasks T049, T068 to T070).

import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { signedInHint } from "./accountHint";
import type { Live } from "./account/live";
import { createClient, type ApiClient, type PlayState } from "./api/client";
import { AgeAsk, clearEarlyAnswer } from "./components/AgeAsk";
import { Link } from "./components/Link";
import { ShareSite } from "./components/ShareSite";
import { navigate, useRoute } from "./router";
import {
  createStore,
  recordAnswer,
  recordDay,
  recordPracticeAnswer,
  type Level,
  type Notice,
  type Progress,
  type ProgressStore,
} from "./storage";
import { Challenge } from "./views/Challenge";
import { Home } from "./views/Home";
import { Play } from "./views/Play";
import { Practice } from "./views/Practice";
import { Privacy } from "./views/Privacy";
import { Result } from "./views/Result";

// The account code is its own chunk, loaded only on /account (research A9). The fallback is
// also the prerendered first screen of the page (the age question); it stays out of that chunk.
const AccountPage = lazy(() => import("./account/AccountPage"));

function AccountLoading() {
  // A new visitor (and the prerendered page) sees the age question at once; a signed-in browser
  // waits for its account.
  if (signedInHint()) {
    return (
      <section className="card narrow" aria-busy="true">
        <h1 className="text-3xl">Account</h1>
        <p>Loading…</p>
      </section>
    );
  }
  return <AgeAsk />;
}

export interface AppProps {
  store?: ProgressStore;
  client?: ApiClient;
}

function search(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name);
}

export function App({ store: givenStore, client: givenClient }: AppProps = {}) {
  const store = useMemo(() => givenStore ?? createStore(), [givenStore]);
  const [{ progress: initial, notice: initialNotice }] = useState(() =>
    store.load(),
  );
  const [progress, setProgress] = useState<Progress>(initial);
  const [notice, setNotice] = useState<Notice>(initialNotice);
  const client = useMemo(
    () =>
      givenClient ??
      createClient({ playerId: () => store.load().progress.playerId }),
    [givenClient, store],
  );
  const route = useRoute();
  // An age answer given on the first screen of /account is for that visit only.
  useEffect(() => {
    if (route.view !== "account") clearEarlyAnswer();
  }, [route.view]);

  // Signed-in browsers keep their progress in step with the account (M2). The sync code is
  // loaded only for them, after the first screen.
  const latest = useRef(progress);
  useEffect(() => {
    latest.current = progress;
  }, [progress]);
  const live = useRef<Live | null>(null);
  const [signedIn, setSignedIn] = useState(() => signedInHint());
  const current = useCallback(() => latest.current, []);
  const replace = useCallback(
    (next: Progress) => {
      latest.current = next;
      store.save(next);
      setProgress(next);
    },
    [store],
  );
  useEffect(() => {
    if (!signedIn) return;
    let stopped = false;
    void import("./account/live")
      .then((m) => m.connect(current, replace))
      .then((connected) => {
        if (stopped) connected?.stop();
        else live.current = connected;
      })
      .catch(() => undefined);
    return () => {
      stopped = true;
      live.current?.stop();
      live.current = null;
    };
  }, [signedIn, current, replace]);

  const update = useCallback(
    (change: (p: Progress) => Progress) => {
      setProgress((before) => {
        const next = change(before);
        store.save(next);
        latest.current = next;
        return next;
      });
      live.current?.changed();
    },
    [store],
  );

  const finished = useCallback(
    (play: PlayState) => {
      // Keyed by the play's server date: a play finished after midnight counts for its own day.
      if (play.mode === "daily" && play.finished)
        update((p) => recordDay(p, play));
      navigate(`/result?play=${play.playId}`);
      window.scrollTo(0, 0);
    },
    [update],
  );

  const answered = useCallback(
    (
      level: Level,
      playMode: "daily" | "replay",
      deck: string,
      grade: number,
      duplicate: boolean,
    ) => {
      // Replays are not scored, so they do not count in the skill view either.
      if (playMode === "daily")
        update((p) => recordAnswer(p, { level, deck, grade, duplicate }));
    },
    [update],
  );

  const challengeFinished = useCallback(
    (play: PlayState) => {
      if (play.mode === "daily" && play.finished)
        update((p) => recordDay(p, play));
    },
    [update],
  );

  const mode = search("mode") === "replay" ? "replay" : "daily";

  return (
    <div className="wrap">
      <header className="top">
        <Link href="/" className="mark" aria-label="Stay Sharp, home">
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="#0b1f33" />
            <path
              d="M9 16.5l4.5 4.5L23 11"
              fill="none"
              stroke="#5fd3b4"
              strokeWidth="3.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Stay Sharp
        </Link>
        <nav className="top-links" aria-label="Site">
          <Link href="/account" className="account-link">
            {/* A person icon on a phone, the word from 640 px; the name stays "Account". */}
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="8.5" r="4" fill="none" stroke="currentColor" strokeWidth="2" />
              <path d="M4.5 20.5c1.2-3.6 4.1-5.5 7.5-5.5s6.3 1.9 7.5 5.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span className="account-word">Account</span>
          </Link>
        </nav>
        <span className="by">
          by{" "}
          <a href="https://www.lumineth.com/">
            {/* Lumineth's mark, as on www.lumineth.com (white tile on the dark page). */}
            <svg className="lm" viewBox="0 0 48 48" aria-hidden="true">
              <rect className="lm-tile" width="48" height="48" rx="11" />
              <rect
                className="lm-stem"
                x="12"
                y="9"
                width="8.5"
                height="30"
                rx="4.25"
              />
              <rect
                x="12"
                y="30.5"
                width="24"
                height="8.5"
                rx="4.25"
                fill="#0E7C66"
              />
              <path
                d="M12 34.75a4.25 4.25 0 0 1 4.25-4.25h4.25V39h-4.25A4.25 4.25 0 0 1 12 34.75z"
                fill="#5FD3B4"
              />
              <rect
                x="28.8"
                y="10.8"
                width="7.4"
                height="7.4"
                rx="1.3"
                transform="rotate(45 32.5 14.5)"
                fill="#5FD3B4"
              />
            </svg>
            <span className="by-short">Lumineth</span>
            <span className="by-long">lumineth.com</span>
          </a>
        </span>
      </header>
      {notice && (
        <StorageNotice notice={notice} onDismiss={() => setNotice(null)} />
      )}
      <main id="main" className="grid gap-6 content-start">
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
                if (progress.level)
                  answered(progress.level, playMode, deck, grade, duplicate);
              }}
            />
          ) : (
            <ChooseLevelFirst />
          ))}
        {route.view === "result" && (
          <Result
            key={search("play")}
            client={client}
            playId={search("play")}
            progress={progress}
          />
        )}
        {route.view === "challenge" && route.challengeId && (
          <Challenge
            key={route.challengeId}
            client={client}
            challengeId={route.challengeId}
            relaxed={progress.relaxed}
            onFinished={challengeFinished}
            onAnswered={({ level, mode: playMode, deck, grade, duplicate }) => {
              // The level of a challenge is the challenge's, whatever level this browser chose.
              answered(level, playMode, deck, grade, duplicate);
            }}
          />
        )}
        {route.view === "not-found" && <NotFound />}
        {route.view === "practice" &&
          (progress.level ? (
            <Practice
              key={progress.level}
              client={client}
              level={progress.level}
              practice={progress.practice[progress.level]}
              onAnswered={(answer) => {
                const level = progress.level;
                // Boxes only: practice never touches the streak, the freeze or the skill view.
                if (level)
                  update((p) => recordPracticeAnswer(p, level, answer));
              }}
            />
          ) : (
            <ChooseLevelFirst />
          ))}
        {route.view === "privacy" && <Privacy />}
        {route.view === "account" && (
          <Suspense fallback={<AccountLoading />}>
            <AccountPage current={current} replace={replace} onSignedIn={() => setSignedIn(true)} onSignedOut={() => setSignedIn(false)} />
          </Suspense>
        )}
      </main>
      <footer className="site-foot">
        <span>
          © 2026 <a href="https://www.lumineth.com/">Lumineth</a>
        </span>
        <span className="foot-links">
          <ShareSite />
          <nav aria-label="Legal">
            <Link href="/privacy">Privacy</Link>
          </nav>
        </span>
      </footer>
    </div>
  );
}

function StorageNotice({
  notice,
  onDismiss,
}: {
  notice: Exclude<Notice, null>;
  onDismiss: () => void;
}) {
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
    <section className="card narrow">
      <h1 className="text-3xl">Choose a level first</h1>
      <p>
        <Link href="/">Go to today's set</Link> and pick Starter, Junior or
        Senior.
      </p>
    </section>
  );
}

function NotFound() {
  return (
    <section className="card narrow">
      <h1 className="text-3xl">Page not found</h1>
      <p>
        <Link href="/">Go to today's set</Link>
      </p>
    </section>
  );
}
