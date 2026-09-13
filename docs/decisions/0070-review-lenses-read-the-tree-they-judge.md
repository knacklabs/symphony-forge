---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-13)"
date: 2026-09-13
stories: []
---

# Review lenses read the tree they judge

## Context

The autoreview skill starts its engine in an empty temporary folder and tells
it so: "the review sandbox is intentionally empty ... read-only tools cannot
access unchanged repository files". The engine's read-only sandbox enforces
it. A probe on 2026-09-13 handed the reviewer a two-file repository whose
diff touched only the caller and asked it to open the callee before any
verdict. It tried, was refused ("CreateProcess rejected access ... blocked by
policy"), and wrote `VERDICT C1: missing` for a contract the callee satisfied.

That is the shape of WF-1 T5's review loop. Eleven of the first twenty-five
blocking findings were claims about unchanged code the reviewer could not
open (`request()` already threw on a non-2xx; the write DTOs accepted no
`siteId`). Contract C16 came back `partial` in five consecutive rounds, each
time citing a different file, because the reviewer could see only the file
the last fix touched and had to guess about the other six. Forge's own lens
preamble made it worse: "you see ONLY the diff bundle ... say so when
something cannot be verified from it", and the recorder turns every such
`partial` into a blocking finding.

The owner's requirement: the same process that raises a partial must be able
to read the repository, read-only, and give a yes or a no -- never a maybe.

## Decision

Each review lens runs inside the reviewed worktree, read-only. `forge review`
writes a small launcher beside the worktree and hands it to the skill as its
Codex binary; the launcher replaces the skill's empty working folder with the
review worktree and starts the real Codex otherwise unchanged. The sandbox
stays read-only: the skill passes no sandbox flag and ignores user
configuration, so `codex exec` keeps its read-only default, and the worktree
is a fresh detached checkout with no ignored files in it.

The lens brief changes accordingly. The diff is the subject and is judged
first. When a verdict or a finding depends on code the diff does not show,
the reviewer opens it and cites the line it read. "Cannot verify from the
diff" is not a verdict; a partial or missing verdict names the failing line.
Reading is for resolving, not roaming: no finding on code the diff neither
touches nor calls.

On Windows the launcher does two more things, both learned from probes on
2026-09-13. The skill's `--ignore-user-config` drops `[windows] sandbox =
"elevated"`, and without that sandbox Codex refuses every command in
read-only mode ("blocked by policy" for `Get-Location` itself); the launcher
carries that one key through as a `-c` override. The skill also hands the
engine a fresh runtime `CODEX_HOME`, while the elevated sandbox keeps its
set-up state under the user's real one (`.sandbox`, `.sandbox-bin`,
`.sandbox-secrets`); without it Codex re-runs set-up and its UAC prompt is
cancelled (error 1223). The launcher points the engine back at the home that
holds the state; configuration stays ignored and the auth file is the same
one the skill hard-linked. With both in place the probe printed its working
folder, listed the files, read the callee, was denied a write, and returned
`implemented` with the callee's line where it had returned `missing`.

When the tree cannot be offered -- another engine, `codex` not on PATH, or
`FORGE_REVIEW_EMPTY_WORKSPACE=1` -- the run says so, and the fallback brief
tells the reviewer that what it cannot see is not thereby partial.

## Consequences

- A partial verdict is a read line, so it cannot wander from file to file
  across rounds, and a wrong one is refuted by the reviewer itself.
- The host's triage (0069) verifies rather than discovers: the reviewer's
  evidence is already a line in the repository.
- Cost: a lens that hits a partial reads more, so minutes and tokens per such
  lens; a clean review costs nothing extra.
- The skill's own prompt still describes an empty sandbox; the brief says
  that note does not apply. An upstream flag that runs the engine in the
  repository would retire the launcher, and is the right ask.
