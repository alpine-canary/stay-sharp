// Streak, longest streak, freeze and skill view for one level (task T098, Story 2, FR-012 to
// FR-016). Every figure comes from the pure functions in ../progress; this file only shows them.

import { DECK_ORDER, deckName } from "../decks";
import { skills } from "../progress/skills";
import { streak, weekOf } from "../progress/streak";
import type { Level, Progress } from "../storage";

export interface ProgressCardProps {
  progress: Progress;
  level: Level;
  /** Today in Europe/Zurich, from the server when it answered, else from this device. */
  today: string;
}

function days(n: number): string {
  return n === 1 ? "day" : "days";
}

function count(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function ProgressCard({ progress, level, today }: ProgressCardProps) {
  const played = Object.keys(progress.days[level]);
  const view = streak(played, today);
  const week = weekOf(today);
  const thisWeek = played.filter((d) => weekOf(d) === week && d <= today).length;
  const usedThisWeek = view.frozen.some((d) => weekOf(d) === week);
  const yesterdayFrozen = !view.playedToday && view.frozen.length > 0 && view.frozen.at(-1) === previousDay(today);
  const rows = skills(progress.deckStats[level], DECK_ORDER[level]);
  const anyAnswered = rows.some((r) => r.answered > 0);

  let streakNote: string;
  if (played.length === 0) streakNote = "Finish today's set to start a streak.";
  else if (view.current === 0) streakNote = "Finish today's set to start a new streak.";
  else if (!view.playedToday) streakNote = "Finish today's set to keep it going.";
  else streakNote = "Done for today. Come back tomorrow.";

  let freezeNote: string;
  if (yesterdayFrozen) freezeNote = "You missed yesterday. Your freeze covered it, so your streak goes on.";
  else if (view.held) freezeNote = "Ready. It covers one missed day by itself.";
  else if (usedThisWeek) freezeNote = "Used this week. You can earn a new one next week.";
  else freezeNote = `${Math.min(thisWeek, 5)} of 5 dailies this week. Finish 5 to earn one.`;

  return (
    <aside className="island" aria-labelledby="progress-title">
      <h2 id="progress-title" className="text-2xl">
        Your progress
      </h2>

      <dl className="stats">
        <div>
          <dt>Streak</dt>
          <dd>
            <span className="big">{view.current}</span> {days(view.current)}
          </dd>
        </div>
        <div>
          <dt>Longest</dt>
          <dd>
            <span className="big">{view.longest}</span> {days(view.longest)}
          </dd>
        </div>
        <div>
          <dt>Freeze</dt>
          <dd>
            <span className="big">{view.held ? 1 : 0}</span> held
          </dd>
        </div>
      </dl>
      <p className="hint">{streakNote}</p>
      <p className="hint">
        <strong>Freeze:</strong> {freezeNote}
      </p>

      <h3 className="eyebrow">Skills, weakest first</h3>
      {anyAnswered ? (
        <ol className="skills">
          {rows.map((row) => (
            <li key={row.deck}>
              <span className="name">{deckName(row.deck)}</span>
              {row.share === null ? (
                <span className="figure muted">Not played yet</span>
              ) : (
                <>
                  <span className="figure">
                    {count(row.correct)} of {row.answered} right
                  </span>
                  <span className="bar" aria-hidden="true">
                    <i style={{ width: `${Math.round(row.share * 100)}%` }} />
                  </span>
                </>
              )}
            </li>
          ))}
        </ol>
      ) : (
        <p className="hint">Answer a few questions to see which decks need practice.</p>
      )}

      <p className="hint">
        Your progress is kept in this browser only. Another browser or device, a private window, or
        clearing this site's data starts from zero.
      </p>
    </aside>
  );
}

function previousDay(date: string): string {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - 1);
  return day.toISOString().slice(0, 10);
}

/** Today in Europe/Zurich from this device's clock, used until the server answers. */
export function zurichToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Zurich" }).format(now);
}
