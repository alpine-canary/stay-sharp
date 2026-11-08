# Feature Specification: Daily AI news questions

**Feature Branch**: `003-news-pipeline`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "M3 news pipeline brought forward: the AI this week deck (Senior and
Junior) gets a fresh question every day, written automatically from trusted, recent sources,
checked by code and by a second, independent model pass, and published for the day 3 days ahead
without human approval (maintainer decision 2026-11-08). The other decks are written 14 days
ahead and approved in batch. A reserve question fills the news slot when the job fails. Costs
bounded, dev on recorded fixtures only, any real model call approved first."

## Context

Today every question is written ahead and approved by the maintainer (M1 FR-025, constitution
principle III). The AI this week deck goes stale: a story written 14 days ahead is old news on
the day it is played. On 2026-11-08 the maintainer decided that this one deck is written by an
automated job close to the day it is played, and published without a person approving each
question, provided automated checks pass. Everything else keeps the M1 rules.

This feature needs an amendment of constitution principle III, limited to the AI this week deck,
before any code ships (see FR-020).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A fresh news question every day (Priority: P1)

A Senior or Junior player opens today's set. The fifth question, AI this week, is about a story
published in the last 10 days, from a trusted primary source. After answering, the player sees
the explanation, the source's date and a link to it.

**Why this priority**: this is the whole point of the feature. A news deck about old news is
worse than none.

**Independent Test**: with the job running on recorded sources and recorded model answers, the
set for the day 3 days ahead gets a news question for each of Senior and Junior, whose source is
dated within the window and whose link works.

**Acceptance Scenarios**:

1. **Given** the job runs on day D, **When** it finishes, **Then** the sets of D+3 for Senior and
   Junior each contain one AI this week question, about a story published between D-7 and D, from
   a source on the trusted list.
2. **Given** a published news question, **When** a player answers it, **Then** they see the
   explanation, the source's publication date and a working link, and nothing of these reaches
   the browser before the answer (M1 FR-003).
3. **Given** a story already used in the last 30 days, **When** the job looks for news, **Then**
   it does not use that story again.

---

### User Story 2 - Nothing wrong goes out on its own (Priority: P1)

The maintainer trusts the job because every question passes a fixed set of checks before it can
be published, and a question that fails any check is never published.

**Why this priority**: with no person approving each question, the checks are the only gate.
A wrong answer published to every player damages the game's credibility (constitution I).

**Independent Test**: feed the job recorded drafts that each break one rule (wrong answer, answer
not in the source, two identical choices, source too old, source not on the list, broken link,
instructions hidden in the source page, text too long, unsafe words for Junior); none is
published, each is logged with the check that failed.

**Acceptance Scenarios**:

1. **Given** a draft whose right answer is not supported by the source text, **When** it is
   checked, **Then** it is rejected and not published.
2. **Given** a draft that passes the code checks, **When** the independent verification pass
   (a separate model call that sees only the source text and the question, not the draft's
   reasoning) disagrees on the right answer or finds a second defensible answer, **Then** it is
   rejected.
3. **Given** a source page that contains text addressed to the model ("ignore your
   instructions..."), **When** it is processed, **Then** that text is treated as data: it never
   changes what the job does, and the job rejects the story if its draft is affected.
4. **Given** a question is published, **Then** an audit record names the source, the checks that
   passed, the model versions that drafted and verified it, the time, and the cost of the calls.

---

### User Story 3 - A day is never incomplete (Priority: P1)

If the job fails, finds no suitable story, or rejects every draft, the news slot of that day is
filled by a reserve question approved in advance by the maintainer, and the maintainer is told.

**Why this priority**: an incomplete daily set breaks the game for everyone that day (M1 FR-001).

**Independent Test**: make the job fail on D (no source reachable); at the latest when D+2 begins,
the set of D+3 holds a reserve question; an alert reaches the maintainer the day it fails.

**Acceptance Scenarios**:

1. **Given** no news question passed for D+3 by the end of D+1 (two attempts), **When** the
   fallback step runs, **Then** a reserve question that was never played fills the slot, and the
   maintainer gets an alert.
2. **Given** fewer than 5 unused reserve questions remain per level, **Then** the maintainer gets
   a stock alert.
3. **Given** a reserve question is used, **Then** it is never used again as a reserve.

---

### User Story 4 - The maintainer stays in control (Priority: P2)

The maintainer can switch the job off and on, see what it published and why, and withdraw a news
question from a future day (it is replaced by a reserve question). Switching the job on is the
maintainer's approval of its real model calls (constitution III, as amended).

**Why this priority**: an automated publisher needs an off switch and a way to correct it.

**Independent Test**: switch the job off; the next run makes no model call and publishes nothing,
and reserves fill the slots; withdraw a future question; the day's set shows a reserve question
instead.

**Acceptance Scenarios**:

1. **Given** the job is off, **When** its schedule fires, **Then** it makes no model call and
   says so in its log, and the fallback still fills open slots.
2. **Given** a news question scheduled for a future day, **When** the maintainer withdraws it,
   **Then** that day's set uses a reserve question; today's and past sets never change (M1 rule).
3. **Given** the maintainer reads the job's report for a day, **Then** it lists counts, story
   links, check results and cost, and no question text in logs (question text stays in the
   private store only).

---

### User Story 5 - The rest of the set is written ahead (Priority: P2)

The four other Senior and Junior decks and all five Starter decks are written 14 days ahead and
approved by the maintainer in batch. Only the news slot of days 4 to 14 stays open until the job
fills it.

**Why this priority**: it lets the launch stock and the news job work together without breaking
the rule that a published set has exactly one question per deck.

**Independent Test**: publish 14 days of four-deck schedules for Senior and Junior; days 1 to 3
are complete, days 4 to 14 have an open news slot; the stock check reports 14 days for the
written decks and 3 days for news, and raises no false alarm.

**Acceptance Scenarios**:

1. **Given** a schedule with the news slot left open for a future day, **When** it is published,
   **Then** publish accepts it; a set is served to players only when all five slots are filled.
2. **Given** the day D+3 still has an open slot when D+3 is 24 hours away, **Then** the fallback
   fills it (User Story 3).
3. **Given** the stock check runs, **Then** it reports, per level, the days ahead with the
   written decks complete and, separately, the days ahead with a filled news slot, and alarms
   below 7 and below 2 respectively.

### Edge Cases

- Two trusted sources publish the same story: it counts as one story for the 30-day rule.
- A source changes or removes its page after publication: the question stays (it was true and
  sourced when published); the link may break later, which is acceptable for past days.
- The best story is about a product launch: the question asks what it does or changes, never
  promotes it; Junior wording stays plain.
- A story is ambiguous or only rumoured: rejected, only announced facts count.
- The model service is slow or throttled: limited retries with backoff, then the run fails and
  the fallback applies.
- The job runs twice the same day (retry, manual run): the second run does not create a second
  question for the same slot.
- Daylight saving change or a late run near midnight Europe/Zurich: days are counted in
  Europe/Zurich, like the daily sets.
- Cost runs away (bug, loop): a hard cap on calls per run and per day stops the job.
- Starter has no news deck and is not affected.

## Requirements *(mandatory)*

### Functional Requirements

**Sources and selection**

- **FR-001**: The job MUST read stories only from a fixed, versioned list of trusted sources
  (official announcements, release notes and blogs of AI labs and developer-tool vendors, standards
  bodies, and papers), kept in the private content repository and changed only by the maintainer.
- **FR-002**: The job MUST consider only stories published in the 7 days before the run, and MUST
  NOT reuse a story (same link or same event) used in the last 30 days.
- **FR-003**: The job MUST rank candidate stories by relevance to developers who work with coding
  agents and pick the best one that passes the checks; it MAY use a different story for Senior
  and Junior.

**Drafting and checks**

- **FR-004**: For each of Senior and Junior, the job MUST draft one question in the M1 question
  format (FR-024): prompt, four distinct choices, one right choice, explanation, source link and
  publication date.
- **FR-005**: Every draft MUST pass code checks before any further step: schema and length limits,
  four distinct choices of similar length, source on the list and reachable, source date in the
  window, the right answer's key facts present in the source text, no question text or answer
  copied from a past question, language rules (English, no long dashes), Junior wording within the
  Junior reading level.
- **FR-006**: Every draft that passes FR-005 MUST be verified by a second, independent model pass
  that sees only the source text and the question (not the drafting instructions or reasoning),
  answers the question itself, and confirms one and only one defensible right answer, matching
  the draft's. Any disagreement rejects the draft.
- **FR-007**: Text fetched from the internet MUST be treated as untrusted data: it is never
  followed as instructions, and a draft that contains instructions, links or claims not in the
  question's source is rejected.
- **FR-008**: A rejected draft MUST NOT be published; the job MAY try the next story, within the
  per-run limit (FR-015).

**Publishing**

- **FR-009**: A draft that passes FR-005 and FR-006 MUST be published automatically into the news
  slot of the set for the day 3 days after the run (Europe/Zurich), for its level, with no human
  approval, and marked as written by the job.
- **FR-010**: Publishing MUST be idempotent: one news question per level per day, whatever the
  number of runs or retries.
- **FR-011**: Question text and answers MUST stay in the private store and MUST NOT appear in the
  public repository, logs, metrics or the browser before answering (M1 FR-003, FR-024b).
- **FR-012**: Every published question MUST have an audit record: source link and date, check
  results, model and version for drafting and for verification, time, number of calls and cost.

**Fallback and stock**

- **FR-013**: If no question was published for a slot by the time its day is 2 days away, a
  reserve question for that level MUST fill it, and the maintainer MUST be alerted. Reserve
  questions are AI this week questions written and approved by the maintainer in advance, whose
  facts stay true, used at most once.
- **FR-014**: The stock check MUST report, per level, the days ahead with the four written decks
  complete and the days ahead with a filled news slot, and the number of unused reserve questions;
  it MUST alert below 7 days, below 2 days and below 5 reserves respectively.

**Cost and limits**

- **FR-015**: Each run MUST be bounded: at most 4 candidate stories tried per level, at most 12
  model calls per run, a maximum output size on every call, a timeout on every call, and retries
  with backoff for temporary errors only. A daily cap MUST stop any further call that day.
- **FR-016**: Every model call MUST log its token counts and cost (never the text); the monthly
  cost of the job MUST stay under USD 3, and the account stays under its USD 20 budget.
- **FR-017**: The model service MUST run in the EU, through an EU inference profile (constitution
  VI).

**Control**

- **FR-018**: The maintainer MUST be able to switch the job off and on without a deploy. Off means
  no model call and no publication; the fallback still fills slots.
- **FR-019**: The maintainer MUST be able to withdraw a news question from a future day; the
  fallback then fills the slot. Today's and past sets never change.
- **FR-020**: Before any code of this feature ships, constitution principle III MUST be amended:
  for the AI this week deck only, a question may reach players without a person approving it,
  if every check of FR-005 and FR-006 passed and the audit record of FR-012 exists; switching the
  job on (FR-018) is the maintainer's approval of its bounded real model calls.

**Development and tests**

- **FR-021**: Dev and CI MUST run the job only on recorded sources and recorded model answers;
  no real model call happens outside prod without the maintainer's go-ahead each time.
- **FR-022**: An offline evaluation set of at least 30 recorded stories, each with good and
  deliberately broken drafts, MUST show that every broken draft is rejected before the job is
  switched on in prod.

### Key Entities

- **Trusted source**: a name, a feed or page to read, the kind of source, active or not.
- **Story**: a link, title, publication date, source, the event it is about (for the 30-day rule).
- **News draft**: the question in M1 format, its level, story, the drafting model and version,
  and its state (rejected with reasons, or published).
- **Check result**: for a draft, each check's name and pass or fail.
- **Run**: date, level results, number of calls, cost, outcome (published, fallback, off, failed).
- **Reserve question**: an approved AI this week question for one level, used or unused.
- **Job switch**: on or off, who changed it and when.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Over any 30 days, at least 90% of Senior and Junior days have a news question about a
  story at most 10 days old when played; the others use a reserve question.
- **SC-002**: 100% of days have a complete five-question set for every level.
- **SC-003**: In the offline evaluation set, 100% of deliberately broken drafts are rejected, and
  at least 70% of good drafts are accepted.
- **SC-004**: No published question is found wrong by the maintainer's weekly spot check of 7
  questions in the first 4 weeks; any one found wrong is withdrawn or corrected the same day.
- **SC-005**: The job's model cost stays under USD 3 a month, measured from the logged costs.
- **SC-006**: No question text or answer appears in logs, metrics, the public repository or the
  browser before answering (checked by the existing leak checks extended to job output).

## Assumptions

- Senior and Junior only; Starter has no news deck.
- The publication date of a story is the date stated by its source; when a source gives none,
  the story is skipped.
- One run a day, early morning Europe/Zurich, plus one retry the next day for a slot still open.
- "3 days ahead" leaves 2 days for a retry and the fallback before players see the set.
- The trusted source list starts with about 10 to 20 sources chosen by the maintainer from a
  proposed list; adding a source is a change in the private content repository.
- The launch stock (14 days of the other decks for all levels, 3 days of news, and an initial
  set of at least 10 reserve questions per level) is written separately and approved in batch.
- The model choice (a current Claude model on Amazon Bedrock with an EU inference profile) and
  prices are settled in the plan; FR-016's ceiling holds whatever the choice.
- Prod must exist (M1 deploy) before the job can publish; until then it runs in dev on fixtures.
