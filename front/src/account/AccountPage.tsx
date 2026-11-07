// The /account page: the only entry into the account code, loaded on demand (task T218,
// research A9). Nothing here is in the first-screen bundle.
//
// Order (FR-116): the age question, then the e-mail and code, then the account.

import { useEffect, useMemo, useState } from "react";
import { Link } from "../components/Link";
import { freshProgress, type Progress } from "../storage";
import { loadAuthConfig, type AuthConfig } from "./cognito";
import { localStorageOrNull, makeRuntime, type Runtime } from "./runtime";
import { signOut } from "./signOut";
import { AgeQuestion } from "./views/AgeQuestion";
import { Account as SignedIn } from "./views/Account";
import { SignIn } from "./views/SignIn";
import { AccountDeleted } from "./views/DeleteAccount";
import { SignedOut } from "./views/SignedOut";
import { SYNC_KEY } from "./sync";

export interface AccountPageProps {
  /** This browser's progress, and how to replace it (adopting the account). */
  current: () => Progress;
  replace: (progress: Progress) => void;
  /** Tell the app that this browser is now signed in (it starts keeping progress in step). */
  onSignedIn: () => void;
  /** Tell the app that this browser is signed out (account deleted, or sign-out). */
  onSignedOut: () => void;
  loadConfig?: () => Promise<AuthConfig | null>;
  makeRuntimeFor?: (config: AuthConfig) => Runtime;
}

const defaultRuntime = (config: AuthConfig) => makeRuntime(config);

export default function AccountPage({
  current,
  replace,
  onSignedIn,
  onSignedOut,
  loadConfig = loadAuthConfig,
  makeRuntimeFor = defaultRuntime,
}: AccountPageProps) {
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
  return <Account config={config} makeRuntimeFor={makeRuntimeFor} current={current} replace={replace} onSignedIn={onSignedIn} onSignedOut={onSignedOut} />;
}

function Account({
  config,
  makeRuntimeFor,
  current,
  replace,
  onSignedIn,
  onSignedOut,
}: {
  config: AuthConfig;
  makeRuntimeFor: (config: AuthConfig) => Runtime;
  current: () => Progress;
  replace: (progress: Progress) => void;
  onSignedIn: () => void;
  onSignedOut: () => void;
}) {
  const runtime = useMemo(() => makeRuntimeFor(config), [config, makeRuntimeFor]);
  const { cognito, session } = runtime;
  const [step, setStep] = useState<"age" | "sign-in" | "signed-in" | "deleted" | "signed-out">(() => (session.signedIn() ? "signed-in" : "age"));

  if (step === "age") return <AgeQuestion onAdult={() => setStep("sign-in")} />;
  if (step === "sign-in") {
    return (
      <SignIn
        cognito={cognito}
        onSignedIn={(tokens, keep) => {
          session.set(tokens, keep);
          setStep("signed-in");
          onSignedIn();
        }}
      />
    );
  }
  if (step === "deleted") return <AccountDeleted />;
  if (step === "signed-out") return <SignedOut />;
  /** A new anonymous player on this browser: nothing of the account stays here (FR-113). */
  const forget = () => {
    session.clear();
    try {
      window.localStorage.removeItem(SYNC_KEY);
    } catch {
      // Nothing to forget.
    }
    replace(freshProgress());
  };
  const gone = () => {
    forget();
    onSignedOut();
    setStep("deleted");
  };
  const leave = async () => {
    // Stop keeping progress in step first, so nothing is sent after the session ends.
    onSignedOut();
    await signOut(runtime, current, undefined, replace, localStorageOrNull());
    forget();
    setStep("signed-out");
  };
  return <SignedIn runtime={runtime} current={current} replace={replace} onGone={gone} onSignOut={leave} />;
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
      <p>You can keep playing: your streak stays in this browser. Try again later.</p>
      <p>
        <Link href="/">Go to today's set</Link>
      </p>
    </section>
  );
}
