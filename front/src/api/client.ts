// Typed API client on the types generated from contracts/openapi.yaml (task T048).
// - X-Player-Id on every call except the public GET /today.
// - A timeout on every call.
// - One retry for a network error or timeout, only on calls the contract makes idempotent.
// - Typed errors: the UI shows a plain message and a retry button, never a stack trace.

import type { components, paths } from "./schema";

type Schemas = components["schemas"];
type Json<P extends keyof paths, M extends "get" | "post", S extends number> = paths[P][M] extends {
  responses: Record<S, { content: { "application/json": infer T } }>;
}
  ? T
  : never;

export type Today = Json<"/today", "get", 200>;
export type PlayState = Schemas["PlayState"];
export type QuestionView = Schemas["QuestionView"];
export type ChallengeView = Schemas["ChallengeView"];
export type ChallengeCreated = Schemas["ChallengeCreated"];
export type ResultSnapshot = Schemas["ResultSnapshot"];
export type PracticeNext = Json<"/practice/next", "post", 200>;
export type AnswerResult = Schemas["AnswerResult"];
export type AnswerRequest = Schemas["AnswerRequest"];
export type Level = Schemas["Level"];
export type ErrorCode = Schemas["Error"]["code"];
export type StartPlayRequest = NonNullable<paths["/plays"]["post"]["requestBody"]>["content"]["application/json"];

export type ApiErrorKind = "network" | "timeout" | "http";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | undefined;
  readonly code: ErrorCode | undefined;
  readonly body: unknown;

  constructor(kind: ApiErrorKind, message: string, options: { status?: number; code?: ErrorCode; body?: unknown } = {}) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = options.status;
    this.code = options.code;
    this.body = options.body;
  }

  /** The service did not answer usefully: show the "service down" message with a retry. */
  get serviceDown(): boolean {
    return this.kind !== "http" || (this.status !== undefined && this.status >= 500);
  }
}

export interface ClientOptions {
  playerId: () => string;
  /** Campaign network of this visit (src/campaign.ts), sent as X-Source on player calls. */
  source?: () => string | null;
  baseUrl?: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

interface Call {
  method: "GET" | "POST";
  path: string;
  body?: unknown;
  idempotent: boolean;
  /**
   * A public read without player id or cache override (GET /today), so the browser can reuse
   * the response prefetched by index.html.
   */
  anonymous?: boolean;
  /** Statuses whose JSON body is a normal result, not an error (for example 409 with a stored result). */
  accept?: readonly number[];
}

const DEFAULT_TIMEOUT_MS = 8_000;

export function createClient(options: ClientOptions) {
  const base = options.baseUrl ?? "/api/v1";
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const doFetch = options.fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));

  function playerHeaders(): Record<string, string> {
    const headers: Record<string, string> = { "X-Player-Id": options.playerId(), "Content-Type": "application/json" };
    const source = options.source?.();
    if (source) headers["X-Source"] = source;
    return headers;
  }

  async function once(call: Call): Promise<{ status: number; body: unknown }> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let response: Response;
    try {
      const init: RequestInit = call.anonymous
        ? { method: call.method, signal: controller.signal, credentials: "same-origin" }
        : {
            method: call.method,
            headers: playerHeaders(),
            signal: controller.signal,
            credentials: "same-origin",
            cache: "no-store",
          };
      if (call.body !== undefined) init.body = JSON.stringify(call.body);
      response = await doFetch(`${base}${call.path}`, init);
    } catch (error) {
      if (controller.signal.aborted) throw new ApiError("timeout", "The server took too long to answer.");
      throw new ApiError("network", "Could not reach the server.", { body: error });
    } finally {
      clearTimeout(timer);
    }
    let body: unknown = null;
    const text = await response.text();
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }
    if (response.ok || call.accept?.includes(response.status)) return { status: response.status, body };
    const error = typeof body === "object" && body !== null ? (body as { code?: ErrorCode; message?: string }) : {};
    throw new ApiError("http", error.message ?? `The server answered ${response.status}.`, {
      status: response.status,
      ...(error.code ? { code: error.code } : {}),
      body,
    });
  }

  async function request(call: Call): Promise<{ status: number; body: unknown }> {
    try {
      return await once(call);
    } catch (error) {
      const retryable = error instanceof ApiError && (error.kind === "network" || error.kind === "timeout");
      if (!retryable || !call.idempotent) throw error;
      return once(call);
    }
  }

  const play = (playId: string) => `/plays/${encodeURIComponent(playId)}`;

  return {
    async today(): Promise<Today> {
      return (await request({ method: "GET", path: "/today", idempotent: true, anonymous: true })).body as Today;
    },

    /** Start or resume: idempotent for the same player, date, level and mode. */
    async startPlay(body: StartPlayRequest): Promise<{ created: boolean; play: PlayState }> {
      const { status, body: play } = await request({ method: "POST", path: "/plays", body, idempotent: true });
      return { created: status === 201, play: play as PlayState };
    },

    async getPlay(playId: string): Promise<PlayState> {
      return (await request({ method: "GET", path: play(playId), idempotent: true })).body as PlayState;
    },

    /** One-way switch; calling it again is a no-op. */
    async relax(playId: string): Promise<PlayState> {
      return (await request({ method: "POST", path: `${play(playId)}/relaxed`, idempotent: true })).body as PlayState;
    },

    /** Records servedAt the first time only, so a retry is safe. */
    async open(playId: string, index: number): Promise<QuestionView> {
      return (await request({ method: "POST", path: `${play(playId)}/questions/${index}/open`, idempotent: true }))
        .body as QuestionView;
    },

    /**
     * The same answer twice counts once (duplicate: true), so a retry is safe. A different
     * answer already recorded comes back as 409 with the stored result.
     */
    async answer(
      playId: string,
      index: number,
      body: AnswerRequest,
    ): Promise<{ result: AnswerResult; conflict: boolean }> {
      const { status, body: data } = await request({
        method: "POST",
        path: `${play(playId)}/questions/${index}/answer`,
        body,
        idempotent: true,
        accept: [409],
      });
      if (status === 409) return { result: (data as { recorded: AnswerResult }).recorded, conflict: true };
      return { result: data as AnswerResult, conflict: false };
    },

    /** Each call counts against the 200 a day, so a lost reply is not retried. */
    async practiceNext(body: { level: Level; deck?: string; prefer: string[] }): Promise<PracticeNext> {
      return (await request({ method: "POST", path: "/practice/next", body, idempotent: false })).body as PracticeNext;
    },

    /** Same rule as the daily: the same answer twice counts once; a different one is a 409. */
    async practiceAnswer(attemptId: string, body: AnswerRequest): Promise<{ result: AnswerResult; conflict: boolean }> {
      const { status, body: data } = await request({
        method: "POST",
        path: `/practice/${encodeURIComponent(attemptId)}/answer`,
        body,
        idempotent: true,
        accept: [409],
      });
      if (status === 409) return { result: (data as { recorded: AnswerResult }).recorded, conflict: true };
      return { result: data as AnswerResult, conflict: false };
    },

    /** The result card was copied or shared: counted once, so never retried. */
    async shared(): Promise<void> {
      await request({ method: "POST", path: "/shares", idempotent: false });
    },

    /** Creating twice returns the same challenge, so a retry is safe. */
    async createChallenge(playId: string): Promise<ChallengeCreated> {
      return (await request({ method: "POST", path: "/challenges", body: { playId }, idempotent: true }))
        .body as ChallengeCreated;
    },

    /** Records a colleague's finished play the first time only, so a retry is safe. */
    async getChallenge(challengeId: string): Promise<ChallengeView> {
      return (
        await request({ method: "GET", path: `/challenges/${encodeURIComponent(challengeId)}`, idempotent: true })
      ).body as ChallengeView;
    },
  };
}

export type ApiClient = ReturnType<typeof createClient>;
