import { beforeEach, describe, expect, it, vi } from "vitest";
import { REFRESH_KEY, SESSION_KEY, signedInHint } from "../accountHint";
import { SignInError, type Tokens } from "./cognito";
import { createSession } from "./session";

const NOW = 1_000_000;

function jwt(payload: object): string {
  const part = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${part({ alg: "none" })}.${part(payload)}.sig`;
}

const TOKENS: Tokens = {
  accessToken: "acc",
  idToken: jwt({ email: "player@example.test", sub: "s" }),
  refreshToken: "ref",
  expiresAt: NOW + 3_600_000,
};

function make(refresh = vi.fn<(token: string) => Promise<Tokens>>()) {
  let clock = NOW;
  const session = createSession({
    session: window.sessionStorage,
    local: window.localStorage,
    refresh,
    now: () => clock,
  });
  return { session, refresh, advance: (ms: number) => (clock += ms) };
}

beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
});

describe("session", () => {
  it("keeps tokens for this tab only by default", () => {
    const { session } = make();
    session.set(TOKENS, false);
    expect(JSON.parse(window.sessionStorage.getItem(SESSION_KEY) ?? "null")).toMatchObject({ accessToken: "acc", refreshToken: "ref" });
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
    expect(signedInHint()).toBe(true);
    expect(session.email()).toBe("player@example.test");
  });

  it("keeps the refresh token on the device only with keep me signed in", () => {
    const { session } = make();
    session.set(TOKENS, true);
    expect(window.localStorage.getItem(REFRESH_KEY)).toBe("ref");
    expect(JSON.parse(window.sessionStorage.getItem(SESSION_KEY) ?? "null")).not.toHaveProperty("refreshToken");
  });

  it("gives the access token while it has more than a minute left", async () => {
    const { session, refresh } = make();
    session.set(TOKENS, false);
    expect(await session.accessToken()).toBe("acc");
    expect(refresh).not.toHaveBeenCalled();
  });

  it("refreshes a token about to expire, from the device after a restart", async () => {
    const refresh = vi.fn<(token: string) => Promise<Tokens>>().mockResolvedValue({ ...TOKENS, accessToken: "acc2" });
    const first = make(refresh);
    first.session.set(TOKENS, true);
    window.sessionStorage.clear(); // the browser was closed
    const { session } = make(refresh);
    expect(signedInHint()).toBe(true);
    expect(await session.accessToken()).toBe("acc2");
    expect(refresh).toHaveBeenCalledWith("ref");
  });

  it("signs out locally when the refresh token no longer works", async () => {
    const refresh = vi.fn<(token: string) => Promise<Tokens>>().mockRejectedValue(new SignInError("expired"));
    const { session, advance } = make(refresh);
    session.set(TOKENS, true);
    advance(3_600_000);
    expect(await session.accessToken()).toBeNull();
    expect(signedInHint()).toBe(false);
  });

  it("stays signed in when the sign-in service is down", async () => {
    const refresh = vi.fn<(token: string) => Promise<Tokens>>().mockRejectedValue(new SignInError("unavailable"));
    const { session, advance } = make(refresh);
    session.set(TOKENS, true);
    advance(3_600_000);
    await expect(session.accessToken()).rejects.toThrow(SignInError);
    expect(signedInHint()).toBe(true);
  });

  it("clear removes every token", () => {
    const { session } = make();
    session.set(TOKENS, true);
    session.clear();
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull();
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
    expect(session.current()).toBeNull();
    expect(signedInHint()).toBe(false);
  });

  it("ignores a damaged session", async () => {
    window.sessionStorage.setItem(SESSION_KEY, "{nope");
    const { session } = make();
    expect(session.current()).toBeNull();
    expect(await session.accessToken()).toBeNull();
  });
});
