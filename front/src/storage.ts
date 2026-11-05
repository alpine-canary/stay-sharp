// Local progress in the browser (data-model.md "Local progress", research R3, R7).
// One versioned key. Blocked storage falls back to memory; broken data is reset with a visible
// notice. Nothing here ever throws to the UI.

export const STORAGE_KEY = "staysharp.v1";
export const VERSION = 1;

export type Level = "senior" | "starter";
export const LEVELS: readonly Level[] = ["senior", "starter"];

export interface DayResult {
  score: number;
  bonus: number;
  relaxed: boolean;
}

export interface Freeze {
  held: number;
  earnedWeek: string | null;
  usedOn: string[];
}

export interface DeckStat {
  answered: number;
  correct: number;
}

export interface Progress {
  version: typeof VERSION;
  playerId: string;
  level: Level | null;
  relaxed: boolean;
  days: Record<Level, Record<string, DayResult>>;
  freeze: Record<Level, Freeze>;
  longest: Record<Level, number>;
  deckStats: Record<Level, Record<string, DeckStat>>;
  boxes: Record<string, number>;
}

/** Why the stored progress could not be used as is. Shown once to the player. */
export type Notice = "reset" | "unavailable" | null;

export interface Loaded {
  progress: Progress;
  notice: Notice;
}

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function newPlayerId(): string {
  const id = crypto.randomUUID().toLowerCase();
  if (!UUID_V4.test(id)) throw new Error("randomUUID did not return a UUIDv4");
  return id;
}

function perLevel<T>(make: () => T): Record<Level, T> {
  return { senior: make(), starter: make() };
}

export function freshProgress(playerId: string = newPlayerId()): Progress {
  return {
    version: VERSION,
    playerId,
    level: null,
    relaxed: false,
    days: perLevel(() => ({})),
    freeze: perLevel(() => ({ held: 0, earnedWeek: null, usedOn: [] })),
    longest: perLevel(() => 0),
    deckStats: perLevel(() => ({})),
    boxes: {},
  };
}

// --- Shape checks: anything unexpected means "reset", never a crash. --------------------------

type Json = Record<string, unknown>;

const isObject = (v: unknown): v is Json => typeof v === "object" && v !== null && !Array.isArray(v);
const isCount = (v: unknown): v is number => Number.isInteger(v) && (v as number) >= 0;
const isNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isDate = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);

function everyLevel(v: unknown, check: (value: unknown) => boolean): boolean {
  return isObject(v) && LEVELS.every((level) => check(v[level]));
}

function isDays(v: unknown): boolean {
  return (
    isObject(v) &&
    Object.entries(v).every(
      ([day, r]) =>
        isDate(day) && isObject(r) && isNumber(r.score) && isNumber(r.bonus) && typeof r.relaxed === "boolean",
    )
  );
}

function isFreeze(v: unknown): boolean {
  return (
    isObject(v) &&
    isCount(v.held) &&
    (v.earnedWeek === null || isDate(v.earnedWeek)) &&
    Array.isArray(v.usedOn) &&
    v.usedOn.every(isDate)
  );
}

// Half-right counts as half (FR-015): correct is a multiple of 0.5.
const isHalves = (v: unknown): v is number => isNumber(v) && v >= 0 && Number.isInteger(v * 2);

function isDeckStats(v: unknown): boolean {
  return (
    isObject(v) &&
    Object.values(v).every(
      (s) => isObject(s) && isCount(s.answered) && isHalves(s.correct) && s.correct <= s.answered,
    )
  );
}

function isBoxes(v: unknown): boolean {
  return isObject(v) && Object.values(v).every((b) => Number.isInteger(b) && (b as number) >= 1 && (b as number) <= 5);
}

export function isProgress(v: unknown): v is Progress {
  return (
    isObject(v) &&
    v.version === VERSION &&
    typeof v.playerId === "string" &&
    UUID_V4.test(v.playerId) &&
    (v.level === null || LEVELS.includes(v.level as Level)) &&
    typeof v.relaxed === "boolean" &&
    everyLevel(v.days, isDays) &&
    everyLevel(v.freeze, isFreeze) &&
    everyLevel(v.longest, isCount) &&
    everyLevel(v.deckStats, isDeckStats) &&
    isBoxes(v.boxes)
  );
}

// --- Store ------------------------------------------------------------------------------------

export function browserStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export interface ProgressStore {
  load(): Loaded;
  save(progress: Progress): boolean;
  /** False once a write failed or storage was never available: progress lives in memory only. */
  readonly persistent: boolean;
}

export function createStore(storage: Storage | null = browserStorage()): ProgressStore {
  let persistent = storage !== null;
  let memory: Progress | null = null;

  return {
    get persistent() {
      return persistent;
    },

    load(): Loaded {
      if (memory) return { progress: memory, notice: null };
      if (!storage) {
        memory = freshProgress();
        return { progress: memory, notice: "unavailable" };
      }
      let raw: string | null;
      try {
        raw = storage.getItem(STORAGE_KEY);
      } catch {
        persistent = false;
        memory = freshProgress();
        return { progress: memory, notice: "unavailable" };
      }
      if (raw === null) {
        memory = freshProgress();
        this.save(memory);
        return { progress: memory, notice: null };
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = undefined;
      }
      if (isProgress(parsed)) {
        memory = parsed;
        return { progress: memory, notice: null };
      }
      // Keep the player id if it survived, so answers already stored on the server stay theirs.
      const oldId = isObject(parsed) && typeof parsed.playerId === "string" && UUID_V4.test(parsed.playerId);
      memory = freshProgress(oldId ? (parsed as Json).playerId as string : undefined);
      this.save(memory);
      return { progress: memory, notice: "reset" };
    },

    save(progress: Progress): boolean {
      memory = progress;
      if (!storage || !persistent) return false;
      try {
        storage.setItem(STORAGE_KEY, JSON.stringify(progress));
        return true;
      } catch {
        persistent = false;
        return false;
      }
    },
  };
}

// --- Recording (task T097, R7, W13) -----------------------------------------------------------

export interface FinishedDaily {
  level: Level;
  /** The play's date from the server, never the device clock: a play finished after midnight
   * counts for its own day. */
  date: string;
  score: number;
  bonus: number;
  relaxed: boolean;
}

export function recordDay(progress: Progress, play: FinishedDaily): Progress {
  const days = { ...progress.days[play.level], [play.date]: { score: play.score, bonus: play.bonus, relaxed: play.relaxed } };
  return { ...progress, days: { ...progress.days, [play.level]: days } };
}

export interface GradedAnswer {
  level: Level;
  deck: string;
  grade: number;
  /** The server already had this answer: it was counted the first time. */
  duplicate: boolean;
}

/** Add one graded answer to the skill view. A duplicate returns the same object, unchanged. */
export function recordAnswer(progress: Progress, answer: GradedAnswer): Progress {
  if (answer.duplicate) return progress;
  const stats = progress.deckStats[answer.level];
  const before = stats[answer.deck] ?? { answered: 0, correct: 0 };
  const after = { answered: before.answered + 1, correct: before.correct + answer.grade };
  return {
    ...progress,
    deckStats: { ...progress.deckStats, [answer.level]: { ...stats, [answer.deck]: after } },
  };
}
