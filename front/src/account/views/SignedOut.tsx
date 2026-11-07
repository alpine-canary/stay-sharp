// After signing out (US6): this browser plays as a new anonymous player; the account keeps
// everything and comes back on sign-in.

import { useEffect, useRef } from "react";
import { Link } from "../../components/Link";

export function SignedOut() {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  return (
    <section className="card narrow">
      <h1 className="text-3xl" ref={heading} tabIndex={-1}>
        You are signed out
      </h1>
      <p>This browser no longer shows your account's progress. Your account keeps all of it: sign in again, here or on another device, to pick it up.</p>
      <div className="row">
        <Link href="/" className="btn">
          Go to today's set
        </Link>
      </div>
    </section>
  );
}
