// The account offer on the result screen (tasks T236, T237, FR-102, US4). Main bundle: no
// sign-in code here, only a link to /account (which loads it).
//
// Shown only when it is worth something: after a finished daily, with a streak of 3 days or
// more in that level, never to a signed-in browser, and not for 7 days after "Not now".

import { useState } from "react";
import { signedInHint } from "../accountHint";
import { Link } from "./Link";

export const OFFER_KEY = "staysharp.offerDismissed";
const MIN_STREAK = 3;
const QUIET_DAYS = 7;

export interface OfferRule {
  streak: number;
  /** Finished, scored dailies in this browser (all levels). */
  finishedDailies: number;
  signedIn: boolean;
  /** Server date of the last "Not now", or null. */
  dismissedOn: string | null;
  /** Server date of this result. */
  today: string;
}

function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
}

export function shouldOffer({ streak, finishedDailies, signedIn, dismissedOn, today }: OfferRule): boolean {
  if (signedIn || finishedDailies < 1 || streak < MIN_STREAK) return false;
  return dismissedOn === null || daysBetween(dismissedOn, today) >= QUIET_DAYS;
}

function readDismissed(): string | null {
  try {
    const value = window.localStorage.getItem(OFFER_KEY);
    return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
  } catch {
    return null;
  }
}

export interface AccountOfferProps {
  streak: number;
  finishedDailies: number;
  today: string;
}

export function AccountOffer({ streak, finishedDailies, today }: AccountOfferProps) {
  const [shown, setShown] = useState(() =>
    shouldOffer({ streak, finishedDailies, today, signedIn: signedInHint(), dismissedOn: readDismissed() }),
  );
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
