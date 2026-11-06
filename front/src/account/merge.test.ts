import { describe, expect, it } from "vitest";
import { freshProgress, isProgress, type Progress } from "../storage";
import { fromCopy, mergeProgress, toCopy } from "./merge";

const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";

function withDays(id: string, days: Record<string, number>, extra: Partial<Progress> = {}): Progress {
  const p = freshProgress(id);
  const senior = Object.fromEntries(Object.entries(days).map(([d, score]) => [d, { score, bonus: 0, relaxed: false }]));
  return { ...p, days: { ...p.days, senior }, ...extra };
}

describe("mergeProgress (T226)", () => {
  it("keeps one result per date, the account's on a clash, and recomputes the longest streak", () => {
    const local = withDays(B, { "2026-11-03": 2, "2026-11-04": 5 });
    const account = withDays(A, { "2026-11-01": 4, "2026-11-02": 3, "2026-11-03": 4 });
    const merged = mergeProgress(local, account, "sum");
    expect(merged.playerId).toBe(B);
    expect(Object.keys(merged.days.senior).sort()).toEqual(["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"]);
    expect(merged.days.senior["2026-11-03"]?.score).toBe(4);
    expect(merged.longest.senior).toBe(4);
    expect(isProgress(merged)).toBe(true);
  });

  it("never lowers a stored longest streak", () => {
    const local = withDays(B, {}, { longest: { senior: 0, junior: 0, starter: 12 } });
    const account = withDays(A, {}, { longest: { senior: 9, junior: 0, starter: 3 } });
    expect(mergeProgress(local, account, "max").longest).toEqual({ senior: 9, junior: 0, starter: 12 });
  });

  it("adds skill counts of two histories, but never counts a shared history twice", () => {
    const stats = (answered: number, correct: number) => ({ senior: { spot: { answered, correct } }, junior: {}, starter: {} });
    const local = { ...freshProgress(B), deckStats: stats(4, 3) };
    const account = { ...freshProgress(A), deckStats: stats(6, 2.5) };
    expect(mergeProgress(local, account, "sum").deckStats.senior.spot).toEqual({ answered: 10, correct: 5.5 });
    expect(mergeProgress(local, account, "max").deckStats.senior.spot).toEqual({ answered: 6, correct: 2.5 });
    // Merging the result again with "max" changes nothing.
    const once = mergeProgress(local, account, "max");
    expect(mergeProgress(once, account, "max")).toEqual(once);
  });

  it("combines freezes and practice boxes, keeping the lower box", () => {
    const local = freshProgress(B);
    local.freeze.senior = { held: 1, earnedWeek: "2026-10-26", usedOn: ["2026-10-20"] };
    local.practice.senior = { seen: 5, cards: { q1: { box: 3, due: 9, deck: "spot" } } };
    const account = freshProgress(A);
    account.freeze.senior = { held: 0, earnedWeek: "2026-11-02", usedOn: ["2026-10-29"] };
    account.practice.senior = { seen: 7, cards: { q1: { box: 1, due: 8, deck: "spot" }, q2: { box: 2, due: 11, deck: "fail" } } };
    const merged = mergeProgress(local, account, "sum");
    expect(merged.freeze.senior).toEqual({ held: 1, earnedWeek: "2026-11-02", usedOn: ["2026-10-20", "2026-10-29"] });
    expect(merged.practice.senior.seen).toBe(12);
    expect(merged.practice.senior.cards.q1?.box).toBe(1);
    expect(merged.practice.senior.cards.q2?.box).toBe(2);
  });

  it("keeps this browser's level choice, or takes the account's when it has none", () => {
    expect(mergeProgress({ ...freshProgress(B), level: "junior" }, { ...freshProgress(A), level: "senior" }, "max").level).toBe("junior");
    expect(mergeProgress(freshProgress(B), { ...freshProgress(A), level: "senior" }, "max").level).toBe("senior");
  });
});

describe("account copy", () => {
  it("leaves the player id out and reads it back with this browser's id", () => {
    const progress = withDays(A, { "2026-11-01": 3 });
    const copy = toCopy(progress);
    expect(copy).not.toHaveProperty("playerId");
    expect(fromCopy(JSON.parse(JSON.stringify(copy)), B, isProgress)?.playerId).toBe(B);
    expect(fromCopy({ version: 1 }, B, isProgress)).toBeNull();
  });
});
