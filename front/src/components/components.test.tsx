import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Choices } from "./Choices";
import { CodeBlock, lines } from "./CodeBlock";
import { Squares } from "./Squares";
import { formatSeconds, Timer } from "./Timer";

const CODE = "a = 1\nb = 2\nc = a / 0\nprint(c)\n";

function Picker() {
  const [line, setLine] = useState<number | null>(null);
  return (
    <>
      <CodeBlock code={CODE} picked={line} onPick={setLine} />
      <output>{line ?? "none"}</output>
    </>
  );
}

describe("CodeBlock", () => {
  it("drops the final newline", () => {
    expect(lines(CODE)).toHaveLength(4);
  });

  it("picks a line with the arrow keys and Enter", async () => {
    const user = userEvent.setup();
    render(<Picker />);
    const box = screen.getByRole("listbox");
    box.focus();
    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(screen.getByRole("status")).toHaveTextContent("3");
    expect(screen.getByRole("option", { name: /Line 3/ })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{End}{ArrowDown} ");
    expect(screen.getByRole("status")).toHaveTextContent("4");
  });

  it("picks a line with a click", async () => {
    const user = userEvent.setup();
    render(<Picker />);
    await user.click(screen.getByRole("option", { name: /Line 2/ }));
    expect(screen.getByRole("status")).toHaveTextContent("2");
  });

  it("marks the right line after the answer", () => {
    render(<CodeBlock code={CODE} picked={2} correctLines={[3]} />);
    expect(screen.getByRole("region")).toBeInTheDocument();
  });
});

describe("Choices", () => {
  const choices = [
    { id: "AAAAAAAA", text: "One" },
    { id: "BBBBBBBB", text: "Two" },
    { id: "CCCCCCCC", text: "Three" },
    { id: "DDDDDDDD", text: "Four" },
  ];

  it("is a radio group", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Choices name="q" legend="Your answer" choices={choices} value={null} onChange={onChange} />);
    await user.click(screen.getByRole("radio", { name: /Two/ }));
    expect(onChange).toHaveBeenCalledWith("BBBBBBBB");
  });

  it("is disabled while submitting", () => {
    render(<Choices name="q" legend="Your answer" choices={choices} value={null} onChange={vi.fn()} disabled />);
    for (const radio of screen.getAllByRole("radio")) expect(radio).toBeDisabled();
  });

  it("names the right answer and the wrong pick in text", () => {
    render(
      <Choices name="q" legend="x" choices={choices} value="AAAAAAAA" onChange={vi.fn()} correctId="CCCCCCCC" disabled />,
    );
    expect(screen.getByText("Right answer")).toBeInTheDocument();
    expect(screen.getByText("Your answer")).toBeInTheDocument();
  });
});

describe("Squares", () => {
  it("says each result in words, not only colour", () => {
    render(<Squares grades={[1, 0.5, 0, null]} decks={["Spot the bug"]} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
    expect(items[0]).toHaveTextContent("Question 1 (Spot the bug): right");
    expect(items[1]).toHaveTextContent("half right");
    expect(items[2]).toHaveTextContent("wrong");
    expect(items[3]).toHaveTextContent("not answered");
  });
});

describe("Timer", () => {
  it("formats minutes and seconds", () => {
    expect(formatSeconds(0)).toBe("0:00");
    expect(formatSeconds(65.9)).toBe("1:05");
    expect(formatSeconds(-3)).toBe("0:00");
  });

  it("states the target once for screen readers and hides the ticking digits", () => {
    render(<Timer servedAt={new Date().toISOString()} targetSeconds={45} />);
    expect(screen.getByText(/within 45 seconds/)).toBeInTheDocument();
    expect(screen.getByText(/0:45/).closest("[aria-hidden]")).toHaveAttribute("aria-hidden", "true");
  });

  it("never shows a negative time when the browser clock is behind", () => {
    const future = new Date(Date.now() + 60_000).toISOString();
    render(<Timer servedAt={future} targetSeconds={45} />);
    expect(screen.getByText(/0:00 \/ 0:45/)).toBeInTheDocument();
  });
});
