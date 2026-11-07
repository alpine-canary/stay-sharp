import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SignInError, type Cognito, type Pending, type Tokens } from "../cognito";
import { SignIn, type PasskeyDevice } from "./SignIn";

const NO_PASSKEYS: PasskeyDevice = { supported: () => false, get: vi.fn() };

const TOKENS: Tokens = { accessToken: "a", idToken: "i", refreshToken: "r", expiresAt: 1 };
const PENDING: Pending = { email: "player@example.test", step: "otp", session: "s" };

function fakeCognito(overrides: Partial<Cognito> = {}): Cognito {
  return {
    start: vi.fn().mockResolvedValue(PENDING),
    answer: vi.fn().mockResolvedValue(TOKENS),
    resend: vi.fn().mockResolvedValue({ ...PENDING, session: "s2" }),
    startPasskey: vi.fn().mockResolvedValue({ email: PENDING.email, session: "wa", options: { challenge: "AQID" } }),
    finishPasskey: vi.fn().mockResolvedValue(TOKENS),
    refresh: vi.fn(),
    signOut: vi.fn(),
    ...overrides,
  } as Cognito;
}

describe("SignIn", () => {
  it("signs in by keyboard alone: e-mail, keep me signed in, pasted code", async () => {
    const user = userEvent.setup();
    const cognito = fakeCognito();
    const onSignedIn = vi.fn();
    render(<SignIn cognito={cognito} onSignedIn={onSignedIn} passkeys={NO_PASSKEYS} />);
    expect(screen.getByRole("heading", { level: 1, name: "Your e-mail" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).toBeNull();

    await user.type(screen.getByLabelText("E-mail address"), "player@example.test");
    await user.click(screen.getByRole("checkbox", { name: "Keep me signed in on this device" }));
    await user.keyboard("{Enter}");
    expect(cognito.start).toHaveBeenCalledWith("player@example.test");

    const heading = await screen.findByRole("heading", { level: 1, name: "Check your e-mail" });
    expect(heading).toHaveFocus();
    const code = screen.getByLabelText("Code");
    expect(code).toHaveAttribute("autocomplete", "one-time-code");
    expect(code).toHaveAttribute("inputmode", "numeric");
    expect(code).not.toHaveAttribute("maxlength");
    await user.click(code);
    await user.paste("123 456");
    await user.keyboard("{Enter}");
    expect(cognito.answer).toHaveBeenCalledWith(PENDING, "123 456");
    expect(onSignedIn).toHaveBeenCalledWith(TOKENS, true);
  });

  it("shows a refused code in plain words, tied to the field", async () => {
    const user = userEvent.setup();
    const cognito = fakeCognito({ answer: vi.fn().mockRejectedValue(new SignInError("code")) });
    render(<SignIn cognito={cognito} onSignedIn={vi.fn()} passkeys={NO_PASSKEYS} />);
    await user.type(screen.getByLabelText("E-mail address"), "player@example.test{Enter}");
    await user.type(await screen.findByLabelText("Code"), "000000{Enter}");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("That code did not work. Check it, or ask for a new one.");
    expect(screen.getByLabelText("Code")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Code")).toHaveAttribute("aria-describedby", alert.id);
  });

  it("sends a new code and goes back to the e-mail", async () => {
    const user = userEvent.setup();
    const cognito = fakeCognito();
    render(<SignIn cognito={cognito} onSignedIn={vi.fn()} passkeys={NO_PASSKEYS} />);
    await user.type(screen.getByLabelText("E-mail address"), "player@example.test{Enter}");
    await user.click(await screen.findByRole("button", { name: "Send a new code" }));
    expect(cognito.resend).toHaveBeenCalledWith(PENDING);
    expect(await screen.findByRole("status")).toHaveTextContent("A new code is on its way.");
    await user.click(screen.getByRole("button", { name: "Use another e-mail" }));
    expect(screen.getByRole("heading", { level: 1, name: "Your e-mail" })).toBeInTheDocument();
  });

  it("says when sign-in is down, and keeps the e-mail typed", async () => {
    const user = userEvent.setup();
    const cognito = fakeCognito({ start: vi.fn().mockRejectedValue(new SignInError("unavailable")) });
    render(<SignIn cognito={cognito} onSignedIn={vi.fn()} passkeys={NO_PASSKEYS} />);
    await user.type(screen.getByLabelText("E-mail address"), "player@example.test{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent(/not available right now/);
    expect(screen.getByLabelText("E-mail address")).toHaveValue("player@example.test");
    expect(screen.getByRole("button", { name: "Send me a code" })).toBeEnabled();
  });

  it("signs in with a passkey when the device has one", async () => {
    const user = userEvent.setup();
    const cognito = fakeCognito();
    const onSignedIn = vi.fn();
    const device: PasskeyDevice = { supported: () => true, get: vi.fn().mockResolvedValue({ id: "cred" }) };
    render(<SignIn cognito={cognito} onSignedIn={onSignedIn} passkeys={device} />);
    await user.type(screen.getByLabelText("E-mail address"), "player@example.test");
    await user.click(screen.getByRole("button", { name: "Sign in with a passkey instead" }));
    expect(device.get).toHaveBeenCalledWith({ challenge: "AQID" });
    expect(cognito.finishPasskey).toHaveBeenCalledWith(expect.objectContaining({ session: "wa" }), { id: "cred" });
    expect(onSignedIn).toHaveBeenCalledWith(TOKENS, false);
  });

  it("a cancelled passkey points to the e-mail code", async () => {
    const user = userEvent.setup();
    const device: PasskeyDevice = { supported: () => true, get: vi.fn().mockRejectedValue(new DOMException("x", "NotAllowedError")) };
    render(<SignIn cognito={fakeCognito()} onSignedIn={vi.fn()} passkeys={device} />);
    await user.type(screen.getByLabelText("E-mail address"), "player@example.test");
    await user.click(screen.getByRole("button", { name: "Sign in with a passkey instead" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That passkey did not work on this device. Ask for a code instead.");
  });

  it("no passkey button where the browser has none", () => {
    render(<SignIn cognito={fakeCognito()} onSignedIn={vi.fn()} passkeys={NO_PASSKEYS} />);
    expect(screen.queryByRole("button", { name: /passkey/ })).toBeNull();
  });
});
