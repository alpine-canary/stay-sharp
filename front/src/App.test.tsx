import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { ApiError, type ApiClient } from "./api/client";
import { createStore, STORAGE_KEY } from "./storage";
import { route } from "./router";

function fakeClient(today: ApiClient["today"]): ApiClient {
  return { today } as ApiClient;
}

const TODAY = { date: "2026-11-20", gameNumber: 5, weekStart: "2026-11-16", levels: [] };

afterEach(() => {
  window.history.pushState(null, "", "/");
  window.localStorage.clear();
});

describe("routes", () => {
  it.each([
    ["/", "home"],
    ["/play", "play"],
    ["/practice/", "practice"],
    ["/privacy", "privacy"],
    ["/c/ABCDEFGHJKLM", "challenge"],
    ["/c/short", "not-found"],
    ["/nope", "not-found"],
  ])("%s is %s", (path, view) => {
    expect(route(path).view).toBe(view);
  });
});

describe("shell", () => {
  it("shows today's game number", async () => {
    render(<App store={createStore(window.localStorage)} client={fakeClient(() => Promise.resolve(TODAY))} />);
    expect(await screen.findByRole("heading", { name: "Today's set #5" })).toBeInTheDocument();
  });

  it("remembers the level choice in storage", async () => {
    const user = userEvent.setup();
    render(<App store={createStore(window.localStorage)} client={fakeClient(() => Promise.resolve(TODAY))} />);
    await user.click(screen.getByRole("radio", { name: "Starter" }));
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}").level).toBe("starter");
    expect(screen.getByRole("radio", { name: "Starter" })).toBeChecked();
  });

  it("shows a plain message and a retry button when the service is down", async () => {
    const user = userEvent.setup();
    const today = vi
      .fn<ApiClient["today"]>()
      .mockRejectedValueOnce(new ApiError("network", "Could not reach the server."))
      .mockResolvedValue(TODAY);
    render(<App store={createStore(window.localStorage)} client={fakeClient(today)} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The game is not reachable right now.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Today's set #5" })).toBeInTheDocument();
  });

  it("tells the player when saved progress was reset", async () => {
    window.localStorage.setItem(STORAGE_KEY, "{broken");
    render(<App store={createStore(window.localStorage)} client={fakeClient(() => Promise.resolve(TODAY))} />);
    expect(screen.getByText(/could not be read/).closest('[role="status"]')).not.toBeNull();
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
  });

  it("shows a not-found view for an unknown path", () => {
    window.history.pushState(null, "", "/nope");
    render(<App store={createStore(window.localStorage)} client={fakeClient(() => Promise.resolve(TODAY))} />);
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
