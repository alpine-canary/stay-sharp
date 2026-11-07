import { describe, expect, it, vi } from "vitest";
import { freshProgress } from "../storage";
import type { AccountApi } from "./api";
import type { Cognito } from "./cognito";
import type { Session } from "./session";
import { signOut } from "./signOut";

const progress = freshProgress("11111111-1111-4111-8111-111111111111");

function runtime(overrides: { put?: () => Promise<unknown>; globalSignOut?: () => Promise<void>; token?: string | null } = {}) {
  const api = { putProgress: vi.fn(overrides.put ?? (() => Promise.resolve({ stored: { version: 2, body: {} }, conflict: false }))) } as unknown as AccountApi;
  const cognito = { signOut: vi.fn(overrides.globalSignOut ?? (() => Promise.resolve())) } as unknown as Cognito;
  const session = { accessToken: vi.fn().mockResolvedValue(overrides.token === undefined ? "acc" : overrides.token) } as unknown as Session;
  return { api, cognito, session };
}

describe("signOut (FR-113)", () => {
  it("sends this browser's progress, then signs out everywhere", async () => {
    const r = runtime();
    await signOut(r, () => progress);
    expect(r.api.putProgress).toHaveBeenCalledTimes(1);
    expect(r.cognito.signOut).toHaveBeenCalledWith("acc");
  });

  it("still finishes when the account cannot be reached", async () => {
    const r = runtime({ put: () => Promise.reject(new Error("offline")), globalSignOut: () => Promise.reject(new Error("offline")) });
    await expect(signOut(r, () => progress)).resolves.toBeUndefined();
  });

  it("does not wait forever for a slow server", async () => {
    vi.useFakeTimers();
    const r = runtime({ put: () => new Promise(() => undefined), globalSignOut: () => new Promise(() => undefined) });
    const done = signOut(r, () => progress, 3_000);
    await vi.advanceTimersByTimeAsync(6_000);
    await expect(done).resolves.toBeUndefined();
    vi.useRealTimers();
  });

  it("skips the server when the session has already expired", async () => {
    const r = runtime({ token: null });
    await signOut(r, () => progress);
    expect(r.cognito.signOut).not.toHaveBeenCalled();
  });
});
