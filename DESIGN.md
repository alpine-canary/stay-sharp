# DESIGN.md: Stay Sharp

Visual rules for the game at stay-sharp.lumineth.com. Stay Sharp is a Lumineth product: it uses
Lumineth's brand (navy, teal, mint on navy only, Source Serif 4 and IBM Plex Sans), made playful
by one idea: **calm paper for reading, navy "islands" for the parts that make it a game** (the
code, the verdict squares, the streak, the score). CSS: `front/src/index.css`.

## Colours

Every pair is measured in `front/src/contrast.test.ts` (text 4.5:1, UI parts 3:1, both themes).

| Role | Light | Dark | Where |
|---|---|---|---|
| Page | `#F4F6F8` | `#0B1F33` | page background |
| Surface | `#FFFFFF` | `#0F2A44` | cards, answer options |
| Ink / muted | `#111A22` / `#4F5D6B` | `#E6EDF3` / `#A9B9C9` | text, hints |
| Line / strong | `#D8E0E7` / `#74828F` | `#23405E` / `#6F8AA6` | borders; strong for controls |
| Primary button | navy `#0F2A44`, white text | mint `#5FD3B4`, navy text | Play, Check, Next, Copy result |
| Link, eyebrow | teal-ink `#0A5F4E` | mint | links, small capitals |
| Right | `#0E7C66` on `#ECF7F3` | mint | right answer, square |
| Wrong | `#B3261E` on `#FBE9E7` | `#FF8A80` | wrong answer, square |
| Half right | amber `#8A5A0E` on `#FBF0DC` | `#E9B35A` | half-right answer, square |
| Island | `#0B1F33`, text `#E6EDF3`, muted `#8FA3B8` | `#081726` | code, status, result, streak |

- **Mint only on navy** (Lumineth rule): on islands, and on the dark page, which is navy too.
- **Amber** is Lumineth's colour for proof figures; Stay Sharp also uses it for "half right",
  because the game needs a third verdict colour. Documented exception.
- One primary button per screen; everything else is a ghost button or a text link.

## Type

- **Source Serif 4, 600**: headings, the question, the score and streak figures. Lining figures
  (`lining-nums`); never `tabular-nums` on a decimal, its tabular point sits too high.
- **IBM Plex Sans 400 and 600**: body (17 px), options, buttons, eyebrows (600, 14.5 px,
  `letter-spacing .1em`, capitals).
- **Mono**: the system's (`ui-monospace, SFMono-Regular, Menlo, monospace`), no download. Code
  14.5 px; deck chips and timer 13 to 14 px. Text between backticks in an explanation is code.
- Nothing under 14.5 px except mono labels. Three font files, all preloaded, `font-display:
  optional`.

## Layout

- `.wrap` 1120 px, 16 px gutter on a phone, 24 px from 768 px. Header: mark + "Stay Sharp" and
  "by Lumineth". Footer: one aligned bar, "© 2026 Lumineth" and Privacy.
- **Home**: H1 "Stay Sharp" on one line, the one-line pitch, then two columns from 1024 px: the
  today card (deck chips, level, relaxed, Play) and an island ("How it plays" for a new visitor,
  the streak and skills once they have played). Practice is a strip below. Senior is chosen until
  the player picks Starter, so the Play button is always there.
- **Play**: the question card on the left; on the right a status island (set, question n/5,
  timer, squares, relaxed link), and the feedback with Next under it. On a phone: status, question,
  feedback. On a phone the code wraps instead of scrolling sideways.
- **Result**: an island with the squares (48 px), the score (72 to 88 px) and one muted line for
  bonus and time; the share card and the challenge link as cards on the right; Replay and Back as
  text links.

## Motion

`--ease-out: cubic-bezier(.23,1,.32,1)`. Transform and opacity only; nothing loops; under
`prefers-reduced-motion` every element shows its final state.

- A verdict square flips in (scale .6 to 1, 240 ms); on the result they follow each other 60 ms
  apart.
- The feedback rises 8 px (200 ms, transform only so its text is never measured faded).
- The speed bonus chip lifts 6 px and settles (600 ms).
- Buttons press to `scale(.97)` (160 ms).

## Checks

- Screenshots of every view at 390 and 1440 px, light and dark:
  `SHOTS=<label> pnpm --dir front exec playwright test shots` (files in `var/shots/<label>/`).
- axe in light and dark (`tests/e2e/a11y.spec.ts`), Lighthouse on mobile and desktop
  (`pnpm --dir front lhci`), contrast pairs (`contrast.test.ts`).
