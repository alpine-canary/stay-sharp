// Streak, freeze, longest and skill view, table-driven (task T095, FR-012 to FR-015, R7, W13, V5).
//
// Dates are Europe/Zurich calendar days as the server gives them ("YYYY-MM-DD"). 2026-03-23 is a
// Monday; summer time starts on Sunday 2026-03-29 and ends on Sunday 2026-10-25.

import { describe, expect, it } from "vitest";
import { freshProgress, recordAnswer, recordDay } from "../storage";
import { skills } from "./skills";
import { streak, weekOf } from "./streak";

function range(first: string, last: string): string[] {
  const out: string[] = [];
  const day = new Date(`${first}T00:00:00Z`);
  const end = new Date(`${last}T00:00:00Z`);
  while (day <= end) {
    out.push(day.toISOString().slice(0, 10));
    day.setUTCDate(day.getUTCDate() + 1);
  }
  return out;
}

interface Case {
  name: string;
  played: string[];
  today: string;
  current: number;
  longest: number;
  held: boolean;
  frozen: string[];
}

const CASES: Case[] = [
  { name: "no play yet", played: [], today: "2026-03-23", current: 0, longest: 0, held: false, frozen: [] },
  {
    name: "played yesterday, not yet today: the streak is still alive",
    played: ["2026-03-22"],
    today: "2026-03-23",
    current: 1,
    longest: 1,
    held: false,
    frozen: [],
  },
  {
    name: "two days in a row",
    played: ["2026-03-23", "2026-03-24"],
    today: "2026-03-24",
    current: 2,
    longest: 2,
    held: false,
    frozen: [],
  },
  {
    name: "the 5th finished daily of an ISO week earns a freeze",
    played: range("2026-03-23", "2026-03-27"),
    today: "2026-03-27",
    current: 5,
    longest: 5,
    held: true,
    frozen: [],
  },
  {
    name: "4 plays in a week earn nothing",
    played: range("2026-03-23", "2026-03-26"),
    today: "2026-03-26",
    current: 4,
    longest: 4,
    held: false,
    frozen: [],
  },
  {
    name: "5 plays across two weeks earn nothing",
    played: range("2026-03-26", "2026-03-30"),
    today: "2026-03-30",
    current: 5,
    longest: 5,
    held: false,
    frozen: [],
  },
  {
    name: "a whole week, summer time starts on Sunday: one freeze, at most one held",
    played: range("2026-03-23", "2026-03-29"),
    today: "2026-03-29",
    current: 7,
    longest: 7,
    held: true,
    frozen: [],
  },
  {
    name: "the week summer time ends counts Monday to Sunday too",
    played: range("2026-10-21", "2026-10-25"),
    today: "2026-10-25",
    current: 5,
    longest: 5,
    held: true,
    frozen: [],
  },
  {
    name: "a freeze covers one missed day: the day shows frozen and the streak continues",
    played: [...range("2026-03-23", "2026-03-27"), "2026-03-29"],
    today: "2026-03-29",
    current: 6,
    longest: 6,
    held: false,
    frozen: ["2026-03-28"],
  },
  {
    name: "one missed day and today not played yet: the freeze keeps the streak alive",
    played: range("2026-03-23", "2026-03-27"),
    today: "2026-03-29",
    current: 5,
    longest: 5,
    held: false,
    frozen: ["2026-03-28"],
  },
  {
    name: "two missed days reset to 1, the freeze is not wasted, the longest is kept",
    played: [...range("2026-03-23", "2026-03-27"), "2026-03-30"],
    today: "2026-03-30",
    current: 1,
    longest: 5,
    held: true,
    frozen: [],
  },
  {
    name: "two missed days and today not played yet: the streak shows 0",
    played: range("2026-03-23", "2026-03-27"),
    today: "2026-03-30",
    current: 0,
    longest: 5,
    held: true,
    frozen: [],
  },
  {
    name: "one missed day without a freeze resets to 1 (the 5th play of the week then earns one)",
    played: [...range("2026-03-23", "2026-03-26"), "2026-03-28"],
    today: "2026-03-28",
    current: 1,
    longest: 4,
    held: true,
    frozen: [],
  },
  {
    name: "no new freeze in a week where one was used",
    // Freeze earned in week 13, used on Monday 30 (week 14), 5 more plays in week 14.
    played: [...range("2026-03-23", "2026-03-29"), ...range("2026-03-31", "2026-04-04")],
    today: "2026-04-04",
    current: 12,
    longest: 12,
    held: false,
    frozen: ["2026-03-30"],
  },
  {
    name: "a freeze can be earned again the week after it was used",
    played: [...range("2026-03-23", "2026-03-29"), ...range("2026-03-31", "2026-04-10")],
    today: "2026-04-10",
    current: 18,
    longest: 18,
    held: true,
    frozen: ["2026-03-30"],
  },
  {
    name: "the longest streak survives a later, shorter one",
    played: [...range("2026-03-01", "2026-03-10"), ...range("2026-03-20", "2026-03-22")],
    today: "2026-03-22",
    current: 3,
    longest: 10,
    held: true,
    frozen: [],
  },
];

describe("streak", () => {
  it.each(CASES)("$name", ({ played, today, current, longest, held, frozen }) => {
    const got = streak(played, today);
    expect(got).toEqual({ current, longest, held, frozen, playedToday: played.includes(today) });
  });

  it("ignores the order of the log and days after today", () => {
    const got = streak(["2026-03-24", "2026-03-23", "2026-03-30"], "2026-03-24");
    expect(got.current).toBe(2);
  });

  it("weeks run Monday to Sunday, whatever the time zone of the device", () => {
    expect(weekOf("2026-03-29")).toBe("2026-03-23");
    expect(weekOf("2026-03-30")).toBe("2026-03-30");
    expect(weekOf("2026-10-25")).toBe("2026-10-19");
    expect(weekOf("2027-01-03")).toBe("2026-12-28");
  });
});

describe("recording", () => {
  const play = { level: "senior" as const, date: "2026-03-27", score: 4.5, bonus: 0.4, relaxed: false };

  it("a play finished after midnight counts for its own date", () => {
    // Finished at 00:20 on the 28th: the server's play date is still the 27th.
    const p = recordDay(freshProgress(), play);
    expect(Object.keys(p.days.senior)).toEqual(["2026-03-27"]);
    expect(streak(Object.keys(p.days.senior), "2026-03-28").current).toBe(1);
  });

  it("levels are kept apart", () => {
    const p = recordDay(freshProgress(), play);
    expect(p.days.starter).toEqual({});
    const q = recordAnswer(p, { level: "starter", deck: "logic", grade: 1, duplicate: false });
    expect(q.deckStats.senior).toEqual({});
    expect(q.deckStats.starter).toEqual({ logic: { answered: 1, correct: 1 } });
  });

  it("an answer marked duplicate changes no count", () => {
    const p = recordAnswer(freshProgress(), { level: "senior", deck: "spot", grade: 0.5, duplicate: false });
    const q = recordAnswer(p, { level: "senior", deck: "spot", grade: 0.5, duplicate: true });
    expect(q).toBe(p);
    expect(q.deckStats.senior.spot).toEqual({ answered: 1, correct: 0.5 });
  });
});

describe("skill view", () => {
  it("half-right counts as half, weakest deck first, unplayed decks last", () => {
    const rows = skills(
      {
        spot: { answered: 4, correct: 3.5 },
        better: { answered: 2, correct: 0.5 },
        fail: { answered: 3, correct: 3 },
        news: { answered: 2, correct: 0.5 },
      },
      ["spot", "better", "fail", "acronym", "news"],
    );
    expect(rows).toEqual([
      { deck: "better", answered: 2, correct: 0.5, share: 0.25 },
      { deck: "news", answered: 2, correct: 0.5, share: 0.25 },
      { deck: "spot", answered: 4, correct: 3.5, share: 0.875 },
      { deck: "fail", answered: 3, correct: 3, share: 1 },
      { deck: "acronym", answered: 0, correct: 0, share: null },
    ]);
  });
});
