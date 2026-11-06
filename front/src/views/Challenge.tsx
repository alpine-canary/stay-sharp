// A challenge link, /c/<id> (task T107, Story 4, FR-018 to FR-020).
// - owner: their own result, the colleagues who finished, and the link to share again;
// - colleague before finishing: "A colleague scored <score>/5" only, and a button to play;
// - colleague after: both results side by side (squares, score, time);
// - unknown, malformed or expired: a plain message and a way to play today's daily.

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, type ApiClient, type ChallengeView, type PlayState, type ResultSnapshot } from "../api/client";
import { Link } from "../components/Link";
import { copyOrSelect, MANUAL_COPY, type CopyStatus } from "../components/ShareCard";
import { Squares } from "../components/Squares";
import { formatSeconds } from "../components/Timer";
import { DECK_ORDER, LEVEL_NAMES, deckName } from "../decks";
import { formatScore } from "./Result";
import { Play, type PlayProps } from "./Play";

export interface ChallengeProps {
  client: ApiClient;
  challengeId: string;
  relaxed: boolean;
  /** A finished play started here; a daily one counts for the streak like any daily. */
  onFinished: (play: PlayState) => void;
  onAnswered?: PlayProps["onAnswered"];
}

type State =
  | { status: "loading" }
  | { status: "ready"; challenge: ChallengeView; today: string }
  | { status: "gone"; expired: boolean }
  | { status: "failed" };

const LEVEL = LEVEL_NAMES;

export function Challenge({ client, challengeId, relaxed, onFinished, onAnswered }: ChallengeProps) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [playing, setPlaying] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    Promise.all([client.getChallenge(challengeId), client.today()])
      .then(([challenge, today]) => {
        if (current) setState({ status: "ready", challenge, today: today.date });
      })
      .catch((err: unknown) => {
        if (!current) return;
        if (err instanceof ApiError && err.status === 404) setState({ status: "gone", expired: err.code === "expired" });
        else setState({ status: "failed" });
      });
    return () => {
      current = false;
    };
  }, [client, challengeId, attempt]);

  const finished = useCallback(
    (play: PlayState) => {
      onFinished(play);
      setPlaying(false);
      setState({ status: "loading" });
      setAttempt((n) => n + 1);
      window.scrollTo(0, 0);
    },
    [onFinished],
  );

  if (state.status === "loading") return <p aria-live="polite">Loading the challenge...</p>;
  if (state.status === "gone") {
    return (
      <section className="card" role="alert" aria-labelledby="gone-title">
        <h1 id="gone-title" className="text-2xl">
          {state.expired ? "This challenge has ended" : "This challenge link does not work"}
        </h1>
        <p>
          {state.expired
            ? "Challenge links last 30 days. Today's set is waiting for you."
            : "Check that the whole link was copied. Today's set is waiting for you."}
        </p>
        <div className="row">
          <Link href="/" className="btn">
            Play today's daily
          </Link>
        </div>
      </section>
    );
  }
  if (state.status === "failed") {
    return (
      <section className="card" role="alert">
        <p>The game is not reachable right now.</p>
        <div className="row">
          <button
            type="button"
            className="btn"
            onClick={() => {
              setState({ status: "loading" });
              setAttempt((n) => n + 1);
            }}
          >
            Try again
          </button>
          <Link href="/" className="btn ghost">
            Back to today
          </Link>
        </div>
      </section>
    );
  }

  const { challenge, today } = state;
  const past = challenge.date < today;
  const decks = DECK_ORDER[challenge.level].map(deckName);
  const eyebrow = `Challenge · ${past ? "Past set" : "Daily"} #${challenge.gameNumber} · ${challenge.date} · ${LEVEL[challenge.level]}`;

  if (playing) {
    return (
      <Play
        client={client}
        level={challenge.level}
        mode={past ? "replay" : "daily"}
        relaxed={relaxed}
        challenge={{ id: challenge.challengeId, date: challenge.date }}
        onFinished={finished}
        {...(onAnswered ? { onAnswered } : {})}
      />
    );
  }

  if (challenge.viewer === "colleague_before") {
    return (
      <section className="card" aria-labelledby="challenge-title">
        <span className="eyebrow">{eyebrow}</span>
        <h1 id="challenge-title" className="text-2xl">
          A colleague scored {formatScore(challenge.ownerScore)}/5
        </h1>
        <p>Play the same five questions. When you finish, you see both results side by side.</p>
        {past && <p className="hint">This set is from {challenge.date}. It does not count for your streak.</p>}
        <div className="row">
          <button type="button" className="btn" onClick={() => setPlaying(true)}>
            Play this set
          </button>
          <Link href="/" className="btn ghost">
            Play today's daily instead
          </Link>
        </div>
      </section>
    );
  }

  if (challenge.viewer === "owner") {
    const colleagues = challenge.colleagues ?? [];
    return (
      <section className="card" aria-labelledby="challenge-title">
        <span className="eyebrow">{eyebrow}</span>
        <h1 id="challenge-title" className="text-2xl">
          Your challenge
        </h1>
        <p>
          {colleagues.length === 0
            ? "Nobody has finished it yet. Send the link to a colleague."
            : `${colleagues.length} ${colleagues.length === 1 ? "colleague has" : "colleagues have"} finished it.`}
        </p>
        <CopyLink url={`${window.location.origin}/c/${challenge.challengeId}`} />
        <div className="versus">
          {challenge.owner && <Side title="You" snapshot={challenge.owner} decks={decks} />}
          {colleagues.map((snapshot, i) => (
            <Side key={i} title={`Colleague ${i + 1}`} snapshot={snapshot} decks={decks} />
          ))}
        </div>
        <div className="row">
          <Link href="/" className="btn ghost">
            Back to today
          </Link>
        </div>
      </section>
    );
  }

  const others = challenge.others - 1;
  return (
    <section className="card" aria-labelledby="challenge-title">
      <span className="eyebrow">{eyebrow}</span>
      <h1 id="challenge-title" className="text-2xl">
        {verdict(challenge.you, challenge.owner)}
      </h1>
      <div className="versus">
        {challenge.you && <Side title="You" snapshot={challenge.you} decks={decks} />}
        {challenge.owner && <Side title="Your colleague" snapshot={challenge.owner} decks={decks} />}
      </div>
      {others > 0 && (
        <p className="hint">
          {others} other {others === 1 ? "colleague" : "colleagues"} also took this challenge.
        </p>
      )}
      <div className="row">
        <Link href="/" className="btn">
          {past ? "Play today's daily" : "Back to today"}
        </Link>
      </div>
    </section>
  );
}

function verdict(you: ResultSnapshot | undefined, owner: ResultSnapshot | undefined): string {
  if (!you || !owner) return "Both results";
  const mine = you.score + (you.relaxed ? 0 : you.bonus);
  const theirs = owner.score + (owner.relaxed ? 0 : owner.bonus);
  if (mine > theirs) return "You came out ahead";
  if (mine < theirs) return "Your colleague came out ahead";
  return "A draw";
}

function Side({ title, snapshot, decks }: { title: string; snapshot: ResultSnapshot; decks: string[] }) {
  return (
    <div className="side">
      <h2 className="eyebrow">{title}</h2>
      <Squares grades={snapshot.grades} decks={decks} label={`${title}: answers, question by question`} />
      <dl className="side-figures">
        <div>
          <dt>Score</dt>
          <dd>{formatScore(snapshot.score)}/5</dd>
        </div>
        <div>
          <dt>{snapshot.relaxed ? "Relaxed" : "Speed"}</dt>
          <dd>{snapshot.relaxed ? "no bonus" : `+${formatScore(snapshot.bonus)}`}</dd>
        </div>
        <div>
          <dt>Time</dt>
          <dd>{formatSeconds(snapshot.elapsedMs / 1000)}</dd>
        </div>
      </dl>
    </div>
  );
}

function CopyLink({ url }: { url: string }) {
  const box = useRef<HTMLElement>(null);
  const [status, setStatus] = useState<CopyStatus>(null);
  return (
    <div className="share">
      <code ref={box} className="share-text link-text">
        {url}
      </code>
      <div className="row">
        <button type="button" className="btn" onClick={() => void copyOrSelect(url, box.current).then(setStatus)}>
          Copy link
        </button>
      </div>
      <p role="status" className="hint">
        {status === "copied" && "Link copied. Send it to a colleague."}
        {status === "manual" && MANUAL_COPY}
      </p>
    </div>
  );
}
