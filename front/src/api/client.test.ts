import { describe, expect, it, vi } from "vitest";
import { ApiError, createClient } from "./client";

const PLAYER = "9f1c2b3a-4d5e-4f60-8a7b-1c2d3e4f5a6b";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function client(fetchImpl: typeof fetch, timeoutMs = 50) {
  return createClient({ playerId: () => PLAYER, fetchImpl, timeoutMs });
}

describe("api client", () => {
  it("reads /today without player id, so the prefetched response can be reused", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      json(200, { date: "2026-11-20", gameNumber: 5, weekStart: "2026-11-16", levels: [] }),
    );
    const today = await client(fetchImpl).today();
    expect(today.gameNumber).toBe(5);
    const [url, init] = fetchImpl.mock.calls[0] ?? [];
    expect(url).toBe("/api/v1/today");
    expect(init?.headers).toBeUndefined();
    expect(init?.cache).toBeUndefined();
  });

  it("sends the player id and no-store on player calls", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(200, { playId: "p" }));
    await client(fetchImpl).getPlay("2026-11-20.senior.daily");
    const [url, init] = fetchImpl.mock.calls[0] ?? [];
    expect(url).toBe("/api/v1/plays/2026-11-20.senior.daily");
    expect((init?.headers as Record<string, string>)["X-Player-Id"]).toBe(PLAYER);
    expect(init?.cache).toBe("no-store");
  });

  it("sends the campaign source on player calls when the visit has one", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(200, { playId: "p" }));
    await createClient({ playerId: () => PLAYER, source: () => "linkedin", fetchImpl }).getPlay("2026-11-20.senior.daily");
    const [, init] = fetchImpl.mock.calls[0] ?? [];
    expect((init?.headers as Record<string, string>)["X-Source"]).toBe("linkedin");
  });

  it("sends no source header without a campaign source", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(200, { playId: "p" }));
    await client(fetchImpl).getPlay("2026-11-20.senior.daily");
    const [, init] = fetchImpl.mock.calls[0] ?? [];
    expect(init?.headers as Record<string, string>).not.toHaveProperty("X-Source");
  });

  it("retries an idempotent call once after a network error", async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValue(json(200, { grade: 1, bonus: 0, elapsedMs: 1, correctChoiceId: "A", explanation: "x", duplicate: true }));
    const { result } = await client(fetchImpl).answer("2026-11-20.senior.daily", 0, { choiceId: "AAAAAAAA" });
    expect(result.duplicate).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("gives up after one retry", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await client(fetchImpl).today().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).kind).toBe("network");
    expect((error as ApiError).serviceDown).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("does not retry an HTTP error", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(400, { code: "invalid_request", message: "Bad." }));
    const error = (await client(fetchImpl).getPlay("x").catch((e: unknown) => e)) as ApiError;
    expect(error.kind).toBe("http");
    expect(error.status).toBe(400);
    expect(error.code).toBe("invalid_request");
    expect(error.message).toBe("Bad.");
    expect(error.serviceDown).toBe(false);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("treats a 5xx as service down", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(503, { code: "unavailable", message: "Try again." }));
    const error = (await client(fetchImpl).today().catch((e: unknown) => e)) as ApiError;
    expect(error.serviceDown).toBe(true);
  });

  it("times out", async () => {
    const fetchImpl = vi.fn<typeof fetch>((_url, init) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
    });
    const error = (await client(fetchImpl, 10).today().catch((e: unknown) => e)) as ApiError;
    expect(error.kind).toBe("timeout");
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("returns the stored result on a 409 conflict", async () => {
    const recorded = { grade: 0, bonus: 0, elapsedMs: 5, correctChoiceId: "B", explanation: "x", duplicate: false };
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(409, { code: "conflict", recorded }));
    const { result, conflict } = await client(fetchImpl).answer("p", 1, { choiceId: "AAAAAAAA" });
    expect(conflict).toBe(true);
    expect(result).toEqual(recorded);
  });

  it("tells a new play from a resumed one", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(201, { playId: "p" }));
    expect((await client(fetchImpl).startPlay({ level: "senior", mode: "daily" })).created).toBe(true);
  });
});
