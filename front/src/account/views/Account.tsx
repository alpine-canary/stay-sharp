// The signed-in account page (US2 passkeys now; adopt, sync, delete and sign out come with
// their stories).

import { useCallback, useEffect, useState } from "react";
import { Link } from "../../components/Link";
import { SignInError, type Cognito, type PasskeyInfo } from "../cognito";
import { createPasskey, passkeysSupported } from "../passkeys";
import type { Session } from "../session";

export interface PasskeyMaker {
  supported: () => boolean;
  create: (options: Record<string, unknown>) => Promise<Record<string, unknown>>;
}

const BROWSER: PasskeyMaker = { supported: passkeysSupported, create: createPasskey };

export interface AccountProps {
  cognito: Cognito;
  session: Session;
  passkeys?: PasskeyMaker;
}

export function Account({ cognito, session, passkeys = BROWSER }: AccountProps) {
  return (
    <>
      <section className="card narrow">
        <h1 className="text-3xl">Your account</h1>
        <p>Signed in as {session.email() ?? "you"}.</p>
        <p>
          <Link href="/">Go to today's set</Link>
        </p>
      </section>
      {passkeys.supported() && <Passkeys cognito={cognito} session={session} maker={passkeys} />}
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
