import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { SESSION_KEY } from "../accountHint";
import { AccountOffer } from "./AccountOffer";
import { OFFER_KEY, offerNow, shouldOffer, type OfferRule } from "./offerRule";

const BASE: OfferRule = { streak: 3, finishedDailies: 3, signedIn: false, dismissedOn: null, today: "2026-11-20" };

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("shouldOffer (T236)", () => {
  it.each<[string, Partial<OfferRule>, boolean]>([
    ["streak 3 after a finished daily", {}, true],
    ["never before the first finished daily", { finishedDailies: 0 }, false],
    ["not below a 3-day streak", { streak: 2 }, false],
    ["never when signed in", { signedIn: true }, false],
    ["hidden 6 days after Not now", { dismissedOn: "2026-11-14" }, false],
    ["back after 7 days", { dismissedOn: "2026-11-13" }, true],
  ])("%s", (_name, change, expected) => {
    expect(shouldOffer({ ...BASE, ...change })).toBe(expected);
  });
});

describe("AccountOffer", () => {
  it("offers with the streak, links to the account page, and Not now hides it", async () => {
    const user = userEvent.setup();
    render(<AccountOffer streak={12} today="2026-11-20" />);
    expect(screen.getByRole("heading", { name: "Keep your 12-day streak on your phone too?" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create an account" })).toHaveAttribute("href", "/account");
    await user.click(screen.getByRole("button", { name: "Not now" }));
    expect(screen.queryByRole("heading", { name: /streak on your phone/ })).toBeNull();
    expect(window.localStorage.getItem(OFFER_KEY)).toBe("2026-11-20");
  });

  it("is not due for a signed-in browser, nor for 7 days after Not now", () => {
    window.sessionStorage.setItem(SESSION_KEY, "{}");
    expect(offerNow({ streak: 12, finishedDailies: 12, today: "2026-11-20", signedIn: true })).toBe(false);
    window.localStorage.setItem(OFFER_KEY, "2026-11-18");
    expect(offerNow({ streak: 12, finishedDailies: 12, today: "2026-11-20", signedIn: false })).toBe(false);
    window.localStorage.setItem(OFFER_KEY, "2026-11-13");
    expect(offerNow({ streak: 12, finishedDailies: 12, today: "2026-11-20", signedIn: false })).toBe(true);
  });
});
