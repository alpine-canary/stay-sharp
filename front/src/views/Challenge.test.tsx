// Challenge page states (task T107, Story 4 scenarios 1 to 5).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient, type ChallengeView, type ResultSnapshot, type Today } from "../api/client";
import { Challenge } from "./Challenge";

const TODAY: Today = { date: "2026-11-20", gameNumber: 20, weekStart: "2026-11-16", levels: [] };
const OWNER: ResultSnapshot = { grades: [1, 1, 0, 0.5, 1], score: 3.5, bonus: 0.4, elapsedMs: 125_000, relaxed: false };
const YOU: ResultSnapshot = { grades: [1, 1, 1, 1, 0], score: 4, bonus: 0, elapsedMs: 200_000, relaxed: true };

function challenge(extra: Partial<ChallengeView>): ChallengeView {
  return {
    challengeId: "ABCDEFGHJKMN",
    date: "2026-11-20",
    level: "senior",
    gameNumber: 20,
    viewer: "colleague_before",
    ownerScore: 3.5,
    others: 0,
    ...extra,
  };
}

function client(get: ApiClient["getChallenge"], startPlay = vi.fn()): ApiClient {
  return {
    today: () => Promise.resolve(TODAY),
    getChallenge: get,
    startPlay,
  } as unknown as ApiClient;
}

function show(get: ApiClient["getChallenge"], startPlay = vi.fn()) {
  render(<Challenge client={client(get, startPlay)} challengeId="ABCDEFGHJKMN" relaxed={false} onFinished={vi.fn()} />);
}

describe("Challenge", () => {
  it("shows a colleague only the owner's score before they play", async () => {
    show(() => Promise.resolve(challenge({})));
    expect(await screen.findByRole("heading", { name: "A colleague scored 3.5/5" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: /answers, question by question/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Play this set" })).toBeInTheDocument();
    expect(screen.queryByText(/does not count for your streak/)).not.toBeInTheDocument();
  });

  it("starts the challenge's own set, as a replay when the set is past", async () => {
    const startPlay = vi.fn().mockReturnValue(new Promise(() => undefined));
    show(() => Promise.resolve(challenge({ date: "2026-11-18" })), startPlay);
    expect(await screen.findByText(/This set is from 2026-11-18\. It does not count for your streak\./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Play this set" }));
    expect(startPlay).toHaveBeenCalledWith({
      level: "senior",
      mode: "replay",
      relaxed: false,
      challengeId: "ABCDEFGHJKMN",
      date: "2026-11-18",
    });
  });

  it("shows both results side by side after finishing", async () => {
    show(() => Promise.resolve(challenge({ viewer: "colleague_after", owner: OWNER, you: YOU, others: 3 })));
    expect(await screen.findByRole("heading", { name: "You came out ahead" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "You: answers, question by question" })).toHaveTextContent(
      "Question 5 (AI this week): wrong",
    );
    expect(screen.getByRole("list", { name: "Your colleague: answers, question by question" })).toHaveTextContent(
      "Question 4 (Acronym or tool): half right",
    );
    expect(screen.getByText("2:05")).toBeInTheDocument();
    expect(screen.getByText("no bonus")).toBeInTheDocument();
    expect(screen.getByText("2 other colleagues also took this challenge.")).toBeInTheDocument();
  });

  it("shows the owner their result and the colleagues who finished, never a play button", async () => {
    show(() => Promise.resolve(challenge({ viewer: "owner", owner: OWNER, colleagues: [YOU], others: 1 })));
    expect(await screen.findByRole("heading", { name: "Your challenge" })).toBeInTheDocument();
    expect(screen.getByText("1 colleague has finished it.")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Colleague 1: answers, question by question" })).toBeInTheDocument();
    expect(screen.getByText(/\/c\/ABCDEFGHJKMN$/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy link" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Play this set" })).not.toBeInTheDocument();
  });

  it.each([
    ["not_found", "This challenge link does not work"],
    ["expired", "This challenge has ended"],
  ] as const)("a %s link gets a plain message and today's daily", async (code, title) => {
    show(() => Promise.reject(new ApiError("http", "server words", { status: 404, code })));
    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Play today's daily" })).toHaveAttribute("href", "/");
    expect(screen.queryByText("server words")).not.toBeInTheDocument();
  });

  it("offers a retry when the game is not reachable", async () => {
    const get = vi
      .fn()
      .mockRejectedValueOnce(new ApiError("network", "Could not reach the server."))
      .mockResolvedValueOnce(challenge({}));
    show(get);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "A colleague scored 3.5/5" })).toBeInTheDocument();
  });
});
