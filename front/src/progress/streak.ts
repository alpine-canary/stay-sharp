// Streak, longest streak and freeze, derived from the log of finished dailies (R7, FR-012 to
// FR-014). Pure: the same log and the same "today" always give the same figures.
//
// Dates are the server's Europe/Zurich calendar days ("YYYY-MM-DD"). They are handled as UTC
// midnights, so the device's own time zone and summer time never move a day.
//
// Rules, replayed in date order:
// - A finished daily on the day after the previous one adds 1.
// - A gap of exactly one missed day is covered by a held freeze: the day is "frozen", the freeze
//   is used, the streak goes on (a frozen day adds nothing). Any other gap restarts at 1, and a
//   held freeze is kept for later.
// - The 5th finished daily of a Monday-to-Sunday week earns a freeze, unless one is already held
//   or one was used for a day of that week. At most one is held.
// - Today not played yet: the streak is still alive if the last play was yesterday, or the day
//   before with a freeze to cover yesterday (that day then shows frozen). Otherwise it shows 0.

export interface StreakView {
  current: number;
  longest: number;
  held: boolean;
  frozen: string[];
  playedToday: boolean;
}

const DAY_MS = 86_400_000;

function dayNumber(date: string): number {
  return Math.round(Date.parse(`${date}T00:00:00Z`) / DAY_MS);
}

function dateOf(day: number): string {
  return new Date(day * DAY_MS).toISOString().slice(0, 10);
}

/** Monday of the ISO week that holds ``date``. */
export function weekOf(date: string): string {
  const day = dayNumber(date);
  const weekday = (new Date(day * DAY_MS).getUTCDay() + 6) % 7; // Monday 0 ... Sunday 6
  return dateOf(day - weekday);
}

export function streak(played: Iterable<string>, today: string): StreakView {
  const todayN = dayNumber(today);
  const days = [...new Set(played)].map(dayNumber).filter((d) => d <= todayN).sort((a, b) => a - b);

  let current = 0;
  let longest = 0;
  let held = false;
  let previous: number | null = null;
  const frozen: string[] = [];
  const usedInWeek = new Set<string>();
  const playsInWeek = new Map<string, number>();

  for (const day of days) {
    const gap = previous === null ? Infinity : day - previous - 1;
    if (gap === 0) {
      current += 1;
    } else if (gap === 1 && held) {
      const missed = dateOf(day - 1);
      frozen.push(missed);
      usedInWeek.add(weekOf(missed));
      held = false;
      current += 1;
    } else {
      current = 1;
    }
    longest = Math.max(longest, current);

    const week = weekOf(dateOf(day));
    const count = (playsInWeek.get(week) ?? 0) + 1;
    playsInWeek.set(week, count);
    if (count === 5 && !held && !usedInWeek.has(week)) held = true;
    previous = day;
  }

  const playedToday = previous === todayN;
  if (!playedToday && previous !== null) {
    const missed = todayN - previous - 1;
    if (missed === 1 && held) {
      frozen.push(dateOf(todayN - 1));
      held = false;
    } else if (missed >= 1) {
      current = 0;
    }
  }
  return { current, longest, held, frozen, playedToday };
}
