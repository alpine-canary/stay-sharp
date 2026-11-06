// The /account page: the only entry into the account code, loaded on demand (task T218,
// research A9). Nothing here is in the first-screen bundle.
//
// Order (FR-116): the age question, then the e-mail and code, then the account.

import { useEffect, useMemo, useState } from "react";
import { Link } from "../components/Link";
import { createCognito, loadAuthConfig, type AuthConfig, type Cognito } from "./cognito";
import { createSession, type Session } from "./session";
import { AgeQuestion } from "./views/AgeQuestion";
import { SignIn } from "./views/SignIn";

export interface AccountDeps {
  loadConfig?: () => Promise<AuthConfig | null>;
  makeCognito?: (config: AuthConfig) => Cognito;
  makeSession?: (cognito: Cognito) => Session;
}

function browserSession(cognito: Cognito): Session {
  const safe = (get: () => Storage): Storage | null => {
    try {
      return get();
    } catch {
      return null;
    }
  };
  return createSession({
    session: safe(() => window.sessionStorage),
    local: safe(() => window.localStorage),
    refresh: (token) => cognito.refresh(token),
  });
}

export default function AccountPage({
  loadConfig = loadAuthConfig,
  makeCognito = (config) => createCognito(config),
  makeSession = browserSession,
}: AccountDeps) {
  const [config, setConfig] = useState<AuthConfig | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    void loadConfig().then((found) => {
      if (live) setConfig(found);
    });
    return () => {
      live = false;
    };
  }, [loadConfig]);

  if (config === undefined) return <Loading />;
  if (config === null) return <SignInUnavailable />;
  return <Account cognito={makeCognito(config)} makeSession={makeSession} />;
}

function Account({ cognito, makeSession }: { cognito: Cognito; makeSession: (c: Cognito) => Session }) {
  const session = useMemo(() => makeSession(cognito), [cognito, makeSession]);
  const [step, setStep] = useState<"age" | "sign-in" | "signed-in">(() => (session.signedIn() ? "signed-in" : "age"));

  if (step === "age") return <AgeQuestion onAdult={() => setStep("sign-in")} />;
  if (step === "sign-in") {
    return (
      <SignIn
        cognito={cognito}
        onSignedIn={(tokens, keep) => {
          session.set(tokens, keep);
          setStep("signed-in");
        }}
      />
    );
  }
  return (
    <section className="card narrow">
      <h1 className="text-3xl">Your account</h1>
      <p>Signed in as {session.email() ?? "you"}.</p>
      <p>
        <Link href="/">Go to today's set</Link>
      </p>
    </section>
  );
}

/** Same as the prerendered first screen (AccountLoading in App.tsx). */
function Loading() {
  return (
    <section className="card narrow" aria-busy="true">
      <h1 className="text-3xl">Account</h1>
      <p>Loading…</p>
    </section>
  );
}

function SignInUnavailable() {
  return (
    <section className="card narrow">
      <h1 className="text-3xl">Sign-in is not available right now</h1>
      <p>You can keep playing: your streak stays on this device. Try again later.</p>
      <p>
        <Link href="/">Go to today's set</Link>
      </p>
    </section>
  );
}
