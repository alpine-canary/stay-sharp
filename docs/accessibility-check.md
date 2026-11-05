# Manual accessibility check (SC-007a, task T119)

Automated checks (axe on every view, `front/tests/e2e/a11y.spec.ts`; Lighthouse accessibility
100) catch part of the problems only. Before launch, a person plays a full **relaxed** daily with
the keyboard only, then again with a screen reader, on the dev site. The result and the date are
recorded below. It is not done until a person has done it: no row is filled in by an agent.

## Setup

- The dev site address (the CloudFront domain of `staysharp-dev-web`), a fresh browser profile.
- Keyboard pass: no mouse or trackpad at all.
- Screen reader pass: VoiceOver with Safari on macOS (Cmd+F5), or NVDA with Firefox on Windows.

## Steps (each must work, with visible focus at every step)

1. Home: choose a level, switch relaxed mode on, start the daily.
2. For each of the five questions:
   - the question title is read first;
   - on Spot the bug, pick a line in the code with the arrow keys and Enter;
   - choose an answer, submit, hear the verdict and the explanation;
   - go to the next question.
3. Result: the five results are read with words ("right", "half right", "wrong"), not colours;
   copy the share card; create a challenge link and copy it.
4. Open the challenge link in a second browser and play it the same way.
5. Practice: change the deck, answer one question.
6. Privacy page: read it to the end.
7. Zoom the browser to 200 % and repeat step 2 for one question: nothing is cut off and the page
   never scrolls sideways.

## Results

| Date | Tester | Pass | Browser and reader | Problems found | Fixed in |
|---|---|---|---|---|---|
