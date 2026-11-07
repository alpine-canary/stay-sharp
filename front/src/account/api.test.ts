import { describe, expect, it, vi } from "vitest";
import { AccountApiError, createAccountApi } from "./api";

const token = () => Promise.resolve("acc");

describe("account API client (T249 review)", () => {
  it("a body that is not JSON is an error with the status, never a crash", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502 }));
    const api = createAccountApi({ token, fetchImpl });
    await expect(api.getProgress()).rejects.toEqual(new AccountApiError(502, null));
  });

  it("a request that hangs gives up, as offline (status 0)", async () => {
    let signal: AbortSignal | null | undefined;
    const fetchImpl = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      signal = init?.signal;
      return Promise.reject(new DOMException("timed out", "TimeoutError"));
    });
    const api = createAccountApi({ token, fetchImpl });
    const failure = await api.getProgress().catch((e: unknown) => e);
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(failure).toBeInstanceOf(AccountApiError);
    expect((failure as AccountApiError).status).toBe(0);
  });
});
