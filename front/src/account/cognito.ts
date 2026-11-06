// Sign-in without a password, straight against the Cognito user pool API (task T213,
// research A1, A9). No SDK: each call is one POST with an X-Amz-Target header.
//
// One path for everyone, so the screens never reveal whether an e-mail has an account:
// - start(email): try to sign up (no password). A new player gets a confirmation code; for an
//   existing account, Cognito says so and we start a choice-based sign-in with an e-mail code
//   instead. Either way the player sees "we sent you a code".
// - answer(pending, code): confirm the sign-up and sign in with the confirm session, or answer
//   the e-mail code challenge. Both give tokens.
//
// Nothing here logs or stores an e-mail, a code or a token; session.ts keeps the tokens.

export interface AuthConfig {
  /** The user pool API (https://cognito-idp.eu-central-2.amazonaws.com/), or /cognito locally. */
  endpoint: string;
  clientId: string;
}

export interface Tokens {
  accessToken: string;
  idToken: string;
  refreshToken?: string;
  /** Epoch milliseconds when the access token stops working. */
  expiresAt: number;
}

export interface Pending {
  email: string;
  /** "confirm": new account, waiting for the sign-up code; "otp": e-mail code challenge. */
  step: "confirm" | "otp";
  session: string;
}

export type SignInErrorKind = "email" | "code" | "expired" | "throttled" | "unavailable" | "unknown";

const MESSAGES: Record<SignInErrorKind, string> = {
  email: "Please enter a valid e-mail address.",
  code: "That code did not work. Check it, or ask for a new one.",
  expired: "That code has expired. Ask for a new one.",
  throttled: "Too many tries. Wait a few minutes, then ask for a new code.",
  unavailable: "Sign-in is not available right now. You can keep playing; try again later.",
  unknown: "Something went wrong. Please try again.",
};

export class SignInError extends Error {
  readonly kind: SignInErrorKind;
  constructor(kind: SignInErrorKind) {
    super(MESSAGES[kind]);
    this.name = "SignInError";
    this.kind = kind;
  }
}

/** Cognito error type to what the player is told. Unknown types stay vague on purpose. */
const KINDS: Record<string, SignInErrorKind> = {
  CodeMismatchException: "code",
  ExpiredCodeException: "expired",
  NotAuthorizedException: "expired",
  TooManyFailedAttemptsException: "throttled",
  LimitExceededException: "throttled",
  TooManyRequestsException: "throttled",
  CodeDeliveryFailureException: "unavailable",
  InvalidParameterException: "email",
};

class CognitoFailure extends Error {
  constructor(readonly type: string) {
    super(type);
  }
}

const TARGET = "AWSCognitoIdentityProviderService.";
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Body = Record<string, unknown>;

export function createCognito(
  config: AuthConfig,
  fetchImpl: typeof fetch = (input, init) => fetch(input, init),
  now: () => number = Date.now,
) {
  async function call(action: string, body: Body): Promise<Body> {
    let response: Response;
    try {
      response = await fetchImpl(config.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": TARGET + action },
        body: JSON.stringify(body),
        cache: "no-store",
        credentials: "omit",
      });
    } catch {
      throw new SignInError("unavailable");
    }
    if (response.status >= 500) throw new SignInError("unavailable");
    let parsed: Body = {};
    try {
      parsed = (await response.json()) as Body;
    } catch {
      if (!response.ok) throw new SignInError("unknown");
    }
    if (!response.ok) {
      // "__type" may come as "com.amazonaws...#NotAuthorizedException".
      const type = String(parsed.__type ?? "").split("#").pop() ?? "";
      throw new CognitoFailure(type);
    }
    return parsed;
  }

  async function friendly<T>(work: () => Promise<T>): Promise<T> {
    try {
      return await work();
    } catch (error) {
      if (error instanceof CognitoFailure) throw new SignInError(KINDS[error.type] ?? "unknown");
      throw error;
    }
  }

  function tokens(body: Body, refreshToken?: string): Tokens {
    const result = body.AuthenticationResult as Body | undefined;
    if (!result || typeof result.AccessToken !== "string" || typeof result.IdToken !== "string") {
      throw new SignInError("unknown");
    }
    const refresh = typeof result.RefreshToken === "string" ? result.RefreshToken : refreshToken;
    return {
      accessToken: result.AccessToken,
      idToken: result.IdToken,
      ...(refresh ? { refreshToken: refresh } : {}),
      expiresAt: now() + Number(result.ExpiresIn ?? 3600) * 1000,
    };
  }

  async function emailChallenge(email: string): Promise<Pending> {
    const body = await call("InitiateAuth", {
      ClientId: config.clientId,
      AuthFlow: "USER_AUTH",
      AuthParameters: { USERNAME: email, PREFERRED_CHALLENGE: "EMAIL_OTP" },
    });
    if (body.ChallengeName !== "EMAIL_OTP" || typeof body.Session !== "string") {
      throw new SignInError("unknown");
    }
    return { email, step: "otp", session: body.Session };
  }

  return {
    async start(rawEmail: string): Promise<Pending> {
      const email = rawEmail.trim().toLowerCase();
      if (!EMAIL.test(email)) throw new SignInError("email");
      return friendly(async () => {
        try {
          const body = await call("SignUp", {
            ClientId: config.clientId,
            Username: email,
            UserAttributes: [{ Name: "email", Value: email }],
          });
          return { email, step: "confirm", session: String(body.Session ?? "") };
        } catch (error) {
          if (error instanceof CognitoFailure && error.type === "UsernameExistsException") {
            return emailChallenge(email);
          }
          throw error;
        }
      });
    },

    async answer(pending: Pending, rawCode: string): Promise<Tokens> {
      const code = rawCode.replace(/\s+/g, "");
      return friendly(async () => {
        if (pending.step === "confirm") {
          const confirmed = await call("ConfirmSignUp", {
            ClientId: config.clientId,
            Username: pending.email,
            ConfirmationCode: code,
            Session: pending.session,
          });
          return tokens(
            await call("InitiateAuth", {
              ClientId: config.clientId,
              AuthFlow: "USER_AUTH",
              AuthParameters: { USERNAME: pending.email },
              Session: confirmed.Session,
            }),
          );
        }
        return tokens(
          await call("RespondToAuthChallenge", {
            ClientId: config.clientId,
            ChallengeName: "EMAIL_OTP",
            Session: pending.session,
            ChallengeResponses: { USERNAME: pending.email, EMAIL_OTP_CODE: code },
          }),
        );
      });
    },

    async resend(pending: Pending): Promise<Pending> {
      return friendly(async () => {
        if (pending.step === "confirm") {
          await call("ResendConfirmationCode", { ClientId: config.clientId, Username: pending.email });
          return pending;
        }
        return emailChallenge(pending.email);
      });
    },

    async refresh(refreshToken: string): Promise<Tokens> {
      return friendly(async () =>
        tokens(
          await call("InitiateAuth", {
            ClientId: config.clientId,
            AuthFlow: "REFRESH_TOKEN_AUTH",
            AuthParameters: { REFRESH_TOKEN: refreshToken },
          }),
          refreshToken,
        ),
      );
    },

    async signOut(accessToken: string): Promise<void> {
      await friendly(() => call("GlobalSignOut", { AccessToken: accessToken }));
    },
  };
}

export type Cognito = ReturnType<typeof createCognito>;

/** The stage's sign-in settings, written by the web stack (null when sign-in is not set up). */
export async function loadAuthConfig(fetchImpl: typeof fetch = (i, n) => fetch(i, n)): Promise<AuthConfig | null> {
  try {
    const response = await fetchImpl("/auth.json", { cache: "no-store" });
    if (!response.ok) return null;
    const body = (await response.json()) as Partial<AuthConfig>;
    if (typeof body.endpoint !== "string" || typeof body.clientId !== "string") return null;
    return { endpoint: body.endpoint, clientId: body.clientId };
  } catch {
    return null;
  }
}
