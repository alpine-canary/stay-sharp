import { describe, expect, it, vi } from "vitest";
import { freshProgress, type Progress } from "../storage";
import { AccountApiError, type AccountApi } from "./api";
import { toCopy } from "./merge";
import { createSync, SYNC_KEY } from "./sync";

const ID = "22222222-2222-4222-8222-222222222222";

function local(days: Record<string, number>): Progress {
  const p = freshProgress(ID);
  return { ...p, days: { ...p.days, senior: Object.fromEntries(Object.entries(days).map(([d, s]) => [d, { score: s, bonus: 0, relaxed: false }])) } };
}

function setup(api: Partial<AccountApi>, start = local({ "2026-11-02": 3 })) {
  let progress = start;
  const replace = vi.fn((p: Progress) => (progress = p));
  window.localStorage.clear();
  const sync = createSync({
    api: api as AccountApi,
    current: () => progress,
    replace,
    storage: window.localStorage,
    sleep: () => Promise.resolve(),
  });
  return { sync, replace, progress: () => progress };
}

describe("sync (T228)", () => {
  it("sends the copy without the player id and keeps the new version", async () => {
    const putProgress = vi.fn().mockResolvedValue({ stored: { version: 1, body: {} }, conflict: false });
    const { sync } = setup({ putProgress });
    await sync.push();
    expect(putProgress).toHaveBeenCalledWith(0, toCopy(local({ "2026-11-02": 3 })));
    expect(putProgress.mock.calls[0]?.[1]).not.toHaveProperty("playerId");
    expect(sync.state()).toEqual({ version: 1, pending: false });
    expect(JSON.parse(window.localStorage.getItem(SYNC_KEY) ?? "{}")).toEqual({ version: 1, pending: false });
  });

  it("on 409 merges the stored copy here and tries again with its version", async () => {
    const stored = toCopy(local({ "2026-11-01": 5 }));
    const putProgress = vi
      .fn()
      .mockResolvedValueOnce({ stored: { version: 4, body: stored }, conflict: true })
      .mockResolvedValueOnce({ stored: { version: 5, body: {} }, conflict: false });
    const { sync, progress } = setup({ putProgress });
    await sync.push();
    expect(Object.keys(progress().days.senior).sort()).toEqual(["2026-11-01", "2026-11-02"]);
    expect(putProgress.mock.calls[1]?.[0]).toBe(4);
    expect(putProgress.mock.calls[1]?.[1]).toEqual(toCopy(progress()));
    expect(sync.state()).toEqual({ version: 5, pending: false });
  });

  it("stops after 3 conflicts and keeps the push due", async () => {
    const putProgress = vi.fn().mockResolvedValue({ stored: { version: 9, body: toCopy(local({})) }, conflict: true });
    const { sync } = setup({ putProgress });
    await sync.push();
    expect(putProgress).toHaveBeenCalledTimes(3);
    expect(sync.state().pending).toBe(true);
  });

  it("offline: remembers the push and sends it on the next pull", async () => {
    const putProgress = vi
      .fn()
      .mockRejectedValueOnce(new AccountApiError(0, null))
      .mockResolvedValue({ stored: { version: 1, body: {} }, conflict: false });
    const getProgress = vi.fn().mockResolvedValue({ version: 0, body: {} });
    const { sync } = setup({ putProgress, getProgress });
    await sync.push();
    expect(sync.state()).toEqual({ version: 0, pending: true });
    await sync.pull();
    expect(putProgress).toHaveBeenCalledTimes(2);
    expect(sync.state()).toEqual({ version: 1, pending: false });
  });

  it("pull brings a newer copy in, and pushes back what only this browser has", async () => {
    const remote = toCopy(local({ "2026-11-01": 5 }));
    const getProgress = vi.fn().mockResolvedValue({ version: 3, body: remote });
    const putProgress = vi.fn().mockResolvedValue({ stored: { version: 4, body: {} }, conflict: false });
    const { sync, replace } = setup({ getProgress, putProgress });
    await sync.pull();
    expect(replace).toHaveBeenCalledOnce();
    expect(putProgress).toHaveBeenCalledWith(3, expect.anything());
    expect(sync.state()).toEqual({ version: 4, pending: false });
  });

  it("pull with nothing new changes nothing", async () => {
    const getProgress = vi.fn().mockResolvedValue({ version: 0, body: {} });
    const putProgress = vi.fn();
    const { sync, replace } = setup({ getProgress, putProgress });
    await sync.pull();
    expect(replace).not.toHaveBeenCalled();
    expect(putProgress).not.toHaveBeenCalled();
  });
});
