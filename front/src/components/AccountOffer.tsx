// The account offer on the result screen (tasks T236, T237, FR-102, US4). Its own small chunk,
// loaded only when offerRule.ts says it is due; no sign-in code here, only a link to /account.

import { useState } from "react";
import { Link } from "./Link";
import { OFFER_KEY } from "./offerRule";

export { OFFER_KEY, shouldOffer, type OfferRule } from "./offerRule";

/** Shown only when offerRule says it is due (the result screen checks before loading it). */
export interface AccountOfferProps {
  streak: number;
  today: string;
}

export function AccountOffer({ streak, today }: AccountOfferProps) {
  const [shown, setShown] = useState(true);
  if (!shown) return null;

  const dismiss = () => {
    try {
      window.localStorage.setItem(OFFER_KEY, today);
    } catch {
      // Hidden for this page only.
    }
    setShown(false);
  };

  return (
    <section className="card" aria-labelledby="offer-title">
      <h2 id="offer-title" className="text-xl">
        Keep your {streak}-day streak on your phone too?
      </h2>
      <p>A free account saves your streak and progress, so you can play on any device. No password: we send you a code.</p>
      <div className="actions">
        <Link href="/account" className="btn">
          Create an account
        </Link>
        <button type="button" className="link-btn" onClick={dismiss}>
          Not now
        </button>
      </div>
    </section>
  );
}

export default AccountOffer;
