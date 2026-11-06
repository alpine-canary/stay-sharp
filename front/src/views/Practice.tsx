// Practice (task T112, Story 5, FR-021 to FR-023): past questions by deck or all decks, graded and
// explained like the daily. Missed questions come back sooner (progress/boxes.ts). Practice never
// touches the streak, the freeze or the daily result: it only updates the practice boxes.

import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ApiError, type AnswerResult, type ApiClient, type PracticeNext } from "../api/client";
import { Choices } from "../components/Choices";
import { CodeBlock } from "../components/CodeBlock";
import { Feedback } from "../components/Feedback";
import { Link } from "../components/Link";
import { DECK_ORDER, LINE_DECKS, deckName, LEVEL_NAMES } from "../decks";
import { preferred, type PracticeAnswer, type PracticeState } from "../progress/boxes";
import type { Level } from "../storage";

export interface PracticeProps {
  client: ApiClient;
  level: Level;
  practice: PracticeState;
  onAnswered: (answer: PracticeAnswer) => void;
}

type Loading = { status: "loading" } | { status: "ready" } | { status: "blocked"; message: string; retry: boolean };

const ALL = "all";

export function Practice({ client, level, practice, onAnswered }: PracticeProps) {
  const [deck, setDeck] = useState<string>(ALL);
  const [loading, setLoading] = useState<Loading>({ status: "loading" });
  const [current, setCurrent] = useState<PracticeNext | null>(null);
  const [choice, setChoice] = useState<string | null>(null);
  const [line, setLine] = useState<number | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const formId = useId();
  const [request, setRequest] = useState(0);
  // Read when a question is asked for only: answering must not fetch a new question by itself.
  const practiceRef = useRef(practice);
  useEffect(() => {
    practiceRef.current = practice;
  }, [practice]);

  useEffect(() => {
    let live = true;
    const filter = deck === ALL ? {} : { deck };
    client
      .practiceNext({ level, ...filter, prefer: preferred(practiceRef.current, filter) })
      .then((next) => {
        if (!live) return;
        setCurrent(next);
        setChoice(null);
        setLine(null);
        setResult(null);
        setConflict(false);
        setError(null);
        setLoading({ status: "ready" });
      })
      .catch((err: unknown) => {
        if (!live) return;
        if (err instanceof ApiError && err.code === "not_ready") {
          setLoading({ status: "blocked", message: "There are no past questions for this deck yet.", retry: false });
        } else if (err instanceof ApiError && err.code === "rate_limited") {
          setLoading({ status: "blocked", message: "That is 200 practice questions today. Come back tomorrow.", retry: false });
        } else {
          setLoading({ status: "blocked", message: "The game is not reachable right now.", retry: true });
        }
      });
    return () => {
      live = false;
    };
  }, [client, level, deck, request]);

  const ask = useCallback((nextDeck?: string) => {
    setLoading({ status: "loading" });
    if (nextDeck !== undefined) setDeck(nextDeck);
    setRequest((n) => n + 1);
  }, []);

  useEffect(() => {
    if (current) titleRef.current?.focus();
  }, [current]);

  useEffect(() => {
    if (result) feedbackRef.current?.focus();
  }, [result]);

  const question = current?.question;
  const needsLine = question ? LINE_DECKS.has(question.deck) : false;
  const ready = choice !== null && (!needsLine || line !== null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!current || !question || !ready || busy || result || choice === null) return;
    setBusy(true);
    setError(null);
    try {
      const answer = await client.practiceAnswer(current.attemptId, {
        choiceId: choice,
        ...(needsLine && line !== null ? { line } : {}),
      });
      setResult(answer.result);
      setConflict(answer.conflict);
      if (!answer.result.duplicate && !answer.conflict) setCount((n) => n + 1);
      onAnswered({
        qid: current.qid,
        deck: question.deck,
        grade: answer.result.grade,
        duplicate: answer.result.duplicate || answer.conflict,
      });
    } catch (err) {
      setError(
        err instanceof ApiError && !err.serviceDown
          ? err.message
          : "Your answer could not be sent. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <section className="card" aria-labelledby={`${formId}-intro`}>
        <span className="eyebrow">Practice · {LEVEL_NAMES[level]}</span>
        <h1 id={`${formId}-intro`} className="text-2xl">
          Practise past questions
        </h1>
        <p className="hint">
          No timer and no score to keep. Questions you miss come back sooner. Practice never changes your streak or
          today's result.
        </p>
        <fieldset className="levels">
          <legend className="eyebrow">Deck</legend>
          {[ALL, ...DECK_ORDER[level]].map((value) => (
            <label key={value} className="pill">
              <input
                type="radio"
                name="deck"
                value={value}
                checked={deck === value}
                onChange={() => ask(value)}
              />
              {value === ALL ? "All decks" : deckName(value)}
            </label>
          ))}
        </fieldset>
        {count > 0 && (
          <p className="hint" aria-live="polite">
            {count} answered in this session.
          </p>
        )}
      </section>

      {loading.status === "loading" && <p aria-live="polite">Loading a question...</p>}

      {loading.status === "blocked" && (
        <section className="card" role="alert">
          <p>{loading.message}</p>
          <div className="row">
            {loading.retry && (
              <button type="button" className="btn" onClick={() => ask()}>
                Try again
              </button>
            )}
            <Link href="/" className="btn ghost">
              Back to today
            </Link>
          </div>
        </section>
      )}

      {loading.status === "ready" && current && question && (
        <section className="card" aria-labelledby={`${formId}-title`}>
          <div className="qhead">
            <span className="eyebrow">
              {deckName(question.deck)}
              {question.language && question.language !== "text" ? ` · ${question.language}` : ""}
            </span>
            <span className="hint">Practice · no timer</span>
          </div>

          <h2 id={`${formId}-title`} className="qtitle" tabIndex={-1} ref={titleRef}>
            {question.prompt}
          </h2>

          <form onSubmit={submit} className="grid gap-4" noValidate>
            {question.code &&
              (needsLine ? (
                <CodeBlock
                  code={question.code}
                  language={question.language}
                  picked={line}
                  onPick={result ? undefined : setLine}
                  correctLines={result?.correctLines}
                  disabled={busy || result !== null}
                />
              ) : (
                <CodeBlock code={question.code} language={question.language} />
              ))}
            {needsLine && !result && (
              <p className="hint">{line === null ? "Pick a line in the code, then the problem." : `Line ${line} picked.`}</p>
            )}

            <Choices
              name={`practice-${current.attemptId}`}
              legend={needsLine ? "What is wrong with that line?" : "Your answer"}
              choices={question.choices}
              value={choice}
              onChange={setChoice}
              disabled={busy || result !== null}
              correctId={result?.correctChoiceId}
            />

            {!result && (
              <div className="row">
                <button type="submit" className="btn" disabled={!ready || busy}>
                  {busy ? "Checking..." : "Check"}
                </button>
                {needsLine && line === null && <span className="hint">Pick a line first</span>}
              </div>
            )}
          </form>

          {error && (
            <div role="alert" className="notice">
              <p>{error}</p>
            </div>
          )}

          {result && (
            <Feedback
              ref={feedbackRef}
              result={result}
              question={question}
              needsLine={needsLine}
              line={line}
              conflict={conflict}
            />
          )}

          {result && (
            <div className="row">
              <button type="button" className="btn" onClick={() => ask()} disabled={busy}>
                Next question
              </button>
              <Link href="/" className="btn ghost">
                Back to today
              </Link>
            </div>
          )}
        </section>
      )}
    </>
  );
}
