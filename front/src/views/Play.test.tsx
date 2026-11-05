import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError, type AnswerResult, type ApiClient, type PlayState, type QuestionView } from "../api/client";
import { Play } from "./Play";

const CHOICES = [
  { id: "AAAAAAAA", text: "Right one" },
  { id: "BBBBBBBB", text: "Wrong one" },
  { id: "CCCCCCCC", text: "Other" },
  { id: "DDDDDDDD", text: "Another" },
];

function view(index: number, deck = index === 0 ? "spot" : "better"): QuestionView {
  return {
    index,
    deck,
    prompt: `Question ${index + 1}?`,
    code: "x = 1\ny = x / 0\n",
    language: "python",
    choices: CHOICES,
    targetSeconds: 45,
    servedAt: new Date().toISOString(),
  };
}

function state(extra: Partial<PlayState> = {}): PlayState {
  return {
    playId: "2026-11-20.senior.daily",
    date: "2026-11-20",
    level: "senior",
    mode: "daily",
    gameNumber: 5,
    relaxed: false,
    grades: [null, null, null, null, null],
    score: 0,
    bonus: 0,
    finished: false,
    question: view(0),
    ...extra,
  };
}

const RIGHT: AnswerResult = {
  grade: 1,
  bonus: 0.2,
  elapsedMs: 4000,
  correctChoiceId: "AAAAAAAA",
  correctLines: [2],
  explanation: "Division by zero.",
  duplicate: false,
};

const NO_LINES: AnswerResult = { ...RIGHT };
delete NO_LINES.correctLines;

function client(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    today: vi.fn(),
    startPlay: vi.fn().mockResolvedValue({ created: true, play: state() }),
    getPlay: vi.fn().mockResolvedValue(state({ finished: true })),
    relax: vi.fn().mockResolvedValue(state({ relaxed: true })),
    open: vi.fn((_id: string, index: number) => Promise.resolve(view(index))),
    answer: vi.fn().mockResolvedValue({ result: RIGHT, conflict: false }),
    ...overrides,
  } as ApiClient;
}

describe("Play", () => {
  it("answers a spot question by keyboard only and shows the explanation", async () => {
    const user = userEvent.setup();
    const api = client();
    render(<Play client={api} level="senior" mode="daily" relaxed={false} onFinished={vi.fn()} />);

    expect(await screen.findByRole("heading", { name: "Question 1?" })).toHaveFocus();
    expect(screen.getByRole("button", { name: "Check" })).toBeDisabled();
    screen.getByRole("listbox").focus();
    await user.keyboard("{ArrowDown}{Enter}");
    await user.click(screen.getByRole("radio", { name: /Right one/ }));
    await user.keyboard("{Enter}");

    expect(api.answer).toHaveBeenCalledWith("2026-11-20.senior.daily", 0, { choiceId: "AAAAAAAA", line: 2 });
    const feedback = await screen.findByRole("status");
    expect(feedback).toHaveTextContent("Right · +0.2 speed bonus");
    expect(feedback).toHaveTextContent("Division by zero.");
  });

  it("sends one request for a double click", async () => {
    const user = userEvent.setup();
    let release: (value: { result: AnswerResult; conflict: boolean }) => void = () => undefined;
    const api = client({
      startPlay: vi.fn().mockResolvedValue({ created: true, play: state({ question: view(1, "better") }) }),
      answer: vi.fn(() => new Promise((resolve) => (release = resolve))) as ApiClient["answer"],
    });
    render(<Play client={api} level="senior" mode="daily" relaxed={false} onFinished={vi.fn()} />);
    await user.click(await screen.findByRole("radio", { name: /Right one/ }));
    const check = screen.getByRole("button", { name: "Check" });
    await user.dblClick(check);
    expect(api.answer).toHaveBeenCalledTimes(1);
    release({ result: NO_LINES, conflict: false });
    expect(await screen.findByRole("button", { name: "Next question" })).toBeInTheDocument();
  });

  it("shows the right answer after a wrong one", async () => {
    const user = userEvent.setup();
    const api = client({
      startPlay: vi.fn().mockResolvedValue({ created: true, play: state({ question: view(1, "better") }) }),
      answer: vi.fn().mockResolvedValue({ result: { ...NO_LINES, grade: 0, bonus: 0 }, conflict: false }),
    });
    render(<Play client={api} level="senior" mode="daily" relaxed={false} onFinished={vi.fn()} />);
    await user.click(await screen.findByRole("radio", { name: /Wrong one/ }));
    await user.click(screen.getByRole("button", { name: "Check" }));
    const feedback = await screen.findByRole("status");
    expect(feedback).toHaveTextContent("Not this time");
    expect(feedback).toHaveTextContent("Right answer: Right one");
  });

  it("keeps the answer for a retry after a network failure", async () => {
    const user = userEvent.setup();
    const answer = vi
      .fn()
      .mockRejectedValueOnce(new ApiError("network", "Could not reach the server."))
      .mockResolvedValue({ result: NO_LINES, conflict: false });
    const api = client({
      startPlay: vi.fn().mockResolvedValue({ created: true, play: state({ question: view(1, "better") }) }),
      answer,
    });
    render(<Play client={api} level="senior" mode="daily" relaxed={false} onFinished={vi.fn()} />);
    await user.click(await screen.findByRole("radio", { name: /Right one/ }));
    await user.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be sent");
    await user.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Right");
    expect(answer).toHaveBeenCalledTimes(2);
  });

  it("switches to relaxed after a confirmation and hides the timer", async () => {
    const user = userEvent.setup();
    const api = client();
    render(<Play client={api} level="senior" mode="daily" relaxed={false} onFinished={vi.fn()} />);
    expect(await screen.findByText(/within 45 seconds/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Switch to relaxed mode" }));
    await user.click(screen.getByRole("button", { name: "Switch to relaxed" }));
    expect(api.relax).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/within 45 seconds/)).not.toBeInTheDocument();
    expect(screen.getByText("Relaxed · no timer")).toBeInTheDocument();
  });

  it("goes to the result when the play is already finished", async () => {
    const onFinished = vi.fn();
    const done = state({ finished: true });
    delete done.question;
    render(
      <Play
        client={client({ startPlay: vi.fn().mockResolvedValue({ created: false, play: done }) })}
        level="senior"
        mode="daily"
        relaxed={false}
        onFinished={onFinished}
      />,
    );
    await vi.waitFor(() => expect(onFinished).toHaveBeenCalledWith(done));
  });

  it("explains why a replay is refused", async () => {
    const refused = new ApiError("http", "x", { status: 409, code: "conflict" });
    render(
      <Play
        client={client({ startPlay: vi.fn().mockRejectedValue(refused) })}
        level="senior"
        mode="replay"
        relaxed={false}
        onFinished={vi.fn()}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Finish today's set before replaying it.");
  });
});
