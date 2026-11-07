// Share card without spoilers (task T099, Story 3, FR-017, FR-033).

import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ShareCard, shareText, type ShareInput } from "./ShareCard";

const BASE: ShareInput = {
  gameNumber: 42,
  level: "senior",
  grades: [1, 1, 0, 0.5, 1],
  score: 3.5,
  bonus: 0.4,
  relaxed: false,
  elapsedMs: 192_400,
  streak: 9,
  address: "stay-sharp.example.org",
};

describe("shareText", () => {
  it("has the exact format of Story 3", () => {
    expect(shareText(BASE)).toBe(
      ["Stay Sharp #42 · Senior", "🟩🟩🟥🟨🟩  3.5/5 · speed +0.4 · 3m12s · streak 9", "stay-sharp.example.org"].join(
        "\n",
      ),
    );
  });

  it("says relaxed instead of the speed bonus", () => {
    const text = shareText({ ...BASE, level: "starter", relaxed: true, bonus: 0, score: 5, grades: [1, 1, 1, 1, 1] });
    expect(text.split("\n")[0]).toBe("Stay Sharp #42 · Starter");
    expect(text.split("\n")[1]).toBe("🟩🟩🟩🟩🟩  5/5 · relaxed · 3m12s · streak 9");
  });

  it("pads seconds and shows zero bonus and zero streak plainly", () => {
    const line = shareText({ ...BASE, bonus: 0, elapsedMs: 65_999, streak: 0 }).split("\n")[1];
    expect(line).toBe("🟩🟩🟥🟨🟩  3.5/5 · speed +0 · 1m05s · streak 0");
  });

  it("uses one distinct symbol per grade, so it reads without colour", () => {
    const line = shareText({ ...BASE, grades: [1, 0.5, 0, 1, 0] }).split("\n")[1] ?? "";
    const squares = [...(line.split("  ")[0] ?? "")];
    expect(squares).toEqual(["🟩", "🟨", "🟥", "🟩", "🟥"]);
    expect(new Set(["🟩", "🟨", "🟥"]).size).toBe(3);
  });

  it("carries no question content: only the three fixed lines", () => {
    const text = shareText(BASE);
    expect(text.split("\n")).toHaveLength(3);
    // Nothing but the card's own words, figures, squares and the address.
    const words = text.replace(/[🟩🟨🟥·#+/\n]/gu, " ").split(/\s+/).filter(Boolean);
    const allowed = /^(Stay|Sharp|Senior|Starter|speed|relaxed|streak|\d+(\.\d)?|\d+m\d{2}s|stay-sharp\.example\.org)$/;
    for (const word of words) expect(word).toMatch(allowed);
  });
});

describe("ShareCard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the card with a text label per question and copies it", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    render(<ShareCard {...BASE} />);

    expect(screen.getByText(/Question 3: wrong/)).toBeInTheDocument();
    expect(screen.getByText(/Question 4: half right/)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy result" }));
    });
    expect(writeText).toHaveBeenCalledWith(shareText(BASE));
    expect(screen.getByRole("status")).toHaveTextContent("Copied. Paste it wherever you like.");
  });

  it("selects the text and says so when the clipboard is not available", async () => {
    vi.stubGlobal("navigator", { ...navigator, clipboard: undefined });
    render(<ShareCard {...BASE} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy result" }));
    });
    expect(screen.getByRole("status")).toHaveTextContent(/could not copy.*selected/i);
    expect(window.getSelection()?.toString()).toBe(shareText(BASE));
  });

  it("falls back the same way when the browser refuses the copy", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    render(<ShareCard {...BASE} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy result" }));
    });
    expect(screen.getByRole("status")).toHaveTextContent(/could not copy.*selected/i);
  });
  it("offers the share sheet where the browser has one, with the same text", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, share });
    render(<ShareCard {...BASE} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Share" }));
    });
    expect(share).toHaveBeenCalledWith({ text: shareText(BASE) });
    expect(screen.getByRole("button", { name: "Copy result" })).toBeInTheDocument();
  });

  it("says nothing when the player closes the share sheet", async () => {
    const share = vi.fn().mockRejectedValue(new DOMException("closed", "AbortError"));
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, share, clipboard: { writeText } });
    render(<ShareCard {...BASE} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Share" }));
    });
    expect(writeText).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("copies instead when the share sheet fails", async () => {
    const share = vi.fn().mockRejectedValue(new DOMException("no", "NotAllowedError"));
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, share, clipboard: { writeText } });
    render(<ShareCard {...BASE} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Share" }));
    });
    expect(writeText).toHaveBeenCalledWith(shareText(BASE));
  });

  it("shows only the copy button where there is no share sheet", () => {
    vi.stubGlobal("navigator", { ...navigator, share: undefined });
    render(<ShareCard {...BASE} />);
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
  });
});
