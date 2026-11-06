// Whether this browser has an account session, read without loading the account code (main
// bundle; the offer and the header link use it). Only key names, never a token value.

export const SESSION_KEY = "staysharp.session";
export const REFRESH_KEY = "staysharp.refresh";

function has(storage: () => Storage, key: string): boolean {
  try {
    return storage().getItem(key) !== null;
  } catch {
    return false;
  }
}

export function signedInHint(): boolean {
  return has(() => window.sessionStorage, SESSION_KEY) || has(() => window.localStorage, REFRESH_KEY);
}
