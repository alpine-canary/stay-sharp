# 0001. Clean history before the repository goes public

**Date**: 2026-11-03 | **Status**: accepted

## Context

The first commits were written as private notes. Some lines in them were not meant for a public
repository. Editing the files was not enough: git keeps every earlier version, and the diff of a
fix still shows the removed lines.

## Decision

Start the public history from one clean root commit that holds the cleaned files, then replay the
later commits on top of it. The commits that only removed private lines were dropped, because
their content is already in the clean root. The final files on every branch are byte for byte
the same as before the rewrite.

The old history is kept only in a local git bundle outside the repository. It is never pushed.

## Alternatives considered

- `git filter-repo` on the two early commits: keeps more history, but the removed lines would
  still appear in the diffs of later fix commits unless each one was rewritten too.
- Leave the history as it is: not acceptable for a public repository.

## Consequences

- History before 2026-11-03 starts at the clean root commit.
- Commit hashes changed; nothing had been pushed, so no one else is affected.
- The public leak-guard scan (FR-024b) also covers the full history from now on.
