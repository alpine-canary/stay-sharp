// What we keep and where (task T113, FR-035, FR-036). Written so a 12-year-old can follow it.
// Every fact here matches the code: browser storage (src/storage.ts), the table and its expiry
// times (infra/stacks/data_stack.py, store/*.py), logs without IP addresses (api_stack.py).

import { Link } from "../components/Link";

export function Privacy() {
  return (
    <section className="card prose" aria-labelledby="privacy-title">
      <span className="eyebrow">Privacy</span>
      <h1 id="privacy-title" className="text-2xl">
        What we keep, and where
      </h1>
      <p>
        You do not need an account. We never ask for your name, your e-mail or your age. There are no ads, no
        cookies and no trackers.
      </p>

      <h2 className="text-lg">In your browser</h2>
      <p>
        Your browser keeps your progress: your level, the days you played, your scores, your streak and which
        questions to practise again. It also keeps a random code made for this browser, so the game knows your
        answers are yours. The code says nothing about who you are.
      </p>
      <p>
        If you clear this site's data, use a private window, or play on another browser or device, your progress
        starts from zero. We cannot bring it back, because we never had it.
      </p>

      <h2 className="text-lg">On our server, in Switzerland</h2>
      <p>
        Our server is in Zurich, Switzerland. To count each answer only once, it keeps your answers and scores
        under that random code:
      </p>
      <ul>
        <li>daily games: about 90 days, then deleted;</li>
        <li>practice questions: about 14 days;</li>
        <li>
          challenges: about 30 days. A challenge only shows scores. Your colleague never sees your random code.
        </li>
      </ul>
      <p>
        Deleting can take up to two more days. Backups, made in case something breaks, keep a copy for up to 35
        days.
      </p>
      <p>
        Our logs keep technical ids only, never your IP address. We count things like "how many games were
        finished today" as totals, never per person.
      </p>

      <div className="row">
        <Link href="/" className="btn ghost">
          Back to today
        </Link>
      </div>
    </section>
  );
}
