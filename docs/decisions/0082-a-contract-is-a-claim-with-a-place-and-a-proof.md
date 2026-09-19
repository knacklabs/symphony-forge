---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-19)"
date: 2026-09-19
stories: []
---

# A contract is a claim with a place and a proof

## Context

WF-BIO-1 T5's nine contracts were paragraphs of 600 to 2,100 characters,
three to fourteen sentences, up to six files named. Three cold reviews
returned only "partial" verdicts on them, seven, then five, then seven, and
two contracts flipped back to partial after fixes had touched them. No real
defect was found in three rounds. A reviewer can always find a sentence of a
paragraph to call unmet, so verdicts diverged instead of converging.

## Decision

A plan contract is one checkable claim. Its `statement` is a single
sentence; `lands_in` names the repo-relative file the claim lands in; `proof`
names the required test that fails while the claim is unmet. Guidance about
how to build it belongs in the task objective or the plan. The recorder
requires `proof` to name one of the task's required tests; the task grill
flags a contract that bundles claims or binds no proof.

The proof run answers each bound claim: `verify.json` records the claim and
its test's status. The reviewer is told which claims are proven and judges
only whether the test proves the claim; a partial or missing verdict on a
proven claim that cites no line in that test is set aside, never a finding.

## Consequences

- "Partial" means the test proves less than the sentence says, at a line the
  reviewer read, or it does not exist.
- Existing contracts without `proof` keep today's behaviour: the reviewer
  verdicts them; the grill asks for the split at the next re-grill.
- A contract's identity stays `id`; the new fields change nothing for the
  review stamp, the launch or the seal.
