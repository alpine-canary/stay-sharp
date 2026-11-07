import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AccountApiError, type AccountApi } from "../api";
import { DeleteAccount } from "./DeleteAccount";

function api(deleteAccount: () => Promise<void>): AccountApi {
  return { deleteAccount: vi.fn(deleteAccount) } as unknown as AccountApi;
}

describe("DeleteAccount (T234)", () => {
  it("says what goes, asks once, and reports only after the server is done", async () => {
    const user = userEvent.setup();
    let finish: () => void = () => undefined;
    const a = api(() => new Promise<void>((resolve) => (finish = resolve)));
    const onDeleted = vi.fn();
    render(<DeleteAccount api={a} onDeleted={onDeleted} />);
    expect(screen.getByText(/your e-mail, your games, your streak and your progress, on every device/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(screen.getByRole("heading", { name: "Delete your account for good?" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Yes, delete everything" }));
    expect(screen.getByRole("button", { name: "Deleting…" })).toBeDisabled();
    expect(onDeleted).not.toHaveBeenCalled();
    finish();
    await vi.waitFor(() => expect(onDeleted).toHaveBeenCalledOnce());
  });

  it("503: not finished, try again; nothing is reported as deleted", async () => {
    const user = userEvent.setup();
    const a = api(() => Promise.reject(new AccountApiError(503, "unavailable")));
    const onDeleted = vi.fn();
    render(<DeleteAccount api={a} onDeleted={onDeleted} />);
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    await user.click(screen.getByRole("button", { name: "Yes, delete everything" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Deleting has started but is not finished. Please try again in a minute.");
    expect(onDeleted).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Yes, delete everything" })).toBeEnabled();
  });

  it.each([
    [new AccountApiError(500, null)],
    [new AccountApiError(0, null)],
  ])("a timeout or a lost answer never claims that nothing was deleted (%s)", async (failure) => {
    const user = userEvent.setup();
    render(<DeleteAccount api={api(() => Promise.reject(failure))} onDeleted={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    await user.click(screen.getByRole("button", { name: "Yes, delete everything" }));
    const alert = await screen.findByRole("alert");
    expect(alert).not.toHaveTextContent(/Nothing was deleted/);
    expect(alert).toHaveTextContent(/try again/i);
  });

  it("a refusal before anything started says nothing was deleted", async () => {
    const user = userEvent.setup();
    render(<DeleteAccount api={api(() => Promise.reject(new AccountApiError(401, "unauthorized")))} onDeleted={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    await user.click(screen.getByRole("button", { name: "Yes, delete everything" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Nothing was deleted/);
  });

  it("can be called off", async () => {
    const user = userEvent.setup();
    const a = api(() => Promise.resolve());
    render(<DeleteAccount api={a} onDeleted={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    await user.click(screen.getByRole("button", { name: "Keep my account" }));
    expect(a.deleteAccount).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete my account" })).toBeInTheDocument();
  });
});
