// "Delete my account" (task T234, FR-114, FR-115): one confirmation, plain consequences, and the
// result only once the server has finished. Then this browser starts again as a new player.

import { useEffect, useRef, useState } from "react";
import { Link } from "../../components/Link";
import { AccountApiError, type AccountApi } from "../api";

export interface DeleteAccountProps {
  api: AccountApi;
  /** Everything is gone on the server: forget the session and the local progress. */
  onDeleted: () => void;
}

export function DeleteAccount({ api, onDeleted }: DeleteAccountProps) {
  const [step, setStep] = useState<"ask" | "confirm" | "working">("ask");
  const [error, setError] = useState<string | null>(null);
  const confirm = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (step === "confirm") confirm.current?.focus();
  }, [step]);

  async function remove() {
    setStep("working");
    setError(null);
    try {
      await api.deleteAccount();
      onDeleted();
    } catch (failure) {
      setError(
        failure instanceof AccountApiError && failure.status === 503
          ? "Deleting has started but is not finished. Please try again in a minute."
          : "Your account could not be reached. Nothing was deleted yet; please try again later.",
      );
      setStep("confirm");
    }
  }

  return (
    <section className="card narrow" aria-labelledby="delete-title" aria-busy={step === "working"}>
      {step === "ask" ? (
        <>
          <h2 id="delete-title" className="text-2xl">
            Delete my account
          </h2>
          <p>
            This deletes your account and everything kept with it: your e-mail, your games, your streak and your
            progress, on every device. It cannot be undone.
          </p>
          <div>
            <button type="button" className="btn ghost" onClick={() => setStep("confirm")}>
              Delete my account
            </button>
          </div>
        </>
      ) : (
        <>
          <h2 id="delete-title" className="text-2xl" ref={confirm} tabIndex={-1}>
            Delete your account for good?
          </h2>
          <p>Your streak and progress go too, on all your devices. You can still play without an account.</p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="actions">
            <button type="button" className="btn danger" onClick={() => void remove()} disabled={step === "working"}>
              {step === "working" ? "Deleting…" : "Yes, delete everything"}
            </button>
            <button type="button" className="btn ghost" onClick={() => setStep("ask")} disabled={step === "working"}>
              Keep my account
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export function AccountDeleted() {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  return (
    <section className="card narrow">
      <h1 className="text-3xl" ref={heading} tabIndex={-1}>
        Your account is deleted
      </h1>
      <p>Everything kept with it is gone. You can keep playing without an account.</p>
      <div className="row">
        <Link href="/" className="btn">
          Go to today's set
        </Link>
      </div>
    </section>
  );
}
