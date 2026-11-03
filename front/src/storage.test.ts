import { describe, expect, it } from "vitest";
import { createStore, freshProgress, isProgress, newPlayerId, STORAGE_KEY } from "./storage";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

class MemoryStorage implements Storage {
  data = new Map<string, string>();
  failWrites = false;
  failReads = false;
  get length() {
    return this.data.size;
  }
  clear() {
    this.data.clear();
  }
  key(i: number) {
    return [...this.data.keys()][i] ?? null;
  }
  getItem(k: string) {
    if (this.failReads) throw new DOMException("blocked", "SecurityError");
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    if (this.failWrites) throw new DOMException("full", "QuotaExceededError");
    this.data.set(k, v);
  }
  removeItem(k: string) {
    this.data.delete(k);
  }
}

describe("player id", () => {
  it("is a lowercase UUIDv4", () => {
    expect(newPlayerId()).toMatch(UUID_V4);
  });
});

describe("store", () => {
  it("creates progress with a player id on the first visit and saves it", () => {
    const storage = new MemoryStorage();
    const { progress, notice } = createStore(storage).load();
    expect(notice).toBeNull();
    expect(progress.playerId).toMatch(UUID_V4);
    expect(progress.level).toBeNull();
    expect(JSON.parse(storage.getItem(STORAGE_KEY) ?? "")).toEqual(progress);
  });

  it("returns the same player id on the next visit", () => {
    const storage = new MemoryStorage();
    const first = createStore(storage).load().progress;
    const second = createStore(storage).load().progress;
    expect(second.playerId).toBe(first.playerId);
  });

  it("resets broken JSON with a notice, never a crash", () => {
    const storage = new MemoryStorage();
    storage.setItem(STORAGE_KEY, "{not json");
    const { progress, notice } = createStore(storage).load();
    expect(notice).toBe("reset");
    expect(isProgress(progress)).toBe(true);
  });

  it("resets a wrong shape but keeps a valid player id", () => {
    const storage = new MemoryStorage();
    const id = newPlayerId();
    storage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, playerId: id, boxes: { q: 9 } }));
    const { progress, notice } = createStore(storage).load();
    expect(notice).toBe("reset");
    expect(progress.playerId).toBe(id);
    expect(progress.boxes).toEqual({});
  });

  it("resets another version", () => {
    const storage = new MemoryStorage();
    storage.setItem(STORAGE_KEY, JSON.stringify({ ...freshProgress(), version: 2 }));
    expect(createStore(storage).load().notice).toBe("reset");
  });

  it("works in memory when storage is blocked", () => {
    const storage = new MemoryStorage();
    storage.failReads = true;
    const store = createStore(storage);
    const { progress, notice } = store.load();
    expect(notice).toBe("unavailable");
    expect(store.persistent).toBe(false);
    expect(store.save({ ...progress, level: "starter" })).toBe(false);
    expect(store.load().progress.level).toBe("starter");
  });

  it("works in memory when there is no storage at all", () => {
    const store = createStore(null);
    expect(store.load().notice).toBe("unavailable");
  });

  it("keeps going when a write fails", () => {
    const storage = new MemoryStorage();
    const store = createStore(storage);
    const { progress } = store.load();
    storage.failWrites = true;
    expect(store.save({ ...progress, level: "senior" })).toBe(false);
    expect(store.persistent).toBe(false);
    expect(store.load().progress.level).toBe("senior");
  });

  it("accepts real progress data", () => {
    const p = freshProgress();
    p.level = "senior";
    p.days.senior["2026-11-20"] = { score: 4.5, bonus: 0.6, relaxed: false };
    p.freeze.senior = { held: 1, earnedWeek: "2026-11-16", usedOn: [] };
    p.longest.senior = 3;
    p.deckStats.senior.spot = { answered: 3, correct: 2 };
    p.boxes.null_check = 2;
    expect(isProgress(JSON.parse(JSON.stringify(p)))).toBe(true);
    expect(isProgress({ ...p, deckStats: { ...p.deckStats, senior: { spot: { answered: 1, correct: 2 } } } })).toBe(false);
  });
});
