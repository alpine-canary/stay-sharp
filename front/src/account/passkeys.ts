// Passkeys in the browser (task T217, FR-105): the WebAuthn API, with the JSON shapes Cognito
// sends and expects (base64url for every binary field). No library.

type Json = Record<string, unknown>;

export function passkeysSupported(): boolean {
  return typeof window !== "undefined" && typeof window.PublicKeyCredential === "function" && !!navigator.credentials;
}

export function fromB64url(text: string): ArrayBuffer {
  const base64 = text.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(text.length / 4) * 4, "=");
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

export function toB64url(buffer: ArrayBuffer | ArrayBufferView): string {
  const bytes = buffer instanceof ArrayBuffer ? new Uint8Array(buffer) : new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function descriptors(list: unknown): PublicKeyCredentialDescriptor[] | undefined {
  if (!Array.isArray(list)) return undefined;
  return (list as Json[]).map((d) => ({ ...(d as object), type: "public-key", id: fromB64url(String(d.id)) }));
}

export function creationOptions(json: Json): PublicKeyCredentialCreationOptions {
  const user = json.user as Json;
  const options = {
    ...json,
    challenge: fromB64url(String(json.challenge)),
    user: { ...user, id: fromB64url(String(user.id)) },
  } as unknown as PublicKeyCredentialCreationOptions;
  const exclude = descriptors(json.excludeCredentials);
  if (exclude) options.excludeCredentials = exclude;
  return options;
}

export function requestOptions(json: Json): PublicKeyCredentialRequestOptions {
  const options = { ...json, challenge: fromB64url(String(json.challenge)) } as unknown as PublicKeyCredentialRequestOptions;
  const allow = descriptors(json.allowCredentials);
  if (allow) options.allowCredentials = allow;
  return options;
}

/** A credential as JSON, as Cognito expects it (what PublicKeyCredential.toJSON() gives). */
export function credentialJson(credential: PublicKeyCredential): Json {
  const response = credential.response as AuthenticatorAttestationResponse & AuthenticatorAssertionResponse;
  const out: Json = { clientDataJSON: toB64url(response.clientDataJSON) };
  if ("attestationObject" in response && response.attestationObject) {
    out.attestationObject = toB64url(response.attestationObject);
    out.transports = typeof response.getTransports === "function" ? response.getTransports() : [];
  }
  if ("authenticatorData" in response && response.authenticatorData) {
    out.authenticatorData = toB64url(response.authenticatorData);
    out.signature = toB64url(response.signature);
    if (response.userHandle) out.userHandle = toB64url(response.userHandle);
  }
  return {
    id: credential.id,
    rawId: toB64url(credential.rawId),
    type: credential.type,
    response: out,
    clientExtensionResults: credential.getClientExtensionResults(),
    authenticatorAttachment: credential.authenticatorAttachment ?? undefined,
  };
}

export async function createPasskey(options: Json): Promise<Json> {
  const credential = (await navigator.credentials.create({ publicKey: creationOptions(options) })) as PublicKeyCredential | null;
  if (!credential) throw new Error("no credential");
  return credentialJson(credential);
}

export async function usePasskey(options: Json): Promise<Json> {
  const credential = (await navigator.credentials.get({ publicKey: requestOptions(options) })) as PublicKeyCredential | null;
  if (!credential) throw new Error("no credential");
  return credentialJson(credential);
}
