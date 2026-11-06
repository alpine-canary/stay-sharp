// Account tokens on this device (task T215, research A9).
// - Access and id tokens: memory and sessionStorage (this tab only).
// - Refresh token: sessionStorage, or localStorage when the player ticks "keep me signed in on
//   this device" (it then survives a browser restart).
// - clear() removes all of them (sign out, deleted account).

import { REFRESH_KEY, SESSION_KEY } from "../accountHint";
import { SignInError, type Tokens } from "./cognito";

const MARGIN_MS = 60_000;

export interface SessionOptions {
  session: Storage | null;
  local: Storage | null;
  refresh: (refreshToken: string) => Promise<Tokens>;
  now?: () => number;
}

function read(storage: Storage | null, key: string): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function write(storage: Storage | null, key: string, value: string | null): void {
  try {
    if (value === null) storage?.removeItem(key);
    else storage?.setItem(key, value);
  } catch {
    // Storage refused: the session lives in memory for this page only.
  }
}

function isTokens(value: unknown): value is Tokens {
  const v = value as Partial<Tokens> | null;
  return typeof v?.accessToken === "string" && typeof v.idToken === "string" && typeof v.expiresAt === "number";
}

/** The claims of a JWT, without checking it (display only; the API checks tokens). */
export function claims(token: string): Record<string, unknown> {
  try {
    const part = token.split(".")[1] ?? "";
    const binary = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    const text = new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0)));
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return {};
  }
}

export function createSession(options: SessionOptions) {
  const now = options.now ?? Date.now;
  let memory: Tokens | null = null;
  let refreshing: Promise<string | null> | null = null;

  function current(): Tokens | null {
    if (memory) return memory;
    const raw = read(options.session, SESSION_KEY);
    if (raw) {
      try {
        const parsed: unknown = JSON.parse(raw);
        if (isTokens(parsed)) memory = parsed;
      } catch {
        write(options.session, SESSION_KEY, null);
      }
    }
    return memory;
  }

  function refreshToken(): string | null {
    return current()?.refreshToken ?? read(options.local, REFRESH_KEY);
  }

  function set(tokens: Tokens, keep: boolean): void {
    const kept = keep || read(options.local, REFRESH_KEY) !== null;
    const refresh = tokens.refreshToken ?? refreshToken() ?? undefined;
    memory = { ...tokens, ...(refresh ? { refreshToken: refresh } : {}) };
    const forTab: Tokens = { ...memory };
    if (kept) {
      delete forTab.refreshToken;
      write(options.local, REFRESH_KEY, refresh ?? null);
    }
    write(options.session, SESSION_KEY, JSON.stringify(forTab));
  }

  function clear(): void {
    memory = null;
    write(options.session, SESSION_KEY, null);
    write(options.local, REFRESH_KEY, null);
  }

  async function renew(): Promise<string | null> {
    const token = refreshToken();
    if (!token) {
      clear();
      return null;
    }
    try {
      const tokens = await options.refresh(token);
      set(tokens, read(options.local, REFRESH_KEY) !== null);
      return tokens.accessToken;
    } catch (error) {
      // The service is down: keep the session and let the caller say so.
      if (error instanceof SignInError && error.kind === "unavailable") throw error;
      clear();
      return null;
    }
  }

  return {
    current,
    set,
    clear,
    signedIn: (): boolean => current() !== null || read(options.local, REFRESH_KEY) !== null,
    email(): string | null {
      const tokens = current();
      const email = tokens ? claims(tokens.idToken).email : null;
      return typeof email === "string" ? email : null;
    },
    /** A working access token, refreshed when needed; null when signed out. */
    async accessToken(): Promise<string | null> {
      const tokens = current();
      if (tokens && tokens.expiresAt - now() > MARGIN_MS) return tokens.accessToken;
      refreshing ??= renew().finally(() => {
        refreshing = null;
      });
      return refreshing;
    },
  };
}

export type Session = ReturnType<typeof createSession>;
