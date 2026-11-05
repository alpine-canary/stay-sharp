// Practice page (task T112, Story 5, FR-021 to FR-023).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError, type AnswerResult, type ApiClient, type PracticeNext } from "../api/client";
import { freshPractice, recordPractice } from "../progress/boxes";
import { Practice } from "./Practice";

const NEXT: PracticeNext = {
  attemptId: "ABCDEFGHJKMNPQRS",
  qid: "proto_acr01",
  question: {
    index: 0,
    deck: "acronym",
    prompt: "What does a DLQ hold?",
    choices: [
      { id: "AAAAAAAA", text: "Messages that kept failing" },
      { id: "BBBBBBBB", text: "Logs" },
      { id: "CCCCCCCC", text: "Secrets" },
      { id: "DDDDDDDD", text: "Metrics" },
    ],
    servedAt: new Date().toISOString(),
  },
};

const WRONG: AnswerResult = {
  grade: 0,
  bonus: 0,
  elapsedMs: 4000,
  correctChoiceId: "AAAAAAAA",
  explanation: "A dead-letter queue keeps what could not be processed.",
  duplicate: false,
};

function client(extra: Partial<ApiClient>): ApiClient {
  return { practiceNext: vi.fn().mockResolvedValue(NEXT), practiceAnswer: vi.fn(), ...extra } as unknown as ApiClient;
}

describe("Practice", () => {
  it("asks for due questions first and shows the same feedback as the daily", async () => {
    const practice = recordPractice(recordPractice(freshPractice(), { qid: "missed", deck: "spot", grade: 0, duplicate: false }), {
      qid: "other",
      deck: "news",
      grade: 1,
      duplicate: false,
    });
    const practiceAnswer = vi.fn().mockResolvedValue({ result: WRONG, conflict: false });
    const api = client({ practiceAnswer });
    const onAnswered = vi.fn();
    render(<Practice client={api} level="senior" practice={practice} onAnswered={onAnswered} />);

    expect(await screen.findByRole("heading", { name: "What does a DLQ hold?" })).toBeInTheDocument();
    expect(api.practiceNext).toHaveBeenCalledWith({ level: "senior", prefer: ["missed"] });

    await userEvent.click(screen.getByRole("radio", { name: "Logs" }));
    await userEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByText("Not this time")).toBeInTheDocument();
    expect(screen.getByText("Right answer:")).toBeInTheDocument();
    expect(screen.getByText(/dead-letter queue/)).toBeInTheDocument();
    expect(onAnswered).toHaveBeenCalledWith({ qid: "proto_acr01", deck: "acronym", grade: 0, duplicate: false });
    expect(screen.queryByText(/streak \d/)).not.toBeInTheDocument();
  });

  it("filters by deck", async () => {
    const api = client({});
    render(<Practice client={api} level="senior" practice={freshPractice()} onAnswered={vi.fn()} />);
    await screen.findByRole("heading", { name: "What does a DLQ hold?" });
    await userEvent.click(screen.getByRole("radio", { name: "AI this week" }));
    expect(api.practiceNext).toHaveBeenLastCalledWith({ level: "senior", deck: "news", prefer: [] });
  });

  it("counts a duplicate or conflicting answer once", async () => {
    const practiceAnswer = vi.fn().mockResolvedValue({ result: { ...WRONG, grade: 1 }, conflict: true });
    const onAnswered = vi.fn();
    render(<Practice client={client({ practiceAnswer })} level="senior" practice={freshPractice()} onAnswered={onAnswered} />);
    await userEvent.click(await screen.findByRole("radio", { name: "Logs" }));
    await userEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByText(/This is the answer that counts/)).toBeInTheDocument();
    expect(onAnswered).toHaveBeenCalledWith(expect.objectContaining({ duplicate: true }));
  });

  it.each([
    ["not_ready", 404, "There are no past questions for this deck yet."],
    ["rate_limited", 429, "That is 200 practice questions today. Come back tomorrow."],
  ] as const)("says so plainly on %s", async (code, status, text) => {
    const practiceNext = vi.fn().mockRejectedValue(new ApiError("http", "x", { status, code }));
    render(<Practice client={client({ practiceNext })} level="senior" practice={freshPractice()} onAnswered={vi.fn()} />);
    expect(await screen.findByText(text)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });
});
