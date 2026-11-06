import { describe, expect, it } from "vitest";
import { creationOptions, fromB64url, requestOptions, toB64url } from "./passkeys";

describe("passkey JSON", () => {
  it("round-trips base64url without padding", () => {
    for (const text of ["", "AA", "AAE", "_-8", "aGVsbG8gd29ybGQ"]) {
      expect(toB64url(fromB64url(text))).toBe(text);
    }
    expect(toB64url(new Uint8Array([251, 255]))).toBe("-_8");
  });

  it("turns Cognito's creation options into WebAuthn options", () => {
    const options = creationOptions({
      challenge: "AQID",
      rp: { id: "localhost", name: "Stay Sharp" },
      user: { id: "BAU", name: "a@example.test", displayName: "a@example.test" },
      pubKeyCredParams: [{ type: "public-key", alg: -7 }],
      excludeCredentials: [{ type: "public-key", id: "Bg" }],
    });
    expect(new Uint8Array(options.challenge as ArrayBuffer)).toEqual(new Uint8Array([1, 2, 3]));
    expect(new Uint8Array(options.user.id as ArrayBuffer)).toEqual(new Uint8Array([4, 5]));
    expect(new Uint8Array(options.excludeCredentials?.[0]?.id as ArrayBuffer)).toEqual(new Uint8Array([6]));
    expect(options.rp.id).toBe("localhost");
  });

  it("turns request options into WebAuthn options", () => {
    const options = requestOptions({ challenge: "AQID", rpId: "localhost", allowCredentials: [] });
    expect(options.rpId).toBe("localhost");
    expect(options.allowCredentials).toEqual([]);
  });
});
