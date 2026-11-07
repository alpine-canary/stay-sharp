// When to offer an account on the result screen (tasks T236, T237, FR-102, US4). Kept in the
// main bundle on its own, so the offer itself (AccountOffer.tsx) loads only when it is shown.
//
// Shown only when it is worth something: after a finished daily, with a streak of 3 days or
// more in that level, never to a signed-in browser, and not for 7 days after "Not now".

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

export function readDismissed(): string | null {
  try {
    const value = window.localStorage.getItem(OFFER_KEY);
    return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
  } catch {
    return null;
  }
}

/** The rule with this browser's last "Not now"; ``signedIn`` comes from the session hint. */
export function offerNow(input: { streak: number; finishedDailies: number; today: string; signedIn: boolean }): boolean {
  return shouldOffer({ ...input, dismissedOn: readDismissed() });
}
