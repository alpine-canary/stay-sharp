// E-mail, then the code (task T216, FR-104, FR-106; WCAG 2.2 accessible authentication):
// no password, no puzzle, the code can be pasted or filled by the device, no time pressure
// beyond the code's own 10 minutes, and errors never say whether an e-mail has an account.

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { SignInError, type Cognito, type Pending, type Tokens } from "../cognito";

export interface SignInProps {
  cognito: Cognito;
  onSignedIn: (tokens: Tokens, keep: boolean) => void;
}

function message(error: unknown): string {
  return error instanceof SignInError ? error.message : new SignInError("unknown").message;
}

export function SignIn({ cognito, onSignedIn }: SignInProps) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [keep, setKeep] = useState(false);
  return pending ? (
    <CodeStep
      cognito={cognito}
      pending={pending}
      onPending={setPending}
      onBack={() => setPending(null)}
      onSignedIn={(tokens) => onSignedIn(tokens, keep)}
    />
  ) : (
    <EmailStep cognito={cognito} keep={keep} onKeep={setKeep} onPending={setPending} />
  );
}

function EmailStep({
  cognito,
  keep,
  onKeep,
  onPending,
}: {
  cognito: Cognito;
  keep: boolean;
  onKeep: (keep: boolean) => void;
  onPending: (pending: Pending) => void;
}) {
  const id = useId();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onPending(await cognito.start(email));
    } catch (failure) {
      setError(message(failure));
      setBusy(false);
    }
  }

  return (
    <form className="card narrow form" onSubmit={submit} noValidate aria-busy={busy}>
      <h1 className="text-3xl">Your e-mail</h1>
      <p>We send you a code to sign in. There is no password.</p>
      <div className="field">
        <label htmlFor={`${id}-email`}>E-mail address</label>
        <input
          id={`${id}-email`}
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          spellCheck={false}
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
        />
      </div>
      <label className="check">
        <input type="checkbox" checked={keep} onChange={(e) => onKeep(e.target.checked)} />
        Keep me signed in on this device
      </label>
      {error && (
        <p id={`${id}-error`} className="form-error" role="alert">
          {error}
        </p>
      )}
      <div>
        <button type="submit" className="btn" disabled={busy}>
          {busy ? "Sending…" : "Send me a code"}
        </button>
      </div>
    </form>
  );
}

function CodeStep({
  cognito,
  pending,
  onPending,
  onBack,
  onSignedIn,
}: {
  cognito: Cognito;
  pending: Pending;
  onPending: (pending: Pending) => void;
  onBack: () => void;
  onSignedIn: (tokens: Tokens) => void;
}) {
  const id = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    heading.current?.focus();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSignedIn(await cognito.answer(pending, code));
    } catch (failure) {
      setError(message(failure));
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    setSent(false);
    try {
      onPending(await cognito.resend(pending));
      setSent(true);
      setCode("");
    } catch (failure) {
      setError(message(failure));
    }
  }

  return (
    <form className="card narrow form" onSubmit={submit} noValidate aria-busy={busy}>
      <h1 className="text-3xl" ref={heading} tabIndex={-1}>
        Check your e-mail
      </h1>
      <p>
        We sent a code to <strong>{pending.email}</strong>. It works for 10 minutes.
      </p>
      <div className="field">
        <label htmlFor={`${id}-code`}>Code</label>
        <input
          id={`${id}-code`}
          name="code"
          autoComplete="one-time-code"
          inputMode="numeric"
          spellCheck={false}
          required
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
        />
      </div>
      {error && (
        <p id={`${id}-error`} className="form-error" role="alert">
          {error}
        </p>
      )}
      {sent && <p role="status">A new code is on its way.</p>}
      <div>
        <button type="submit" className="btn" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </div>
      <p className="form-links">
        <button type="button" className="link-btn" onClick={resend}>
          Send a new code
        </button>
        <button type="button" className="link-btn" onClick={onBack}>
          Use another e-mail
        </button>
      </p>
    </form>
  );
}
