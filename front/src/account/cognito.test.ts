import { describe, expect, it, vi } from "vitest";
import { createCognito, SignInError, type AuthConfig } from "./cognito";

const CONFIG: AuthConfig = { endpoint: "https://cognito.test/", clientId: "client-1" };
const EMAIL = "player@example.test";
const TOKENS = { AccessToken: "acc", IdToken: "id", RefreshToken: "ref", ExpiresIn: 3600, TokenType: "Bearer" };

type Reply = [number, unknown];

/** A fetch that answers each Cognito action from a script, and records the calls. */
function scripted(replies: Record<string, Reply | Reply[]>) {
  const calls: { action: string; body: Record<string, unknown>; headers: Record<string, string> }[] = [];
  const queues = new Map(Object.entries(replies).map(([k, v]) => [k, (Array.isArray(v[0]) ? v : [v]) as Reply[]]));
  const fetchImpl = vi.fn<typeof fetch>(async (_url, init) => {
    const headers = init?.headers as Record<string, string>;
    const action = (headers["X-Amz-Target"] ?? "").replace("AWSCognitoIdentityProviderService.", "");
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    calls.push({ action, body, headers });
    const queue = queues.get(action);
    const reply = queue && queue.length > 1 ? queue.shift() : queue?.[0];
    if (!reply) throw new Error(`unexpected ${action}`);
    return new Response(JSON.stringify(reply[1]), { status: reply[0] });
  });
  return { cognito: createCognito(CONFIG, fetchImpl, () => 1_000_000), calls, fetchImpl };
}

const err = (type: string, message = "x"): Reply => [400, { __type: type, message }];

describe("cognito client", () => {
  it("signs a new player up without a password, then signs in with the confirm session", async () => {
    const { cognito, calls } = scripted({
      SignUp: [200, { UserConfirmed: false, UserSub: "s", Session: "up-session" }],
      ConfirmSignUp: [200, { Session: "confirm-session" }],
      InitiateAuth: [200, { AuthenticationResult: TOKENS }],
    });
    const pending = await cognito.start(EMAIL);
    const tokens = await cognito.answer(pending, "123456");
    expect(tokens).toEqual({ accessToken: "acc", idToken: "id", refreshToken: "ref", expiresAt: 1_000_000 + 3_600_000 });
    expect(calls.map((c) => c.action)).toEqual(["SignUp", "ConfirmSignUp", "InitiateAuth"]);
    const [signUp, confirm, initiate] = calls;
    expect(signUp?.body).toEqual({
      ClientId: "client-1",
      Username: EMAIL,
      UserAttributes: [{ Name: "email", Value: EMAIL }],
    });
    expect(signUp?.body).not.toHaveProperty("Password");
    expect(signUp?.headers["Content-Type"]).toBe("application/x-amz-json-1.1");
    expect(confirm?.body).toMatchObject({ ConfirmationCode: "123456", Session: "up-session" });
    expect(initiate?.body).toMatchObject({ AuthFlow: "USER_AUTH", Session: "confirm-session" });
  });

  it("asks a returning player for an e-mail code", async () => {
    const { cognito, calls } = scripted({
      SignUp: err("UsernameExistsException"),
      InitiateAuth: [200, { ChallengeName: "EMAIL_OTP", Session: "otp-session", ChallengeParameters: {} }],
      RespondToAuthChallenge: [200, { AuthenticationResult: TOKENS }],
    });
    const pending = await cognito.start(` ${EMAIL.toUpperCase()} `);
    await cognito.answer(pending, " 123 456 ");
    const [, initiate, respond] = calls;
    expect(initiate?.body).toEqual({
      ClientId: "client-1",
      AuthFlow: "USER_AUTH",
      AuthParameters: { USERNAME: EMAIL, PREFERRED_CHALLENGE: "EMAIL_OTP" },
    });
    expect(respond?.body).toEqual({
      ClientId: "client-1",
      ChallengeName: "EMAIL_OTP",
      Session: "otp-session",
      ChallengeResponses: { USERNAME: EMAIL, EMAIL_OTP_CODE: "123456" },
    });
  });

  it("resends: a new confirmation code for a new player, a new challenge for a returning one", async () => {
    const fresh = scripted({
      SignUp: [200, { UserConfirmed: false, UserSub: "s", Session: "up" }],
      ResendConfirmationCode: [200, { CodeDeliveryDetails: {} }],
    });
    const pendingNew = await fresh.cognito.start(EMAIL);
    expect(await fresh.cognito.resend(pendingNew)).toEqual(pendingNew);
    expect(fresh.calls.at(-1)?.body).toEqual({ ClientId: "client-1", Username: EMAIL });

    const back = scripted({
      SignUp: err("UsernameExistsException"),
      InitiateAuth: [
        [200, { ChallengeName: "EMAIL_OTP", Session: "one" }],
        [200, { ChallengeName: "EMAIL_OTP", Session: "two" }],
      ],
    });
    const pending = await back.cognito.start(EMAIL);
    expect((await back.cognito.resend(pending)).session).toBe("two");
  });

  it.each([
    ["CodeMismatchException", "code"],
    ["ExpiredCodeException", "expired"],
    ["NotAuthorizedException", "expired"],
    ["TooManyFailedAttemptsException", "throttled"],
    ["LimitExceededException", "throttled"],
    ["TooManyRequestsException", "throttled"],
    ["SomethingNewException", "unknown"],
  ])("maps %s to a plain %s message", async (type, kind) => {
    const { cognito } = scripted({
      SignUp: err("UsernameExistsException"),
      InitiateAuth: [200, { ChallengeName: "EMAIL_OTP", Session: "s" }],
      RespondToAuthChallenge: err(type),
    });
    const pending = await cognito.start(EMAIL);
    const failure = await cognito.answer(pending, "000000").catch((e: unknown) => e);
    expect(failure).toBeInstanceOf(SignInError);
    expect((failure as SignInError).kind).toBe(kind);
    expect((failure as SignInError).message).not.toMatch(/exist|registered|unknown user|not found/i);
  });

  it("never tells whether an e-mail has an account", async () => {
    const known = scripted({
      SignUp: err("UsernameExistsException"),
      InitiateAuth: [200, { ChallengeName: "EMAIL_OTP", Session: "s" }],
    });
    const unknown = scripted({ SignUp: [200, { UserConfirmed: false, UserSub: "s", Session: "s" }] });
    const a = await known.cognito.start(EMAIL);
    const b = await unknown.cognito.start(EMAIL);
    expect(Object.keys(a).sort()).toEqual(Object.keys(b).sort());
    expect(a.email).toBe(b.email);
  });

  it("refuses an e-mail that is not one, without calling the service", async () => {
    const { cognito, fetchImpl } = scripted({});
    const failure = await cognito.start("not an email").catch((e: unknown) => e);
    expect((failure as SignInError).kind).toBe("email");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("calls the service down when it does not answer or answers 5xx", async () => {
    const down = scripted({ SignUp: [503, { __type: "ServiceUnavailable" }] });
    expect(((await down.cognito.start(EMAIL).catch((e: unknown) => e)) as SignInError).kind).toBe("unavailable");
    const offline = createCognito(CONFIG, () => Promise.reject(new TypeError("Failed to fetch")));
    expect(((await offline.start(EMAIL).catch((e: unknown) => e)) as SignInError).kind).toBe("unavailable");
  });

  it("refreshes tokens and keeps the refresh token", async () => {
    const { cognito, calls } = scripted({
      InitiateAuth: [200, { AuthenticationResult: { AccessToken: "acc2", IdToken: "id2", ExpiresIn: 60 } }],
    });
    const tokens = await cognito.refresh("ref");
    expect(tokens).toEqual({ accessToken: "acc2", idToken: "id2", refreshToken: "ref", expiresAt: 1_000_000 + 60_000 });
    expect(calls[0]?.body).toEqual({
      ClientId: "client-1",
      AuthFlow: "REFRESH_TOKEN_AUTH",
      AuthParameters: { REFRESH_TOKEN: "ref" },
    });
  });

  it("signs out everywhere with the access token", async () => {
    const { cognito, calls } = scripted({ GlobalSignOut: [200, {}] });
    await cognito.signOut("acc");
    expect(calls[0]?.body).toEqual({ AccessToken: "acc" });
  });
});
