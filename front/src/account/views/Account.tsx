// The signed-in account page: this browser joined to the account (US1), passkeys (US2).

import { useCallback, useEffect, useState } from "react";
import { Link } from "../../components/Link";
import type { Progress } from "../../storage";
import { AccountApiError } from "../api";
import { SignInError, type Cognito, type PasskeyInfo } from "../cognito";
import { joinAccount } from "../join";
import { createPasskey, passkeysSupported } from "../passkeys";
import type { Runtime } from "../runtime";
import type { Session } from "../session";
import { SYNC_KEY } from "../sync";
import { DeleteAccount } from "./DeleteAccount";

export interface PasskeyMaker {
  supported: () => boolean;
  create: (options: Record<string, unknown>) => Promise<Record<string, unknown>>;
}

const BROWSER: PasskeyMaker = { supported: passkeysSupported, create: createPasskey };

export interface AccountProps {
  runtime: Runtime;
  current: () => Progress;
  replace: (progress: Progress) => void;
  /** The account is gone (deleted): the page shows so and the app forgets the session. */
  onGone?: () => void;
  /** Sign out on this browser (US6); resolves once this browser has forgotten the account. */
  onSignOut?: () => Promise<void>;
  passkeys?: PasskeyMaker;
}

type Joining = { state: "working" } | { state: "done"; created: boolean; combined: boolean } | { state: "failed"; message: string };

function remember(version: number) {
  try {
    window.localStorage.setItem(SYNC_KEY, JSON.stringify({ version, pending: false }));
  } catch {
    // The next sync starts from version 0 and merges: nothing is lost.
  }
}

type Done = Extract<Joining, { state: "done" }>;

// One join at a time per page, even if the view mounts twice (React's development mode does).
let inFlight: Promise<Done> | null = null;

function joinOnce(api: Runtime["api"], current: () => Progress, replace: (p: Progress) => void): Promise<Done> {
  inFlight ??= (async (): Promise<Done> => {
    const me = await api.me();
    if (me && me.primaryPlayerId === current().playerId) return { state: "done", created: false, combined: false };
    const joined = await joinAccount(api, current, replace);
    remember(joined.version);
    return { state: "done", created: joined.created, combined: joined.combined };
  })().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

/** Make sure this browser is the account's (after sign-in, or if that was cut short). */
function useJoin({ api }: Runtime, current: () => Progress, replace: (p: Progress) => void): Joining {
  const [joining, setJoining] = useState<Joining>({ state: "working" });
  useEffect(() => {
    let live = true;
    joinOnce(api, current, replace).then(
      (result) => {
        if (live) setJoining(result);
      },
      (error: unknown) => {
        if (!live) return;
        const message =
          error instanceof AccountApiError && error.code === "conflict"
            ? "This browser already belongs to another account."
            : error instanceof AccountApiError && error.code === "deleting"
              ? "This account is being deleted."
              : "Your account could not be reached. Your progress is safe in this browser. Try again later.";
        setJoining({ state: "failed", message });
      },
    );
    return () => {
      live = false;
    };
  }, [api, current, replace]);
  return joining;
}

export function Account({ runtime, current, replace, onGone = () => undefined, onSignOut, passkeys = BROWSER }: AccountProps) {
  const { cognito, session } = runtime;
  const joining = useJoin(runtime, current, replace);
  const [leaving, setLeaving] = useState(false);
  const leave = () => {
    if (!onSignOut || leaving) return;
    setLeaving(true);
    void onSignOut();
  };
  return (
    <>
      <section className="card narrow" aria-busy={joining.state === "working"}>
        <h1 className="text-3xl">Your account</h1>
        <p>{session.email() ? `Signed in as ${session.email()}.` : "You are signed in."}</p>
        {joining.state === "working" && <p role="status">Saving your progress to your account…</p>}
        {joining.state === "done" && (
          <p role="status">
            {joining.combined
              ? "We added this browser's games to your account. Each day counts once."
              : "Your streak and progress are saved to your account. Sign in on another device to pick them up."}
          </p>
        )}
        {joining.state === "failed" && (
          <p className="form-error" role="alert">
            {joining.message}
          </p>
        )}
        <div className="row">
          <Link href="/" className="btn">
            Go to today's set
          </Link>
          {onSignOut && (
            <button type="button" className="btn ghost" onClick={leave} disabled={leaving} aria-disabled={leaving}>
              {leaving ? "Signing out…" : "Sign out"}
            </button>
          )}
        </div>
      </section>
      {passkeys.supported() && <Passkeys cognito={cognito} session={session} maker={passkeys} />}
      <DeleteAccount api={runtime.api} onDeleted={onGone} />
    </>
  );
}

function Passkeys({ cognito, session, maker }: { cognito: Cognito; session: Session; maker: PasskeyMaker }) {
  const [list, setList] = useState<PasskeyInfo[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const withToken = useCallback(
    async <T,>(work: (token: string) => Promise<T>): Promise<T | null> => {
      const token = await session.accessToken();
      return token ? work(token) : null;
    },
    [session],
  );

  const [version, setVersion] = useState(0);
  const reload = () => setVersion((v) => v + 1);

  useEffect(() => {
    let live = true;
    withToken((t) => cognito.listPasskeys(t)).then(
      (found) => {
        if (live) setList(found ?? []);
      },
      () => {
        if (!live) return;
        setList([]);
        setError(new SignInError("unavailable").message);
      },
    );
    return () => {
      live = false;
    };
  }, [cognito, withToken, version]);

  async function add() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      await withToken(async (token) => {
        const options = await cognito.startRegistration(token);
        let credential: Record<string, unknown>;
        try {
          credential = await maker.create(options);
        } catch {
          throw new Error("cancelled");
        }
        await cognito.completeRegistration(token, credential);
      });
      setDone("Passkey added. Next time, sign in with it instead of a code.");
      reload();
    } catch (failure) {
      setError(
        failure instanceof SignInError ? failure.message : "No passkey was added. You can try again, or keep using e-mail codes.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(key: PasskeyInfo) {
    setError(null);
    setDone(null);
    try {
      await withToken((token) => cognito.removePasskey(token, key.id));
      setDone("Passkey removed.");
      reload();
    } catch (failure) {
      setError(failure instanceof SignInError ? failure.message : new SignInError("unknown").message);
    }
  }

  return (
    <section className="card narrow" aria-labelledby="passkeys-title">
      <h2 id="passkeys-title" className="text-2xl">
        Passkeys
      </h2>
      <p>Sign in with your face, your fingerprint or your device's screen lock, without waiting for an e-mail.</p>
      {list && list.length > 0 && (
        <ul className="passkeys">
          {list.map((key) => (
            <li key={key.id}>
              <span>
                {key.name}
                {key.createdAt !== null && (
                  <span className="muted"> · added {new Date(key.createdAt).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</span>
                )}
              </span>
              <button type="button" className="link-btn" aria-label={`Remove ${key.name}`} onClick={() => void remove(key)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {done && <p role="status">{done}</p>}
      <div>
        <button type="button" className="btn ghost" onClick={() => void add()} disabled={busy || list === null}>
          {busy ? "Adding…" : "Add a passkey"}
        </button>
      </div>
    </section>
  );
}
