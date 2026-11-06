// The first account screen (task T240, FR-116, clarification 2026-11-06): no account under 16.
// "No" stores nothing and sends nothing; the game stays fully playable without an account.

import { useEffect, useRef, useState } from "react";
import { Link } from "../../components/Link";

export function AgeQuestion({ onAdult }: { onAdult: () => void }) {
  const [under16, setUnder16] = useState(false);
  return under16 ? (
    <Under16 />
  ) : (
    <section className="card narrow">
      <h1 className="text-3xl">Are you 16 or older?</h1>
      <p>An account keeps your streak on all your devices. Accounts are for players aged 16 and over.</p>
      <div className="actions">
        <button type="button" className="btn" onClick={onAdult}>
          Yes, I am 16 or older
        </button>
        <button type="button" className="btn ghost" onClick={() => setUnder16(true)}>
          No, I am under 16
        </button>
      </div>
    </section>
  );
}

function Under16() {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  return (
    <section className="card narrow">
      <h1 className="text-3xl" ref={heading} tabIndex={-1}>
        You can keep playing without an account
      </h1>
      <p>
        The daily games, all the levels and practice work the same without an account. Your streak stays in this
        browser.
      </p>
      <p>
        <Link href="/">Back to today's set</Link>
      </p>
    </section>
  );
}
