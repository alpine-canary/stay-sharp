// "Challenge a colleague" on the result of a finished daily (task T107, Story 4, FR-018). The
// link names a random challenge id only, never the player.

import { useRef, useState } from "react";
import type { ApiClient } from "../api/client";
import { Link } from "./Link";
import { copyOrSelect, MANUAL_COPY, type CopyStatus } from "./ShareCard";

export interface ChallengeLinkProps {
  client: ApiClient;
  playId: string;
}

type State = { status: "idle" } | { status: "busy" } | { status: "ready"; url: string } | { status: "failed" };

export function ChallengeLink({ client, playId }: ChallengeLinkProps) {
  const [state, setState] = useState<State>({ status: "idle" });
  const [copy, setCopy] = useState<CopyStatus>(null);
  const box = useRef<HTMLElement>(null);

  async function create() {
    setState({ status: "busy" });
    try {
      const created = await client.createChallenge(playId);
      setState({ status: "ready", url: `${window.location.origin}${created.path}` });
    } catch {
      setState({ status: "failed" });
    }
  }

  return (
    <section className="share" aria-labelledby="challenge-title">
      <h2 id="challenge-title" className="eyebrow">
        Challenge a colleague
      </h2>
      {state.status !== "ready" ? (
        <>
          <p className="hint">
            They play the same five questions, then you both see both results. The link shows your score, never
            your name.
          </p>
          <div className="row">
            <button type="button" className="btn ghost" disabled={state.status === "busy"} onClick={() => void create()}>
              {state.status === "busy" ? "Creating the link..." : "Create a challenge link"}
            </button>
          </div>
          {state.status === "failed" && (
            <p role="alert" className="hint">
              The link could not be created. Please try again.
            </p>
          )}
        </>
      ) : (
        <>
          <code ref={box} className="share-text link-text">
            {state.url}
          </code>
          <div className="row">
            <button
              type="button"
              className="btn"
              onClick={() => {
                void copyOrSelect(state.url, box.current).then(setCopy);
              }}
            >
              Copy link
            </button>
            <Link className="btn ghost" href={new URL(state.url).pathname}>
              Open it
            </Link>
          </div>
          <p role="status" className="hint">
            {copy === "copied" && "Link copied. Send it to a colleague."}
            {copy === "manual" && MANUAL_COPY}
          </p>
        </>
      )}
    </section>
  );
}
