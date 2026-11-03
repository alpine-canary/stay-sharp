# Feature Specification: M1 - public daily game without accounts

**Feature Branch**: `001-m1-web-app`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "M1 of Stay Sharp: public web app without accounts. Daily set of 5
questions (one per deck: spot the bug, could do better, what if it fails, acronym or tool, AI this
week), same for everyone at a level, unlocked at 00:00 Europe/Zurich. Practice mode from the
archive with weak spots coming back sooner. Local streak with one earned freeze per week and
longest streak. Per-deck skill view. Share card without spoilers. "Challenge a colleague" link:
anonymous result id, friend plays the same set and sees both results. Explanation after each
answer. React 19 + Vite + Tailwind front end, Python Lambda API with DynamoDB, AWS CDK (Python),
CI and canary deploys. Out of M1: accounts, leaderboard, private groups, badges, Bedrock news
pipeline. Acceptance criteria must include: answers invisible in the browser before submitting;
the same answer sent twice counts once; a scoring error raises the alarm; a failing canary rolls
back by itself."

## User Scenarios & Testing *(mandatory)*

Actors:

- **Player**: anyone with a browser. No account, no sign-in.
- **Challenged player**: a player who arrives through a colleague's challenge link.
- **Maintainer**: the one person who writes and approves questions, deploys and operates the game.

### User Story 1 - Play today's daily set (Priority: P1)

A player opens the site, picks a level, and plays today's five questions: one per deck, in a fixed
order. For each question they choose an answer (for Spot the bug: first the line, then what is
wrong), submit it, and see straight away whether it was right, the right answer, and a short
explanation. After the fifth question they see their result: one square per question, the score
out of 5 and the time taken.

**Why this priority**: this is the game. Without it nothing else has a reason to exist.

**Independent Test**: open the site on a fresh browser, play the five questions of the day, and
check that each answer is graded, explained, and that the final result matches the answers given.

**Acceptance Scenarios**:

1. **Given** it is 00:00 Europe/Zurich on a new day, **When** any player opens the daily set for a
   level, **Then** they all get the same five questions for that date and level, one per deck.
2. **Given** a question is shown and not yet answered, **When** anyone inspects everything the
   browser has received so far (page source, scripts, network responses, storage, caches),
   **Then** the correct answer and the explanation for that question are not present.
3. **Given** a player submits an answer, **When** the grade comes back, **Then** they see right,
   half right (Spot the bug only: line or problem correct, not both) or wrong, the correct answer,
   and the explanation, and for AI this week also the date and a link to the source.
4. **Given** a player submitted an answer, **When** the same submission is sent again (double
   click, network retry, page reload, a replayed request), **Then** it is counted once and the
   score shown does not change.
5. **Given** a player already finished today's set, **When** they open the daily again on the same
   day, **Then** they see their recorded result, and any replay is marked "not scored" and changes
   nothing.
6. **Given** a player answers only some questions and closes the tab, **When** they come back the
   same day, **Then** they continue from the first unanswered question; answered questions keep
   their grade.

---

### User Story 2 - Streak, freeze and skill view (Priority: P2)

The home screen shows the player's current streak, their longest streak, whether they have a
freeze available, and a skill view: for each deck, how many questions they got right out of how
many they answered.

**Why this priority**: the streak is the reason people come back tomorrow; the skill view tells
them what to practise.

**Independent Test**: on one browser, simulate a sequence of played and missed days and check the
streak, longest streak, freeze and skill view figures against a hand-computed table.

**Acceptance Scenarios**:

1. **Given** a player finished yesterday's daily, **When** they finish today's, **Then** the
   streak goes up by one.
2. **Given** a player has played at least 5 dailies in the current week (Monday to Sunday,
   Europe/Zurich) and has not used a freeze this week, **When** the week's count reaches 5,
   **Then** they earn one freeze (at most one held at a time).
3. **Given** a player holds a freeze and misses exactly one day, **When** they play the next day,
   **Then** the freeze is used, the streak continues, and the missed day is shown as "frozen".
4. **Given** a player misses a day without a freeze, or misses two days in a row, **When** they
   play again, **Then** the streak restarts at 1 and the longest streak keeps its value.
5. **Given** a player has answered questions in several decks, **When** they open the skill view,
   **Then** each deck shows correct answers out of answered questions, with half-right counted as
   half, and the decks are listed weakest first.

---

### User Story 3 - Share the result without spoilers (Priority: P2)

After the daily, the player can copy a share card: game number, level, one square per question,
score, time and streak, and the site address. It reveals nothing about the questions or answers.

**Why this priority**: sharing is how a daily game grows; search will not bring players
(docs/seo-keywords-2026-10-24.md).

**Independent Test**: finish a daily, copy the card, and check its text against the expected
format; check that it contains no question text, answer or deck-specific hint.

**Acceptance Scenarios**:

1. **Given** a player finished today's daily, **When** they press "Copy result", **Then** the
   clipboard holds a card in the format:
   `Stay Sharp #<n> · <Level>` / `<5 squares>  <score>/5 · <m>m<ss>s · streak <k>` / `<site address>`.
2. **Given** the squares use colour, **When** the card is read as text or by a screen reader,
   **Then** each result is still distinguishable (distinct symbols, and the on-screen version has
   a text label per question).
3. **Given** the clipboard is not available, **When** the player presses "Copy result", **Then**
   the card text is selected so it can be copied by hand, and a message says so.

---

### User Story 4 - Challenge a colleague (Priority: P3)

After the daily, the player can create a challenge link. A colleague who opens it plays the same
set (same date, same level). When they finish, both results are shown side by side: squares,
score and time. Neither player sees the other's answers to a question before answering it.

**Why this priority**: a direct invitation converts better than a public post, and it needs no
account. It depends on Story 1.

**Independent Test**: finish a daily on browser A, create a link, open it on browser B, play, and
check that B sees both results and A can see B's result from the same link.

**Acceptance Scenarios**:

1. **Given** a player finished a daily, **When** they create a challenge link, **Then** they get a
   link that identifies only an anonymous result (a random id), not the player.
2. **Given** a colleague opens a challenge link for today's set, **When** they have not played it,
   **Then** they see who challenged them only as "A colleague scored <score>/5" and are invited to
   play; the challenger's per-question squares are hidden until they finish.
3. **Given** a colleague opens a challenge link for a past date, **When** they play it, **Then** it
   is played as a past set: graded and explained, compared side by side, but it does not count
   for their streak.
4. **Given** the colleague has finished, **When** either player opens the link again, **Then**
   both results are shown side by side.
5. **Given** a link with an unknown, malformed or expired id, **When** it is opened, **Then** the
   player sees a plain message and a button to play today's daily; no error details are shown.

---

### User Story 5 - Practice mode with weak spots (Priority: P3)

After the daily (or instead of it), a player can practise with questions from past days, filtered
by deck. Questions they got wrong or half right come back sooner than questions they got right.
Practice is graded and explained like the daily but never changes the streak or the daily result.

**Why this priority**: learning is the point, and the archive grows every day. It depends on
Story 1.

**Independent Test**: answer a practice question wrong, answer others right, and check that the
missed one is offered again before the ones answered right.

**Acceptance Scenarios**:

1. **Given** a player opens practice, **When** they pick a deck (or "all decks"), **Then** they
   get questions only from days that have already been published, never from today or the future.
2. **Given** a player missed a question, **When** they keep practising, **Then** that question
   comes back within the next 5 practice questions; each time it is answered right it waits
   longer before coming back (five steps), and after five right answers in a row it stops being
   prioritised.
3. **Given** a practice question is answered, **When** the grade is shown, **Then** the answer and
   explanation were not in the browser before submitting (same rule as the daily).

---

### User Story 6 - Safe changes and alarms for the maintainer (Priority: P1)

The maintainer ships changes without fear: a change goes live to a small share of traffic first,
and if errors or scoring failures rise it is rolled back without anyone acting. If scoring fails
in production for any reason, the maintainer is alerted.

**Why this priority**: a public game that silently grades wrong, or a bad deploy that stays live,
breaks the trust the game depends on. Required by the constitution (Principles IV and V).

**Independent Test**: deploy a version that deliberately fails to score in a test environment,
and check that the alarm fires, the canary is rolled back and the previous version serves all
traffic again, with no manual step.

**Acceptance Scenarios**:

1. **Given** a scoring attempt fails (any error between receiving an answer and storing its
   grade), **When** the failure happens, **Then** it is counted, logged with the question id and
   a request id (no personal data), and an alarm notifies the maintainer within 5 minutes.
2. **Given** a new version is deployed, **When** it serves the canary share of traffic and errors
   or scoring failures exceed the threshold, **Then** the deployment rolls back to the previous
   version by itself and the maintainer is notified.
3. **Given** a new version passes the canary period without crossing the threshold, **When** the
   period ends, **Then** it serves all traffic.
4. **Given** a change is proposed, **When** it is merged, **Then** lint, tests and an
   infrastructure diff have passed; a failing check blocks the merge.
5. **Given** monthly spend reaches the USD 20 budget, **When** the threshold is crossed, **Then**
   the maintainer is alerted.

---

### User Story 7 - Publish questions (Priority: P2)

The maintainer writes questions, each with its answer, explanation, deck and level (and for AI
this week, date and source), and schedules them into future daily sets. Only questions marked
approved can be scheduled. A daily set cannot be published unless it has exactly one question
per deck.

**Why this priority**: without a stock of approved questions there is no daily.

**Independent Test**: add a set of questions with one invalid entry and check that publishing
rejects the invalid one with a clear reason and accepts the rest.

**Acceptance Scenarios**:

1. **Given** a question file with a missing answer, duplicate id, wrong number of choices or a
   Spot the bug line outside the code, **When** the maintainer publishes, **Then** publication is
   refused with the reason and the question id, and nothing from that batch goes live.
2. **Given** a day without a complete set, **When** that day starts, **Then** the maintainer was
   warned at least 7 days earlier, and players see "Today's set is not ready yet" instead of an
   error.
3. **Given** a question is already part of a published daily, **When** the maintainer edits it,
   **Then** past grades are not changed; the edit applies to future plays only and is recorded.

### Edge Cases

- A player plays across midnight Europe/Zurich: the set they started stays the set they finish,
  and it counts for the date it was started; the new set unlocks after they finish.
- The device clock is wrong or in another time zone: the date of the set and of streak days comes
  from the server, not the device.
- A player clears browser storage: streak, freeze, skill view and practice history are lost
  (stated on the site); the daily already played today shows as not played on that browser, but
  the server keeps the first recorded result for that anonymous player id only.
- Two tabs submit the same question at the same time: one grade is stored, both tabs show it.
- An answer arrives for a question not in today's set, for a future date, or with an out-of-range
  choice: it is rejected with a clear message and nothing is stored.
- The network fails while submitting: the player can retry; the retry is counted once.
- The service is down: the player sees a plain message and a retry button, never a blank page.
- A spot-the-bug snippet is long or wide: it scrolls inside its box on a 390 px screen; the page
  itself never scrolls sideways.
- Keyboard only: every step (choose line, choose answer, submit, next, copy, challenge) works
  with the keyboard, with visible focus.
- A challenge link is opened by the challenger themselves: they see their own result and a prompt
  to share the link, not a second play.

## Requirements *(mandatory)*

### Functional Requirements

**Daily set**

- **FR-001**: The system MUST publish one daily set per date and level, unlocked at 00:00
  Europe/Zurich, made of exactly five questions in this order: Spot the bug, Could do better, What
  if it fails?, Acronym or tool, AI this week.
- **FR-002**: The system MUST serve the same daily set to every player of a level on a given date.
- **FR-003**: The system MUST NOT send the correct answer, the explanation, or anything from which
  they can be derived (for example, the order of choices revealing the answer) to the browser
  before the player has submitted an answer to that question.
- **FR-004**: The system MUST grade every answer on the server, deterministically: the same
  submission for the same question always gets the same grade.
- **FR-005**: Grades MUST be 1 (right), 0.5 (Spot the bug only: right line or right problem, not
  both) or 0 (wrong). The daily score is the sum, out of 5. Time taken is recorded and shown but
  does not change the score.
- **FR-006**: The system MUST record each player's answer to a question at most once per date and
  mode: a repeated or concurrent submission of the same answer returns the stored grade and does
  not count again; a different answer to an already-graded question is refused.
- **FR-007**: After each submission the player MUST see the grade, the correct answer, the
  explanation and, for AI this week, the date and a source link.
- **FR-008**: A partly played daily MUST resume at the first unanswered question on the same day.
- **FR-009**: A daily can be replayed after it is finished; replays are graded and explained but
  marked "not scored" and change nothing.
- **FR-010**: The player MUST be able to choose a level among those available at launch, change it
  later, and the choice is remembered on the browser.

**Anonymous identity**

- **FR-011**: The system MUST give each browser a random, anonymous player id on first visit. No
  name, e-mail, or other personal data is asked for or stored. IP addresses MUST NOT be stored
  with game data or written to application logs.

**Streak, freeze, skill view**

- **FR-012**: The streak MUST count consecutive Europe/Zurich days on which the daily was finished,
  with the day's date taken from the server.
- **FR-013**: A player MUST earn one freeze when they finish 5 dailies in one Monday-to-Sunday week,
  hold at most one, and have it used automatically to cover a single missed day.
- **FR-014**: The longest streak MUST be kept and shown next to the current streak.
- **FR-015**: The skill view MUST show, per deck, correct answers (half counts as half) out of
  answered questions, daily and practice combined, weakest deck first.
- **FR-016**: Streak, freeze, longest streak, skill view and practice history are kept on the
  browser in M1; the site MUST say so plainly.

**Share and challenge**

- **FR-017**: After a finished daily the player MUST be able to copy a share card in the format of
  Story 3, containing no question content.
- **FR-018**: The player MUST be able to create a challenge link for a finished daily that points
  to an anonymous result id.
- **FR-019**: Opening a challenge link MUST let a colleague play that same set, then show both
  results side by side (squares, score, time). The challenger's per-question results stay hidden
  until the colleague finishes.
- **FR-020**: Challenge links MUST expire after 30 days; an expired, unknown or malformed link shows
  a plain message and a way to play today's daily.

**Practice**

- **FR-021**: Practice MUST offer questions only from past published days, filterable by deck,
  with the same grading, explanation and answer-hiding rules as the daily.
- **FR-022**: Missed and half-right questions MUST come back sooner, using five boxes: a miss sends
  a question to box 1; each right answer moves it up one box; higher boxes come back less often;
  box 5 questions are no longer prioritised.
- **FR-023**: Practice MUST NOT change the streak, the freeze or the recorded daily result.

**Content**

- **FR-024**: Every question MUST have an id, deck, level, prompt, choices (exactly four), the
  correct choice (and correct lines for Spot the bug), an explanation, and for AI this week a
  publication date and a source link; questions MUST be validated before publication and an
  invalid batch is refused as a whole.
- **FR-025**: Only questions marked approved by the maintainer can be published. In M1 all
  questions are written by a person; no question text is generated by a model.
- **FR-026**: The maintainer MUST be warned when fewer than 7 future days have a complete set.
- **FR-027**: Editing a published question MUST NOT change grades already given; the change is
  recorded with date and reason.

**Operations**

- **FR-028**: Every scoring failure MUST be counted, logged with question id and request id (never
  personal data), and raise an alarm to the maintainer within 5 minutes.
- **FR-029**: New versions MUST go live to a small share of traffic first and be rolled back
  automatically, without human action, if errors or scoring failures cross a set threshold during
  that period.
- **FR-030**: No change reaches production unless lint, tests and an infrastructure diff have
  passed.
- **FR-031**: An alarm MUST alert the maintainer when monthly spend reaches USD 20.
- **FR-032**: Answer submissions MUST be validated (known question, today's or allowed date, valid
  choice and line range, size limit) and rate-limited per client; invalid requests store nothing.

**Accessibility and performance**

- **FR-033**: Every page MUST meet WCAG 2.2 AA, be fully playable with the keyboard, carry no
  information by colour alone, and respect reduced motion.
- **FR-034**: Every page MUST score 100 in Lighthouse Performance, Accessibility, Best Practices
  and SEO on mobile and on desktop.
- **FR-035**: The site MUST have a short page that says what is stored, where (Switzerland or EU),
  and that clearing the browser removes local progress.

### Key Entities

- **Question**: one item of content. Deck, level, prompt, optional code or diagram, four choices,
  correct choice, correct lines (Spot the bug), explanation, source and date (AI this week),
  approval status, version.
- **Daily set**: a date and a level, with five question references in deck order. Has a game
  number (#n) counted from launch day.
- **Anonymous player**: a random id per browser. No personal data.
- **Answer record**: player id, date, mode (daily, replay, practice, challenge), question id,
  submitted choice and line, grade, time of submission. At most one per player, date, mode and
  question.
- **Daily result**: player id, date, level, five grades, score, time taken.
- **Challenge**: random id, the daily result it points to, the date and level of the set, the
  results of players who answered it, expiry date.
- **Local progress** (browser only): current and longest streak, freeze, played days, skill view
  counts, practice boxes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A player can play a full daily set in about 5 minutes; the median time to finish,
  measured over the first 4 weeks, is under 6 minutes.
- **SC-002**: In an automated check run before every release, zero correct answers or explanations
  are found in anything the browser receives before submitting, for every question of the next 7
  days.
- **SC-003**: In an automated check, submitting the same answer 2, 10 and 50 times (in sequence
  and at the same time) always yields exactly one recorded grade and an unchanged score.
- **SC-004**: In a test environment, an injected scoring failure triggers a maintainer alert
  within 5 minutes, every time it is tested.
- **SC-005**: In a test environment, a deployment that injects failures is rolled back with no
  human action, and the previous version serves 100% of traffic again within 15 minutes of the
  start of the deployment.
- **SC-006**: Every page scores 100 in all four Lighthouse categories on mobile and desktop, and
  passes keyboard-only play of a full daily.
- **SC-007**: A page and the first question are usable within 2 seconds on a mid-range phone on a
  4G connection.
- **SC-008**: At launch, approved daily sets exist for at least 14 future days, and the stock
  warning has never been missed by the time it is needed.
- **SC-009**: Monthly cost stays under USD 20, and the real figure is published in the README with
  its date after the first full month.
- **SC-010**: After 4 weeks live, the share of players who come back on a second day and the share
  of challenge links that lead to a finished game are measured and published with their dates
  (no target set before measuring).

## Assumptions

- **Levels at launch**: [NEEDS CLARIFICATION: Which levels are playable at M1 launch? The
  prototype has only Senior, and every extra level needs its own daily stock (5 questions a day
  per level).]
- **Time bonus**: [NEEDS CLARIFICATION: docs/spec.md mentions a capped time bonus; the prototype
  has none. This spec assumes no time bonus (time is shown, not scored). Keep it that way, or add
  a capped bonus?]
- **Game number**: #1 is the M1 launch day for everyone; the number is the same at every level.
- **AI this week** questions are written by hand in M1 from public, dated sources; the automated
  news pipeline is M3.
- **Content stock**: 14 days of approved sets at launch (the prototype's stock, reviewed); the 60
  days in docs/spec.md are for the public launch (M4).
- **Anonymous id**: kept in the browser; the server stores answers under it to enforce
  "count once" and to allow an account to adopt the history in M2.
- **Retention**: anonymous answer records and challenges are deleted after 90 days and 30 days
  respectively; there is no personal data to delete in M1.
- **Analytics**: only aggregate, cookie-free counts (plays, finishes, challenge opens) are
  recorded, so no consent banner is needed.
- **Constraints set by the project (not open in this spec)**: React 19 + Vite + Tailwind front end;
  Python Lambda API with AWS Lambda Powertools; DynamoDB; AWS CDK in Python; GitHub Actions CI;
  canary deploys with automatic rollback; region eu-central-2 (Zurich); a dedicated AWS account
  per environment; address stay-sharp.lumineth.com. See the constitution.
- **Out of M1**: accounts and sign-in, syncing across devices, public leaderboard, private
  groups, badges, reminders, the model-based news pipeline and admin approval screen, mobile store
  app, paid features. Questions are published by the maintainer from files, not from an admin
  screen.
