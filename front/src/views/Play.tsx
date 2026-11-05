// Play today's set (task T068): open, answer, feedback, next. Resume at the first unanswered
// question (the server returns it). A failed submission can be retried safely: the server counts
// the same answer once. Relaxed can be switched on before or during a play, never off.

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import {
  ApiError,
  type AnswerResult,
  type ApiClient,
  type Level,
  type PlayState,
  type QuestionView,
} from "../api/client";
import { Choices } from "../components/Choices";
import { CodeBlock } from "../components/CodeBlock";
import { Feedback } from "../components/Feedback";
import { Link } from "../components/Link";
import { Squares } from "../components/Squares";
import { Timer } from "../components/Timer";
import { DECK_ORDER, LINE_DECKS, deckName } from "../decks";

export interface PlayProps {
  client: ApiClient;
  level: Level;
  mode: "daily" | "replay";
  relaxed: boolean;
  /** Set for a play started from a challenge link: its date and id (Story 4). */
  challenge?: { id: string; date: string } | undefined;
  onFinished: (play: PlayState) => void;
  /** Every graded answer, for the skill view. ``duplicate`` is true when the server had already
   * counted an answer for this question (a retry, or a 409 with the answer that counts). */
  onAnswered?: (answer: { mode: "daily" | "replay"; deck: string; grade: number; duplicate: boolean }) => void;
}

type Loading = { status: "loading" } | { status: "ready" } | { status: "blocked"; message: string; retry: boolean };

function messageOf(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.serviceDown ? fallback : error.message;
  return fallback;
}

export function Play({ client, level, mode, relaxed: relaxedPref, challenge, onFinished, onAnswered }: PlayProps) {
  const [loading, setLoading] = useState<Loading>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [play, setPlay] = useState<PlayState | null>(null);
  const [question, setQuestion] = useState<QuestionView | null>(null);
  const [choice, setChoice] = useState<string | null>(null);
  const [line, setLine] = useState<number | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmRelax, setConfirmRelax] = useState(false);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const formId = useId();

  useEffect(() => {
    let current = true;
    client
      .startPlay({
        level,
        mode,
        relaxed: relaxedPref,
        ...(challenge ? { challengeId: challenge.id, date: challenge.date } : {}),
      })
      .then(({ play: state }) => {
        if (!current) return;
        if (state.finished) {
          onFinished(state);
          return;
        }
        if (!state.question) {
          setLoading({ status: "blocked", message: "This set can no longer be played.", retry: false });
          return;
        }
        setPlay(state);
        setQuestion(state.question);
        setLoading({ status: "ready" });
      })
      .catch((err: unknown) => {
        if (!current) return;
        const notReady = err instanceof ApiError && err.code === "not_ready";
        const message =
          err instanceof ApiError && err.code === "conflict"
            ? challenge
              ? "Finish your own play of that day first, then come back to this link."
              : "Finish today's set before replaying it."
            : messageOf(err, "The game is not reachable right now.");
        setLoading({ status: "blocked", message, retry: !notReady && !(err instanceof ApiError && !err.serviceDown) });
      });
    return () => {
      current = false;
    };
    // relaxedPref is only read when the play is created; a change later does not restart it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, level, mode, challenge?.id, attempt]);

  // Move focus to the new question so keyboard and screen-reader users start from its title.
  useEffect(() => {
    if (question) titleRef.current?.focus();
  }, [question]);

  useEffect(() => {
    if (result) feedbackRef.current?.focus();
  }, [result]);

  if (loading.status === "loading") return <p aria-live="polite">Loading the set...</p>;
  if (loading.status === "blocked" || !play || !question) {
    const message = loading.status === "blocked" ? loading.message : "Something went wrong.";
    return (
      <section className="card" role="alert">
        <p>{message}</p>
        <div className="row">
          {loading.status === "blocked" && loading.retry && (
            <button
              type="button"
              className="btn"
              onClick={() => {
                setLoading({ status: "loading" });
                setAttempt((n) => n + 1);
              }}
            >
              Try again
            </button>
          )}
          <Link href="/" className="btn ghost">
            Back to today
          </Link>
        </div>
      </section>
    );
  }

  const needsLine = LINE_DECKS.has(question.deck);
  const ready = choice !== null && (!needsLine || line !== null);
  const last = question.index === 4;
  const decks = DECK_ORDER[play.level].map(deckName);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!ready || busy || result || choice === null) return;
    setBusy(true);
    setError(null);
    try {
      const answer = await client.answer(play.playId, question.index, {
        choiceId: choice,
        ...(needsLine && line !== null ? { line } : {}),
      });
      setResult(answer.result);
      setConflict(answer.conflict);
      onAnswered?.({
        mode: play.mode,
        deck: question.deck,
        grade: answer.result.grade,
        duplicate: answer.result.duplicate || answer.conflict,
      });
      setPlay((p) => {
        if (!p) return p;
        const grades = [...p.grades];
        while (grades.length < 5) grades.push(null);
        grades[question.index] = answer.result.grade;
        return { ...p, grades };
      });
    } catch (err) {
      setError(messageOf(err, "Your answer could not be sent. Check your connection and try again."));
    } finally {
      setBusy(false);
    }
  };

  const next = async () => {
    setBusy(true);
    setError(null);
    try {
      if (last) {
        onFinished(await client.getPlay(play.playId));
        return;
      }
      const view = await client.open(play.playId, question.index + 1);
      setQuestion(view);
      setChoice(null);
      setLine(null);
      setResult(null);
      setConflict(false);
      window.scrollTo(0, 0);
    } catch (err) {
      setError(messageOf(err, "The next question could not be loaded. Try again."));
    } finally {
      setBusy(false);
    }
  };

  const relax = async () => {
    setBusy(true);
    setError(null);
    try {
      setPlay(await client.relax(play.playId));
      setConfirmRelax(false);
    } catch (err) {
      setError(messageOf(err, "Relaxed mode could not be switched on. Try again."));
    } finally {
      setBusy(false);
    }
  };

  const label = `${mode === "replay" ? "Replay" : "Daily"} #${play.gameNumber}`;

  return (
    <>
      <div className="qhead">
        <Squares grades={play.grades} decks={decks} current={question.index} label="Progress" />
        <span className="hint">
          {label} · {question.index + 1}/5{mode === "replay" ? " · not scored" : ""}
        </span>
      </div>

      <section className="card" aria-labelledby={`${formId}-title`}>
        <div className="qhead">
          <span className="eyebrow">
            {deckName(question.deck)}
            {question.language && question.language !== "text" ? ` · ${question.language}` : ""}
          </span>
          {!play.relaxed && question.targetSeconds !== undefined && (
            <Timer
              key={`${question.index}-${question.servedAt}`}
              servedAt={question.servedAt}
              targetSeconds={question.targetSeconds}
              stopped={result !== null}
            />
          )}
          {play.relaxed && <span className="hint">Relaxed · no timer</span>}
        </div>

        <h1 id={`${formId}-title`} className="qtitle" tabIndex={-1} ref={titleRef}>
          {question.prompt}
        </h1>

        <form id={formId} onSubmit={submit} className="grid gap-4" noValidate>
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
            name={`q${question.index}`}
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
            <button type="button" className="btn" onClick={next} disabled={busy}>
              {last ? "See my result" : "Next question"}
            </button>
          </div>
        )}
      </section>

      {!play.relaxed && (
        <section className="notice" aria-label="Relaxed mode">
          {!confirmRelax ? (
            <p className="hint">
              Need more time?{" "}
              <button type="button" className="link-btn" onClick={() => setConfirmRelax(true)}>
                Switch to relaxed mode
              </button>
            </p>
          ) : (
            <>
              <p>No timer and no speed bonus for the rest of this set. You cannot switch it back for this set.</p>
              <div className="row">
                <button type="button" className="btn" onClick={relax} disabled={busy}>
                  Switch to relaxed
                </button>
                <button type="button" className="btn ghost" onClick={() => setConfirmRelax(false)}>
                  Keep the timer
                </button>
              </div>
            </>
          )}
        </section>
      )}
    </>
  );
}
