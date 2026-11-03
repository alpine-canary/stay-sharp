// Front-end shell (task T049): one place that owns local progress, the API client and the view
// for the current path. Real views (Play, Result, Home details) arrive with Story 1.

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, createClient, type ApiClient, type Today } from "./api/client";
import { useRoute } from "./router";
import { createStore, type Level, type Notice, type Progress, type ProgressStore } from "./storage";

const LEVEL_LABELS: Record<Level, string> = { senior: "Senior", starter: "Starter (12+)" };

type TodayState = { status: "loading" } | { status: "ready"; today: Today } | { status: "down"; message: string };

export interface AppProps {
  store?: ProgressStore;
  client?: ApiClient;
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
    (next: Progress) => {
      store.save(next);
      setProgress(next);
    },
    [store],
  );

  return (
    <div className="mx-auto max-w-xl px-4 py-8">
      <header>
        <p className="text-2xl font-semibold">
          <a href="/">Stay Sharp</a>
        </p>
      </header>
      {notice && <StorageNotice notice={notice} onDismiss={() => setNotice(null)} />}
      <main id="main" className="mt-6">
        {route.view === "home" && <Home client={client} progress={progress} onLevel={(level) => update({ ...progress, level })} />}
        {route.view === "not-found" && <NotFound />}
        {route.view !== "home" && route.view !== "not-found" && <ComingSoon />}
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
    <div role="status" className="mt-4 rounded border border-amber-700 p-3">
      <p>{text}</p>
      <button type="button" className="mt-2 underline" onClick={onDismiss}>
        OK
      </button>
    </div>
  );
}

function Home({ client, progress, onLevel }: { client: ApiClient; progress: Progress; onLevel: (level: Level) => void }) {
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

  return (
    <>
      <h1 className="text-xl font-semibold">
        {today.status === "ready" ? `Today's set #${today.today.gameNumber}` : "Today's set"}
      </h1>
      {today.status === "loading" && <p aria-live="polite">Loading today's set...</p>}
      {today.status === "down" && (
        <div role="alert" className="mt-2">
          <p>{today.message}</p>
          <button type="button" className="mt-2 underline" onClick={retry}>
            Try again
          </button>
        </div>
      )}
      <fieldset className="mt-6">
        <legend className="font-semibold">Level</legend>
        {(Object.keys(LEVEL_LABELS) as Level[]).map((level) => (
          <label key={level} className="mt-2 flex items-center gap-2">
            <input
              type="radio"
              name="level"
              value={level}
              checked={progress.level === level}
              onChange={() => onLevel(level)}
            />
            {LEVEL_LABELS[level]}
          </label>
        ))}
      </fieldset>
    </>
  );
}

function NotFound() {
  return (
    <>
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-2">
        <a href="/" className="underline">
          Go to today's set
        </a>
      </p>
    </>
  );
}

function ComingSoon() {
  return <h1 className="text-xl font-semibold">Coming soon</h1>;
}
