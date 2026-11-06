# Feature Specification: Optional accounts (M2)

**Feature Branch**: `002-accounts`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "M2 accounts for Stay Sharp, as planned in docs/spec.md section 2.4: an
optional account, never asked before the first game, offered when it has value ("Keep your 12-day
streak on your phone too?"). Sign-in without a password: a passkey or an e-mail link. Stored: the
e-mail and a display name, nothing else. The account adopts the browser's existing history, so
streaks follow the player across devices. Signing out keeps playing anonymously. A "Delete my
account" button removes the account and all its data (nFADP / GDPR). Players under 16 need a
parent's consent to create an account; Starter stays fully playable without an account. No
leaderboard, private groups, badges or reminders in this feature. Keep M1 rules."

## Clarifications

### Session 2026-11-06

- Q: What happens when a player under 16 wants an account? -> A: No account under 16 in this
  feature. The player is asked whether they are 16 or older before giving an e-mail; under 16,
  nothing is stored and they keep playing anonymously. Parental consent may come in a later
  feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep my streak on another device (Priority: P1)

A player has played on their laptop for twelve days. On the result screen they see "Keep your
12-day streak on your phone too?". They create an account with their e-mail, without a
password. On their phone they sign in with the same e-mail and find the same streak, freeze,
skills and practice progress for every level, and today's set already marked as played.

**Why this priority**: this is the reason an account exists. Without it, an account has no
value and the game is complete without one.

**Independent Test**: play three dailies on browser A, create an account there, sign in on a
fresh browser B, and check that B shows the same streak, freeze, skill view and today's result,
and that playing tomorrow on B continues the same streak on A.

**Acceptance Scenarios**:

1. **Given** a player with a 12-day Senior streak in this browser and no account, **When** they
   create an account, **Then** the account holds their 12-day streak, longest streak, freeze,
   skill counts and practice progress for Starter, Junior and Senior, and nothing is lost in
   this browser.
2. **Given** an account with a streak, **When** the player signs in on a new browser, **Then**
   that browser shows the account's progress within a few seconds, and today's set shows as
   played if it was played on any device.
3. **Given** a player signed in on two devices, **When** they play today's set on one,
   **Then** the other shows it as played the next time it opens, and the daily cannot be scored
   twice.
4. **Given** a player signs in on a browser that already has its own anonymous progress,
   **When** the account is opened there, **Then** both histories are merged: every day played
   on either counts once, streaks are recomputed from the merged days, and the player is told
   that the two were combined.

---

### User Story 2 - Sign in without a password (Priority: P1)

A player who wants an account gives their e-mail. They prove it is theirs with a one-time
e-mail code or link, or with a passkey on a device that has one. There is never a password to
create, remember or reset.

**Why this priority**: the account is only worth offering if creating it takes under a minute
and leaves nothing to forget.

**Independent Test**: create an account with an e-mail only, sign out, sign back in with the
e-mail code or link, then add a passkey and sign in with it on the same device.

**Acceptance Scenarios**:

1. **Given** a player on the account screen, **When** they enter their e-mail and the one-time
   code or link they receive, **Then** they are signed in, with no password asked at any
   point.
2. **Given** a signed-in player on a device that supports passkeys, **When** they add a
   passkey, **Then** their next sign-in on that device needs only the passkey.
3. **Given** a wrong or expired code or link, **When** it is used, **Then** sign-in is refused
   with a plain message and a way to get a new one; nothing tells whether the e-mail has an
   account.
4. **Given** repeated attempts from one place, **When** a limit is reached, **Then** further
   attempts are slowed or refused for a while.

---

### User Story 3 - Delete my account (Priority: P1)

A player decides to stop. In their account page, "Delete my account" removes the account and
all the data kept about it, after one clear confirmation. The game keeps working in that
browser as a new anonymous player.

**Why this priority**: a legal duty (nFADP, GDPR) and a constitution rule (Principle VI): an
account cannot ship without it.

**Independent Test**: create an account with progress, delete it, and check that no record of
the e-mail, display name, plays, answers or progress remains, and that signing in with that
e-mail starts from nothing.

**Acceptance Scenarios**:

1. **Given** a signed-in player, **When** they confirm "Delete my account", **Then** the
   account, the e-mail, the display name, the passkeys, the server-side plays and answers of
   that player, and the progress copy are removed, and the player sees a confirmation.
2. **Given** a deleted account, **When** the same e-mail is used again, **Then** it creates a
   new, empty account.
3. **Given** a deletion that fails half-way, **When** it is retried, **Then** it finishes, and
   the player is never told it succeeded before it has.
4. **Given** results the player shared or challenges they created before deleting, **When**
   someone opens those links, **Then** the challenge shows no data that could identify the
   deleted player.

---

### User Story 4 - Asked at the right moment, never before (Priority: P2)

A new player plays without ever seeing a sign-up prompt. The account is offered only once it
protects something the player has: after a finished daily once they have a streak worth
keeping, and from a quiet "Account" link at any time.

**Why this priority**: the M1 promise ("no account, play now") must stay true; a prompt at the
wrong time drives players away.

**Independent Test**: a first visit, a first play and a first result show no account prompt; a
result with a streak of at least 3 shows the offer once; dismissing it hides it for a week.

**Acceptance Scenarios**:

1. **Given** a first-time visitor, **When** they open the home, play and see their result,
   **Then** no sign-up prompt appears anywhere.
2. **Given** a player with a streak of 3 days or more and no account, **When** they finish a
   daily, **Then** the result screen offers once "Keep your N-day streak on your phone too?".
3. **Given** the offer was dismissed, **When** the player finishes the next dailies, **Then**
   it does not appear again for 7 days.
4. **Given** any player, **When** they look for it, **Then** an "Account" link in the header
   or footer opens sign-in at any time.

---

### User Story 5 - Players under 16 (Priority: P2)

A 13-year-old plays Starter every day. They can play everything without an account. If they try
to create one, they are asked whether they are 16 or older; under 16, no account is created in
this feature, and they keep playing with their progress in the browser.

**Why this priority**: GDPR article 8 and the nFADP; Starter's audience starts at 12.

**Independent Test**: answer "under 16" when creating an account and check that no account and
no e-mail are stored, that a friendly message explains why, and that the game stays fully
playable.

**Acceptance Scenarios**:

1. **Given** a player who says they are under 16, **When** they try to create an account,
   **Then** no account is created and nothing they typed is stored, and a friendly message says
   accounts start at 16 and their progress stays in this browser.
2. **Given** a player under 16 without an account, **When** they play Starter, Junior or Senior,
   **Then** everything in M1 works as before, including streaks in their browser.

---

### User Story 6 - Sign out and play on (Priority: P3)

A player signs out on a shared computer. The browser forgets the account and its progress; the
next person plays as a new anonymous player.

**Why this priority**: needed for shared devices; rare otherwise.

**Independent Test**: sign out, then check that the account's progress no longer shows and that
a new anonymous play works.

**Acceptance Scenarios**:

1. **Given** a signed-in player, **When** they sign out, **Then** this browser shows no progress
   from the account and plays as a new anonymous player; the account keeps everything.
2. **Given** a signed-out browser, **When** the player signs in again, **Then** the account's
   progress comes back.

### Edge Cases

- The same daily played on two devices before they synchronise: the first finished play counts,
  the other is shown as a replay that is not scored.
- A player signs in mid-play: the play goes on and counts for the account.
- The device is offline when progress changes: it is kept locally and sent at the next
  connection; nothing is lost and nothing counts twice.
- The e-mail code or link is opened on a different device from the one that asked for it: it
  signs in the device that opens it, never silently the other one.
- An e-mail with upper-case letters or spaces around it is the same account as its trimmed,
  lower-case form.
- A display name that is empty, too long, or contains a link or offensive words is refused with
  a plain message.
- Sign-in service down: the game keeps working anonymously; the account screen says sign-in is
  unavailable for now.
- Deleting an account while signed in on another device: that device is signed out at its next
  request and becomes a new anonymous player.
- Storage blocked in the browser (private mode): the account still works for the session;
  progress comes from the account.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-101**: Playing every M1 feature (daily, replay, practice, share card, challenges, all
  three levels) MUST NOT require an account.
- **FR-102**: The system MUST NOT show any sign-up prompt before the player has finished at least
  one daily, and MUST offer an account on the result screen only when the player's streak in
  that level is 3 days or more; a dismissed offer MUST stay hidden for 7 days.
- **FR-103**: An "Account" entry MUST be reachable from every page.
- **FR-104**: A player MUST be able to create an account and sign in with an e-mail address and
  a one-time code or link sent to it; no password MUST ever be asked or stored.
- **FR-105**: A signed-in player MUST be able to add a passkey and sign in with it; they MUST be
  able to remove a passkey.
- **FR-106**: One-time codes and links MUST expire after 10 minutes and work once; failed
  attempts MUST be limited; sign-in responses MUST NOT reveal whether an e-mail has an account.
- **FR-107**: The account MUST store only the e-mail address, a display name, the passkeys'
  public parts, the creation date and the age-group answer; nothing else about the person.
- **FR-108**: The display name MUST be optional, 2 to 24 characters, letters, digits, spaces,
  hyphens and underscores only; it is shown only to the player in this feature.
- **FR-109**: When an account is created, it MUST adopt this browser's player id and its
  server-side plays, answers and challenges, and its local progress for every level.
- **FR-110**: When a player signs in on a browser that has its own anonymous progress, the two
  MUST be merged: each date counts once per level (the first finished play wins), streaks,
  longest streaks and freeze state are recomputed from the merged days, skill counts and
  practice boxes are combined, and the player is told the histories were combined.
- **FR-111**: A signed-in player's progress MUST be the same on every device they use: changes
  on one device MUST appear on another within 1 minute of it opening or coming back online.
- **FR-112**: The daily of a given date and level MUST be scored at most once per account,
  whatever the number of devices; any other play of it is an unscored replay.
- **FR-113**: Signing out MUST remove the account's data from the browser and start a new
  anonymous player id there; the account keeps everything.
- **FR-114**: "Delete my account" MUST, after one confirmation, remove the account, its e-mail,
  display name, passkeys, the player's server-side plays, answers, practice records and
  progress copy, and any link between the account and a challenge. It MUST be idempotent and
  complete within 1 minute; the player MUST be told only once it is done.
- **FR-115**: After deletion, challenges created by the player MUST still open but show no
  data that identifies the deleted player (their result appears as "deleted player" or is
  removed).
- **FR-116**: Before creating an account, the system MUST ask whether the player is 16 or
  older, before the e-mail is asked. Under 16, no account MUST be created and nothing typed MUST
  be stored; a friendly message says accounts start at 16 (clarification 2026-11-06). Starter,
  Junior and Senior MUST stay fully playable without an account at any age.
- **FR-117**: Server logs MUST NOT contain e-mails, display names, codes, links, tokens or IP
  addresses; they MAY contain the opaque account id and player hash.
- **FR-118**: The sign-in and account pages MUST meet WCAG 2.2 AA (including accessible
  authentication: no memory or transcription test beyond copying a code, and paste allowed),
  and every page MUST keep Lighthouse 100 in all four categories on mobile and desktop.
- **FR-119**: The privacy page MUST say what an account stores, where (Switzerland or the EU),
  for how long, and how to delete it, before the player creates one.
- **FR-120**: An account inactive for 24 months MUST be deleted, after an e-mail warning 30 days
  before.
- **FR-121**: If the sign-in service is unavailable, the game MUST keep working anonymously and
  the account page MUST say so plainly.
- **FR-122**: Answers MUST still never reach the browser before the player answers, signed in or
  not (M1 rule, unchanged).

### Key Entities

- **Account**: one person who chose to keep their progress. E-mail (unique, normalised), optional
  display name, age group answer, creation date, last activity date, passkeys. Linked to one or
  more player ids.
- **Player id**: the anonymous id a browser already has in M1. An account adopts the player ids
  of the browsers it signs in on; plays and answers stay keyed by player id.
- **Progress copy**: the account's progress per level (days played with their results, longest
  streak, freeze, skill counts, practice boxes), merged from its devices.
- **Passkey**: a public key registered on one of the player's devices, with a name and a date.
- **Sign-in attempt**: a short-lived one-time code or link, with its expiry and attempt count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-101**: A player creates an account, from tapping the offer to being signed in, in under
  1 minute (median, measured in a test with 5 people).
- **SC-102**: After signing in on a new device, the player's streak shows within 3 seconds on a
  mid-range phone.
- **SC-103**: 100 % of progress survives: in tests merging two browsers' histories, no played day
  is lost and none is counted twice.
- **SC-104**: A deleted account leaves no record of its e-mail, display name or progress
  anywhere the system controls within 1 minute (backups excepted, which expire within 35 days).
- **SC-105**: No player sees a sign-up prompt before finishing their first daily (checked by an
  automated browser test on a fresh browser).
- **SC-106**: Every page, including sign-in and account, keeps Lighthouse 100 in all four
  categories on mobile and desktop and has no WCAG 2.2 AA violation in automated checks.
- **SC-107**: The monthly cost stays under the USD 20 budget with 1,000 accounts.

## Assumptions

- The sign-in service is a managed one in the same cloud and region family as M1 (Switzerland,
  or the EU where a service is missing there); the plan picks it.
- The e-mail carries a one-time code, a link, or both; the plan picks what the service supports
  best. Either satisfies FR-104.
- Display names are not shown to anyone else until a later feature (leaderboard, groups) asks
  for it with its own consent.
- Anonymous plays keep their M1 expiry (about 90 days); plays adopted by an account are kept
  while the account exists.
- Backups (point-in-time recovery) keep deleted data for at most 35 days and are not restored
  into the live table for a deleted account; this is said on the privacy page.
- Leaderboards, private groups, badges and reminders are out of scope (later M2 features).
- Production deploy needs the maintainer's approval, as in M1.
