// What we keep and where (task T113, FR-035, FR-036; accounts: T235, FR-114 to FR-117).
// Written so a 12-year-old can follow it. Every fact here matches the code: browser storage
// (src/storage.ts), the table and its expiry times (infra/stacks/data_stack.py, store/*.py),
// logs without IP addresses (api_stack.py), accounts (infra/stacks/auth_stack.py,
// store/accounts.py, store/deletion.py, store/inactive.py for the 24-month rule and the
// unconfirmed sign-ups).

import { Link } from "../components/Link";

export function Privacy() {
  return (
    <section className="card prose" aria-labelledby="privacy-title">
      <span className="eyebrow">Privacy</span>
      <h1 id="privacy-title" className="text-2xl">
        What we keep, and where
      </h1>
      <p>
        You do not need an account to play. Without one, we never ask for your name, your e-mail or your age.
        There are no ads, no cookies and no trackers.
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
          challenges: about 30 days. A challenge shows results only, never who played. Your colleague never sees
          your random code.
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

      <h2 className="text-lg">If you create an account</h2>
      <p>
        An account is optional and only for players aged 16 and over. It keeps your streak and progress on all
        your devices. With an account, we also keep:
      </p>
      <ul>
        <li>your e-mail address, used only to send you sign-in codes (no newsletter);</li>
        <li>that you said you are 16 or older;</li>
        <li>
          your passkeys, if you add any: only the public part. Your face, your fingerprint and your screen lock
          never leave your device;
        </li>
        <li>a copy of your progress, and the games from all your devices, under one random code.</li>
      </ul>
      <p>
        All of it stays in Zurich, Switzerland. Our logs never keep your e-mail address or your sign-in codes.
      </p>
      <p>
        If you do not use your account for 23 months, we send you one e-mail. A month later, unless you have
        signed in, we delete the account and everything kept with it. If you ask for a code to create an
        account but never type it, we delete your e-mail address after 7 days.
      </p>
      <p>
        <strong>Delete my account</strong>, on your account page, deletes all of it within a minute: your
        account, your e-mail, your games and your progress. Challenge results you left for a colleague stay as
        scores without a name. Backups keep a copy for up to 35 days, then it is gone.
      </p>

      <div className="row">
        <Link href="/" className="btn ghost">
          Back to today
        </Link>
      </div>
    </section>
  );
}
