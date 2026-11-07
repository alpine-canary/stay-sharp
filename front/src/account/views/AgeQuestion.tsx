// The first account screen (task T240, FR-116, clarification 2026-11-06): no account under 16.
// "No" stores nothing and sends nothing; the game stays fully playable without an account.

import { useEffect, useRef, useState } from "react";
import { AgeAsk } from "../../components/AgeAsk";
import { Link } from "../../components/Link";

export function AgeQuestion({ onAdult, under16: startUnder16 = false }: { onAdult: () => void; under16?: boolean }) {
  const [under16, setUnder16] = useState(startUnder16);
  return under16 ? <Under16 /> : <AgeAsk onAnswer={(answer) => (answer === "adult" ? onAdult() : setUnder16(true))} />;
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
