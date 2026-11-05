import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { freshProgress, type Progress } from "../storage";
import { ProgressCard, zurichToday } from "./ProgressCard";

function withDays(dates: string[]): Progress {
  const p = freshProgress();
  for (const d of dates) p.days.senior[d] = { score: 4, bonus: 0.2, relaxed: false };
  return p;
}

function figure(term: string): string {
  const dt = screen.getByText(term, { selector: "dt" });
  return dt.nextElementSibling?.textContent ?? "";
}

describe("ProgressCard", () => {
  it("shows streak, longest and a freeze earned this week", () => {
    const p = withDays(["2026-03-23", "2026-03-24", "2026-03-25", "2026-03-26", "2026-03-27"]);
    render(<ProgressCard progress={p} level="senior" today="2026-03-27" />);
    expect(figure("Streak")).toBe("5 days");
    expect(figure("Longest")).toBe("5 days");
    expect(figure("Freeze")).toBe("1 held");
    expect(screen.getByText(/Ready\. It covers one missed day/)).toBeInTheDocument();
    expect(screen.getByText("Done for today. Come back tomorrow.")).toBeInTheDocument();
  });

  it("says a missed yesterday was covered by the freeze", () => {
    const p = withDays(["2026-03-23", "2026-03-24", "2026-03-25", "2026-03-26", "2026-03-27"]);
    render(<ProgressCard progress={p} level="senior" today="2026-03-29" />);
    expect(figure("Streak")).toBe("5 days");
    expect(figure("Freeze")).toBe("0 held");
    expect(screen.getByText(/You missed yesterday\. Your freeze covered it/)).toBeInTheDocument();
    expect(screen.getByText("Finish today's set to keep it going.")).toBeInTheDocument();
  });

  it("counts this week's dailies towards the next freeze", () => {
    render(<ProgressCard progress={withDays(["2026-03-23", "2026-03-24"])} level="senior" today="2026-03-24" />);
    expect(figure("Streak")).toBe("2 days");
    expect(screen.getByText(/2 of 5 dailies this week/)).toBeInTheDocument();
  });

  it("lists decks weakest first, half-right as half, unplayed decks last", () => {
    const p = freshProgress();
    p.deckStats.senior = { spot: { answered: 4, correct: 3.5 }, better: { answered: 2, correct: 0.5 } };
    render(<ProgressCard progress={p} level="senior" today="2026-03-24" />);
    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      "Could do better0.5 of 2 right",
      "Spot the bug3.5 of 4 right",
      "What if it fails?Not played yet",
      "Acronym or toolNot played yet",
      "AI this weekNot played yet",
    ]);
  });

  it("keeps levels apart and says where progress is kept", () => {
    const p = withDays(["2026-03-23"]);
    render(<ProgressCard progress={p} level="starter" today="2026-03-23" />);
    expect(figure("Streak")).toBe("0 days");
    expect(screen.getByText("Finish today's set to start a streak.")).toBeInTheDocument();
    expect(screen.getByText(/Answer a few questions/)).toBeInTheDocument();
    expect(screen.getByText(/kept in this browser only/)).toBeInTheDocument();
  });

  it("knows today in Zurich from the device clock", () => {
    // 23:30 UTC on 28 March is already 29 March in Zurich (00:30, and 01:30 after the switch).
    expect(zurichToday(new Date("2026-03-28T23:30:00Z"))).toBe("2026-03-29");
    expect(zurichToday(new Date("2026-03-29T21:59:00Z"))).toBe("2026-03-29");
    expect(zurichToday(new Date("2026-03-29T22:00:00Z"))).toBe("2026-03-30");
  });
});
