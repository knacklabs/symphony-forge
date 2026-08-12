---
slug: rescue-prompt-file
title: Read-only rescue accepts long prompts via prompt-file
status: confirmed
saved: 2026-08-12T15:20:42+00:00
---

# Read-only rescue accepts long prompts via prompt-file

> Captured 2026-08-12, clearing the spec debt on adhoc story FORGE-ROLE-2:
> the guard allowlist gap was found dogfooding FORGE-WIN-1 exploration —
> heredoc-wrapped long prompts are correctly refused, but the clean
> file-based route is not admitted either.

## Why

The role split routes all Codex writes through `./forge delegate`, while
allowlisted direct read-only status/resume/task calls pass the companion
guard. A real exploration brief is multi-paragraph; inline argv prompts
don't carry it, and shell heredoc wrapping is (rightly) refused as
shell-shaped. With no admitted file route, the anytime contract — a
read-only rescue is always available — holds only for short prompts,
which is exactly when rescue is least needed.

## Behaviour

- The companion guard allowlists `--prompt-file <path>` on READ-ONLY task
  invocations: the file's content is data, not argv, so prompt length and
  shape stop mattering to the guard.
- Write invocations are unchanged: they still route exclusively through
  `./forge delegate`, which already composes its own brief file.
- The read-only rescue route (`/codex:rescue`) can hand a long brief to
  the companion through a file with no shell wrapping.
- Refusals stay strict for everything else: shell metacharacters, heredocs,
  and write-shaped argv are refused exactly as today.

## Acceptance criteria

- The companion guard admits a read-only task invocation carrying
  `--prompt-file` and refuses the same flag on a write-shaped invocation
  outside `forge delegate`.
- A multi-paragraph brief reaches Codex through the file route,
  live-verified end to end.
- Heredoc/inline-shell prompt wrapping remains refused (regression).
- Existing guard behavior for status/resume/short inline task calls is
  unchanged (existing suite green).

## Non-goals

- No change to the write path or to delegate's brief composition.
- No new prompt-composition machinery beyond writing the brief file the
  guard admits.
