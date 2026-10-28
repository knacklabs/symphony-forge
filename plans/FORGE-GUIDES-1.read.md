---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-28T12:26:38.187121+00:00
seconds: 436.023
read_hash: 77e0109d88284039b19d5e78885c6f5c47851feb
round: 1
passed: no
doc_seen: 77e0109d88284039b19d5e78885c6f5c47851feb
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a18273-6557-7180-9e9c-b5797855179c
session:
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Unproven: item 4’s upgrade test has no existing Dockerfile or package manifest to preserve.
   Raise: Test.
   Case: normal use - upgrading an existing app with its own Dockerfile and dependencies.
   `plans/FORGE-GUIDES-1.md:43,168` prescribe the setup from `tests/test_mcp_resources_guide.py:21`. That fixture contains only Forge files; `tests/conftest.py:521` adds a README, but no Dockerfile, package manifest or lockfile. Reading the promised files fails; checking that they remain absent cannot catch sync overwriting existing app files. Seed representative app files before upgrading, then compare their bytes afterward.
   Gain 3, Work 2, Harm 3
   Disposition: cut - item 4's existing-repo test now seeds a root-user Dockerfile, a README, a package.json with Prettier and its lockfile entry before the upgrade commit, and compares each file's bytes after sync; item 1's adopted package check moves to that test.

2. Advisory: The outgoing-call examples skip the failure logging their rule requires.
   Raise: Functional.
   Case: normal use - a vendor call times out or fails to connect.
   `plans/FORGE-GUIDES-1.md:85` requires every call’s duration and outcome, but both pinned examples at lines 87–102 log only after the request returns. Exceptions bypass those logs; [HTTPX documents timeout exceptions](https://www.python-httpx.org/advanced/timeouts/). The checks at line 161 only require timeout and header text, so they pass with this contradiction. Include failure-duration logging in the examples.
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)
