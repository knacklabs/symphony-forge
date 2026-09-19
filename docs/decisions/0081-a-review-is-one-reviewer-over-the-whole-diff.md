---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-18)"
date: 2026-09-18
stories: []
---

# A review is one reviewer over the whole diff, never file groups

## Context

Decision 0078 dealt a diff too big for one prompt into parallel file groups,
each reviewed alone with the whole tree readable, and merged the results. It
was built for WF-1A T1's 900 KB diff. On WF-BIO-1 T4 (2026-09-18) the review
brief itself had grown to 472 KB of the tool's 480 KB limit, so the capacity
the planner had left for the diff was a few kilobytes, and the same 187 KB
diff that had been seven groups at 11:22 became forty-nine and fifty one-file
groups in every later review. A reviewer holding one file and none of its
tests cannot prove a contract, so it reported the contracts "partial": eight
invented blockers on code that had passed with none an hour earlier, then
seven, six and five more, each refused by hand with a cited line. A single
lens run skipped the split entirely, so the same code was judged with full
context under one command and one-file context under another.

## Decision

A review is one reviewer over the whole diff with the whole tree readable
(0076). The harness measures the prompt it is about to send (brief, prompt
text, diff bytes per path) and prints the composition on every run. A prompt
over the tool's limit is never dealt into groups and, since 2026-09-19,
never refused either: the harness reviews the diff in passes over the whole
task. Every pass reads the same brief, contracts and journal; only the diff
bytes are split, into contiguous slices in git's order, and the other
passes' paths sit at the task base in that pass's checkout; a pass judges findings on what it holds and gives verdicts only
for contracts bound (`lands_in`, 0082) to files it holds or bound to none;
the passes merge into one generation with one stamp, worst verdict wins. A
warning names the pass count and the largest paths, because a diff that
size is usually two tasks. The one refusal left is a single path that does
not fit a pass by itself: generated content for the noise list. Lock and generated
files are still put back to the task base in the review tip (0078); they ship
and stay in scope, their bytes are not sent.

## Consequences

- One Codex run per review, every finding and verdict from a reviewer that
  saw the file and its tests together.
- The group machinery (synthetic group commits, per-group launchers, retry
  briefs, the chunk-shape merge) is removed; the tool's own set-aside of a
  finding located outside the diff is still validated and counted, because a
  verdict read from the tree (0076) lands there.
- A task whose diff alone exceeds the limit is over budget by the harness's
  own policy and is refused with numbers instead of reviewed badly.
- `FORGE_REVIEW_PROMPT_BYTES` lowers the limit for tests and probes.
