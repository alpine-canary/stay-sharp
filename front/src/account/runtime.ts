// The account pieces for this browser: sign-in client, session, account API.

import { createAccountApi, type AccountApi } from "./api";
import { createCognito, type AuthConfig, type Cognito } from "./cognito";
import { createSession, type Session } from "./session";

export interface Runtime {
  cognito: Cognito;
  session: Session;
  api: AccountApi;
}

function safe(get: () => Storage): Storage | null {
  try {
    return get();
  } catch {
    return null;
  }
}

export function browserSession(cognito: Cognito): Session {
  return createSession({
    session: safe(() => window.sessionStorage),
    local: safe(() => window.localStorage),
    refresh: (token) => cognito.refresh(token),
  });
}

export function localStorageOrNull(): Storage | null {
  return safe(() => window.localStorage);
}

export function makeRuntime(config: AuthConfig, makeSession: (c: Cognito) => Session = browserSession): Runtime {
  const cognito = createCognito(config);
  const session = makeSession(cognito);
  return { cognito, session, api: createAccountApi({ token: (force) => session.accessToken(force) }) };
}
