import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AgeAsk, clearEarlyAnswer, earlyAnswer } from "./AgeAsk";

describe("AgeAsk, the first screen of /account (FR-116)", () => {
  it("keeps an answer given before the account code loads, until it is acted on", async () => {
    const user = userEvent.setup();
    render(<AgeAsk />);
    await user.click(screen.getByRole("button", { name: "Yes, I am 16 or older" }));
    expect(earlyAnswer()).toBe("adult");
    expect(earlyAnswer()).toBe("adult"); // stays until the player leaves /account
    clearEarlyAnswer();
    expect(earlyAnswer()).toBeNull();
  });

  it("keeps a No too, which sends and stores nothing", async () => {
    const user = userEvent.setup();
    render(<AgeAsk />);
    await user.click(screen.getByRole("button", { name: "No, I am under 16" }));
    expect(earlyAnswer()).toBe("under16");
    clearEarlyAnswer();
    expect(window.localStorage.length + window.sessionStorage.length).toBe(0);
  });
});
