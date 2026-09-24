---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-24
stories: []
---

# One human approval per story

## Context

Planning four stories took the owner through more than a dozen native approvals: every task plan,
every story-plan amendment (even a changed task order or count) and every re-recorded grill asked
again, often for text the owner had already approved. That keeps the developer in the loop for
bookkeeping, which is the opposite of what Forge is for: the agent should drive and ask only what
needs a human.

## Decision

A human approves a story's plan once, in native Plan Mode. Everything below it is the agent's to
record, with reasons, and is shown in the PR:

- Task plans get their one Codex cold read and no human approval; the story approval covers them.
- A later change to the story plan comes back to the human only when it changes what the story
  delivers: its "What changes for you" or "Done when" sections. Changes to task order, task count,
  dependencies, wording elsewhere or the technical approach are recorded by the agent with a reason.
- A task grill stays valid when files outside the task's write scope change; only a change to the
  task's own contract, its plan or files inside its scope makes it stale.

## Consequences

- One approval per story; task work starts as soon as its cold read is recorded.
- The human still sees every change in the PR and can overrule it there.
- Supersedes the task-plan approval requirement and the re-approval of unchanged or
  delivery-preserving story-plan amendments in earlier decisions.
