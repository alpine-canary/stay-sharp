import { describe, expect, it, vi } from "vitest";
import { freshProgress, type Progress } from "../storage";
import type { AccountApi } from "./api";
import { joinAccount } from "./join";
import { toCopy } from "./merge";

const PRIMARY = "11111111-1111-4111-8111-111111111111";
const HERE = "22222222-2222-4222-8222-222222222222";

function withDay(id: string, day: string): Progress {
  const p = freshProgress(id);
  return { ...p, days: { ...p.days, senior: { [day]: { score: 3, bonus: 0, relaxed: false } } } };
}

function api(adopted: object, remote: { version: number; body: unknown }): AccountApi {
  return {
    adopt: vi.fn().mockResolvedValue(adopted),
    getProgress: vi.fn().mockResolvedValue(remote),
    putProgress: vi.fn().mockResolvedValue({ stored: { version: remote.version + 1, body: {} }, conflict: false }),
    me: vi.fn(),
    deleteAccount: vi.fn(),
  };
}

describe("joinAccount (T229)", () => {
  it("first sign-in: creates the account with this browser's id and stores its progress", async () => {
    let progress = withDay(HERE, "2026-11-02");
    const a = api({ primaryPlayerId: HERE, created: true, merged: { plays: 0, replays: 0 } }, { version: 0, body: {} });
    const joined = await joinAccount(a, () => progress, (p) => (progress = p));
    expect(joined).toEqual({ created: true, combined: false, version: 1 });
    expect(a.adopt).toHaveBeenCalledWith(HERE);
    expect(a.putProgress).toHaveBeenCalledWith(0, toCopy(progress));
    expect(progress.playerId).toBe(HERE);
  });

  it("another browser: switches to the account's id and combines both histories", async () => {
    let progress = withDay(HERE, "2026-11-03");
    const remote = toCopy(withDay(PRIMARY, "2026-11-02"));
    const a = api({ primaryPlayerId: PRIMARY, created: false, merged: { plays: 1, replays: 0 } }, { version: 4, body: remote });
    const joined = await joinAccount(a, () => progress, (p) => (progress = p));
    expect(joined.combined).toBe(true);
    expect(progress.playerId).toBe(PRIMARY);
    expect(Object.keys(progress.days.senior).sort()).toEqual(["2026-11-02", "2026-11-03"]);
    expect(a.putProgress).toHaveBeenCalledWith(4, toCopy(progress));
  });

  it("a conflict while storing is merged once more", async () => {
    let progress = withDay(HERE, "2026-11-03");
    const a = api({ primaryPlayerId: HERE, created: false, merged: { plays: 0, replays: 0 } }, { version: 2, body: toCopy(withDay(HERE, "2026-11-01")) });
    (a.putProgress as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ stored: { version: 3, body: toCopy(withDay(HERE, "2026-11-04")) }, conflict: true })
      .mockResolvedValueOnce({ stored: { version: 4, body: {} }, conflict: false });
    const joined = await joinAccount(a, () => progress, (p) => (progress = p));
    expect(joined.version).toBe(4);
    expect(Object.keys(progress.days.senior).sort()).toEqual(["2026-11-01", "2026-11-03", "2026-11-04"]);
  });
});
