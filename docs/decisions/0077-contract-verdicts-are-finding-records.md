---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-15)"
date: 2026-09-15
stories: []
---

# Contract verdicts are finding records, not lines in the summary

## Context

The combined review (0069) has the reviewer write one string,
`overall_explanation`, that must hold the quality, performance and security
assessments between six marker lines and, inside the quality assessment, one
`VERDICT <contract>: implemented|partial|missing — file:line` line per plan
contract. The autoreview helper caps that string at 3,000 characters in the
schema it hands Codex, and every chunk of a large diff must write all of it
again.

On WF-1A T1 (2026-09-14) pass 1 of four came out at 3,027 characters. The
text was cut mid-word inside the security assessment, before its end marker,
and the recorder refused the hour-long run; its findings existed only in the
log. Only the verdict lines grow with the plan: sixteen contracts cost about
1,900 characters of a 3,000-character box before a word of assessment is
written. Raising the cap is not ours to do and would move the cliff, not
remove it.

## Decision

A contract verdict is a finding record. For every plan contract the reviewer
adds one finding titled exactly `[quality] VERDICT <contract-id>:
implemented|partial|missing`, with the file and line it read and one sentence
of evidence in the body, and that location as `code_location`. A record has
its own 2,000-character body and a pass may carry any number of them.

`overall_explanation` holds only the three assessments and their markers; its
required size is now constant. When forge projects the helper's output into
lens artifacts it lifts every verdict record out of the findings stream into
`contract_verdicts`, the same field and shape as before, and never counts a
record as a blocking or non-blocking finding whatever priority it carries. A
verdict record under any tag but `[quality]` refuses the run.

A `VERDICT` line still written inside the quality assessment keeps parsing, so
a generation recorded before this change reads unchanged, and a reviewer that
writes both is judged by the worst verdict, as across chunks. A contract with
neither a record nor a line stays `partial`, fail-closed, as before.

## Consequences

- The reviewer's box no longer depends on how many contracts a task has; the
  overflow that refused WF-1A's review cannot recur from verdict volume.
- Evidence gets more room, a body per contract instead of a share of one box.
- Closeout, the board, the fix brief and rejection read `contract_verdicts`
  exactly as before; the raw helper output is stored verbatim in the
  generation, so the original records are always recoverable.
- The single-lens diagnostic run (`forge review --lens`) keeps the line form;
  it is not the recorded proof.
- Not addressed here: re-running one failed chunk instead of the whole review
  needs the helper to expose per-pass results, an upstream change.
