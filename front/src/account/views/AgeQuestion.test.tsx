import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgeQuestion } from "./AgeQuestion";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("AgeQuestion (FR-116)", () => {
  it("asks before anything else, with two plain answers", () => {
    render(<AgeQuestion onAdult={vi.fn()} />);
    expect(screen.getByRole("heading", { level: 1, name: "Are you 16 or older?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yes, I am 16 or older" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "No" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/e-mail/i)).toBeNull();
  });

  it("No shows a friendly page, stores nothing and sends nothing", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const onAdult = vi.fn();
    render(<AgeQuestion onAdult={onAdult} />);
    await user.click(screen.getByRole("button", { name: "No" }));
    const heading = screen.getByRole("heading", { level: 1, name: "You can keep playing without an account" });
    expect(heading).toHaveFocus();
    expect(screen.getByRole("link", { name: "Back to today's set" })).toHaveAttribute("href", "/");
    expect(onAdult).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("Yes goes on to the e-mail step", async () => {
    const user = userEvent.setup();
    const onAdult = vi.fn();
    render(<AgeQuestion onAdult={onAdult} />);
    await user.click(screen.getByRole("button", { name: "Yes, I am 16 or older" }));
    expect(onAdult).toHaveBeenCalledOnce();
  });
});
