Never ask whether a problem needs a separate fix: a problem outside your Done-when is a `Spotted:`
line. Never ask to record a narrow choice: fix only the review findings inside your Done-when, and
list each other finding in the `Proof list:` as `Outside Done-when: <finding> - <why>`.

## Before you hand over

The review blocks on these. Check each against your committed work before your last message:
- Every Done-when item you cover works, proven by its test or check; an item that changes
  runtime behaviour has an end-to-end test through the real entry point.
- Each new test fails without your change, and no test was weakened or deleted to pass.
- The `Proof list:` names every Done-when item you cover with its test or check, or `missing`.
- No new dependency, service, datastore, queue, background job or abstraction layer that the plan
  doesn't name, and nothing simpler would do.
- Validation, security, data-loss protection and accessibility hold, and so do the Standards.
- The repo's own rules under `## Review rules` in its AGENTS.md hold.
- Each file outside Scope is one the change needs, named in your handoff.
- Everything is committed.
