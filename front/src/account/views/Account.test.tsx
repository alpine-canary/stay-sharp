import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { freshProgress } from "../../storage";
import type { AccountApi } from "../api";
import type { Cognito } from "../cognito";
import type { Session } from "../session";
import { Account as AccountView, type AccountProps, type PasskeyMaker } from "./Account";

const ID = "11111111-1111-4111-8111-111111111111";
const progress = freshProgress(ID);
const joinedApi = { me: vi.fn().mockResolvedValue({ primaryPlayerId: ID, createdAt: "x" }) } as unknown as AccountApi;

function Account({ cognito, session, passkeys, api = joinedApi }: { cognito: Cognito; session: Session; passkeys: PasskeyMaker; api?: AccountApi }) {
  const props: AccountProps = { runtime: { cognito, session, api }, current: () => progress, replace: vi.fn(), passkeys };
  return <AccountView {...props} />;
}

function session(): Session {
  return { email: () => "player@example.test", accessToken: vi.fn().mockResolvedValue("acc") } as unknown as Session;
}

function cognito(list: { id: string; name: string; createdAt: number | null }[][]): Cognito {
  const listPasskeys = vi.fn();
  for (const l of list) listPasskeys.mockResolvedValueOnce(l);
  listPasskeys.mockResolvedValue(list.at(-1));
  return {
    listPasskeys,
    startRegistration: vi.fn().mockResolvedValue({ challenge: "AQID" }),
    completeRegistration: vi.fn().mockResolvedValue(undefined),
    removePasskey: vi.fn().mockResolvedValue(undefined),
  } as unknown as Cognito;
}

describe("Account passkeys (FR-105)", () => {
  it("adds a passkey and lists it", async () => {
    const user = userEvent.setup();
    const c = cognito([[], [{ id: "c1", name: "Passkey", createdAt: Date.UTC(2026, 10, 6) }]]);
    const maker: PasskeyMaker = { supported: () => true, create: vi.fn().mockResolvedValue({ id: "c1" }) };
    render(<Account cognito={c} session={session()} passkeys={maker} />);
    expect(screen.getByText("Signed in as player@example.test.")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Add a passkey" }));
    expect(maker.create).toHaveBeenCalledWith({ challenge: "AQID" });
    expect(c.completeRegistration).toHaveBeenCalledWith("acc", { id: "c1" });
    expect(await screen.findByText("Passkey added. Next time, sign in with it instead of a code.")).toBeInTheDocument();
    expect(screen.getByText(/added 6 Nov 2026/)).toBeInTheDocument();
  });

  it("removes a passkey by its own named button", async () => {
    const user = userEvent.setup();
    const c = cognito([[{ id: "c1", name: "Passkey", createdAt: null }], []]);
    render(<Account cognito={c} session={session()} passkeys={{ supported: () => true, create: vi.fn() }} />);
    await user.click(await screen.findByRole("button", { name: "Remove Passkey" }));
    expect(c.removePasskey).toHaveBeenCalledWith("acc", "c1");
    expect(await screen.findByText("Passkey removed.")).toBeInTheDocument();
  });

  it("a cancelled passkey changes nothing and says so", async () => {
    const user = userEvent.setup();
    const c = cognito([[]]);
    const maker: PasskeyMaker = { supported: () => true, create: vi.fn().mockRejectedValue(new DOMException("x", "NotAllowedError")) };
    render(<Account cognito={c} session={session()} passkeys={maker} />);
    await user.click(await screen.findByRole("button", { name: "Add a passkey" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No passkey was added.");
    expect(c.completeRegistration).not.toHaveBeenCalled();
  });

  it("no passkey section where the browser has none", () => {
    render(<Account cognito={cognito([[]])} session={session()} passkeys={{ supported: () => false, create: vi.fn() }} />);
    expect(screen.queryByRole("heading", { name: "Passkeys" })).toBeNull();
  });

  it("joins this browser to the account when it is not yet", async () => {
    const api = {
      me: vi.fn().mockResolvedValue(null),
      adopt: vi.fn().mockResolvedValue({ primaryPlayerId: ID, created: true, merged: { plays: 0, replays: 0 } }),
      getProgress: vi.fn().mockResolvedValue({ version: 0, body: {} }),
      putProgress: vi.fn().mockResolvedValue({ stored: { version: 1, body: {} }, conflict: false }),
    } as unknown as AccountApi;
    render(<Account cognito={cognito([[]])} session={session()} passkeys={{ supported: () => false, create: vi.fn() }} api={api} />);
    expect(await screen.findByText(/Your streak and progress are saved to your account/)).toBeInTheDocument();
    expect(api.adopt).toHaveBeenCalledWith(ID);
    expect(JSON.parse(window.localStorage.getItem("staysharp.sync") ?? "{}")).toEqual({ version: 1, pending: false });
  });

  it("says when the account cannot be reached, and keeps the progress", async () => {
    const { AccountApiError } = await import("../api");
    const api = { me: vi.fn().mockRejectedValue(new AccountApiError(0, null)) } as unknown as AccountApi;
    render(<Account cognito={cognito([[]])} session={session()} passkeys={{ supported: () => false, create: vi.fn() }} api={api} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be reached/);
  });
});
