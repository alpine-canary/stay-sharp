// The account routes of the API (contracts/accounts.openapi.yaml), with the access token.
// A 401 refreshes the token once (the session does it) and tries again.

import type { components } from "../api/accounts-schema";

export type Me = components["schemas"]["Me"];
export type Adopted = components["schemas"]["Adopted"];
export interface ProgressCopy {
  version: number;
  body: unknown;
}

export class AccountApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | null,
  ) {
    super(`account API ${status}${code ? ` ${code}` : ""}`);
    this.name = "AccountApiError";
  }
  /** Offline, timed out or 5xx: worth trying again later. */
  get transient(): boolean {
    return this.status === 0 || this.status >= 500;
  }
}

export interface AccountApiOptions {
  token: (forceRefresh?: boolean) => Promise<string | null>;
  fetchImpl?: typeof fetch;
  base?: string;
}

export function createAccountApi({ token, fetchImpl = (i, n) => fetch(i, n), base = "/api/v1" }: AccountApiOptions) {
  async function call(method: string, path: string, body?: unknown, headers: Record<string, string> = {}, accept: number[] = []) {
    for (const retry of [false, true]) {
      const access = await token(retry);
      if (!access) throw new AccountApiError(401, "unauthorized");
      let response: Response;
      try {
        response = await fetchImpl(`${base}${path}`, {
          method,
          headers: { Authorization: `Bearer ${access}`, "Content-Type": "application/json", ...headers },
          cache: "no-store",
          credentials: "same-origin",
          ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        });
      } catch {
        throw new AccountApiError(0, null);
      }
      if (response.status === 401 && !retry) continue;
      const text = await response.text();
      const parsed: unknown = text ? JSON.parse(text) : null;
      if (response.ok || accept.includes(response.status)) return { status: response.status, body: parsed };
      const code = (parsed as { code?: string } | null)?.code ?? null;
      throw new AccountApiError(response.status, code);
    }
    throw new AccountApiError(401, "unauthorized");
  }

  return {
    async me(): Promise<Me | null> {
      const result = await call("GET", "/me", undefined, {}, [404]);
      return result.status === 404 ? null : (result.body as Me);
    },
    async adopt(playerId: string): Promise<Adopted> {
      return (await call("POST", "/me/adopt", { adult: true }, { "X-Player-Id": playerId })).body as Adopted;
    },
    async getProgress(): Promise<ProgressCopy> {
      return (await call("GET", "/me/progress")).body as ProgressCopy;
    },
    /** ``conflict`` carries the stored copy when someone else wrote first (409). */
    async putProgress(version: number, body: unknown): Promise<{ stored: ProgressCopy; conflict: boolean }> {
      const result = await call("PUT", "/me/progress", { version, body }, {}, [409]);
      return { stored: result.body as ProgressCopy, conflict: result.status === 409 };
    },
  };
}

export type AccountApi = ReturnType<typeof createAccountApi>;
