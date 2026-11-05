// Time used against the target (task T066). The server measures time for scoring (FR-005a);
// this is only a display, started from the server's servedAt. Hidden in relaxed mode. The
// ticking digits are hidden from screen readers; they hear the target once instead.

import { useEffect, useState } from "react";

export interface TimerProps {
  servedAt: string;
  targetSeconds: number;
  /** Stops the clock once the answer is in. */
  stopped?: boolean;
}

export function formatSeconds(total: number): string {
  const s = Math.max(0, Math.floor(total));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Seconds since servedAt by the browser clock, never negative (clocks can disagree). */
function elapsedSince(servedAt: string, receivedAt: number): number {
  const served = Date.parse(servedAt);
  const now = Date.now();
  // A browser clock behind the server would show a negative time: count from receipt instead.
  const start = Number.isNaN(served) || served > receivedAt ? receivedAt : served;
  return (now - start) / 1000;
}

export function Timer({ servedAt, targetSeconds, stopped = false }: TimerProps) {
  const [receivedAt] = useState(() => Date.now());
  const [seconds, setSeconds] = useState(() => elapsedSince(servedAt, receivedAt));

  useEffect(() => {
    if (stopped) return;
    const tick = () => setSeconds(elapsedSince(servedAt, receivedAt));
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [servedAt, receivedAt, stopped]);

  const over = seconds > targetSeconds;
  return (
    <p className={`timer${over ? " over" : ""}`}>
      <span className="sr-only">Speed bonus if right within {targetSeconds} seconds.</span>
      <span aria-hidden="true">
        {formatSeconds(seconds)} / {formatSeconds(targetSeconds)}
        {over ? " · no bonus" : ""}
      </span>
    </p>
  );
}
