---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-28T10:56:36.657635+00:00
seconds: 168.482
read_hash: 4ff3c3cec08857ab2a2efb7065f159fd8e7d0e83
round: 3
passed: no
doc_seen: 4ff3c3cec08857ab2a2efb7065f159fd8e7d0e83
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 3d69d160bdc2aac3f58632ce6ae57fe00029e5f8
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a181dc-b601-7d53-adb9-493ff97efc15
session:
loop_choice: more
loop_reason: The owner chose one more round: add a web test for the invite hook's retry key
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

1. Blocking: Plan gap: neither starter permits the new header through CORS.
   Raise: Functional. The TypeScript allowlist (`src/forge/templates/starter/apps/api/src/main.ts:20`) and Python allowlist (`src/forge/templates/starter-python/apps/api/app/core/security.py:169`) omit `Idempotency-Key`. Neither file is in Scope. The planned direct API and mocked-fetch cases bypass browser preflight, so they cannot catch this failure.
   Case: normal use - a browser on the configured permitted origin calls the API across origins with the documented retry header; the browser blocks the create.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the doc now adds the header to both CORS allowlists, puts both files in Scope, and adds a preflight step to both app cases.

2. Blocking: Plan gap: the new retry test needs explicit handling for older starters.
   Raise: Plan gap. `plans/FORGE-AGENTREADY-1.md:81` places the case outside the blocks replaced during feature generation. `src/forge/feature_api.py:535-554` copies that remaining text into generated tests. The plan marks controller additions for removal, but specifies no corresponding handling for this test. An older app therefore receives retry assertions for a handler intentionally generated without retry support. The planned older-starter check only generates and inspects files.
   Case: normal use - add a feature to an older starter and run its generated tests.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the TypeScript retry case now sits between the retry-key marks, so an older app's copy drops it; test_3 checks the generated e2e spec in both cases. Python's generated tests copy only marked blocks, so they need no change.

3. Blocking: Unproven: item 3 does not preserve the shared action name for hyphenated TypeScript features.
   Raise: Test. The pinned `'projects_create'` literal passes through `_renamed_source` (`src/forge/feature_api.py:422-435`), which turns it into `'workOrders_create'` for `work-orders`. MCP instead uses `'work_orders_create'` (`src/forge/templates/starter/libs/core/server/src/common/tools.ts:115-137,252`). This contradicts the shared snake-case key space promised at `plans/FORGE-AGENTREADY-1.md:65`. The specified `jobs` assertion cannot detect the mismatch.
   Case: normal use - generate a feature with a supported hyphenated name; its REST and MCP creates use different retry namespaces.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the doc pins the action name as the plural in snake form, adds one fix-up line to the TypeScript feature copy, and test_3 adds a work-orders feature case.

4. Blocking: Not done: the pinned TypeScript validator cannot produce the promised header error field.
   Raise: Plan gap. `plans/FORGE-AGENTREADY-1.md:68` requires validating the scalar header with `retryKeySchema.optional()` through `ZodValidationPipe`. That pipe labels root-level failures `body` (`src/forge/templates/starter/libs/core/server/src/common/zod-validation.pipe.ts:11-14`). The required case at plan line 84 expects `Idempotency-Key`, and Scope includes no pipe change. The implementation instructions and required assertion therefore disagree.
   Case: normal use - an API caller sends the explicitly covered 201-character key.
   Gain 3, Work 2, Harm 2
   Disposition: cut - ZodValidationPipe gets an optional root field name (default body), the header check passes Idempotency-Key, and the pipe file is in Scope. Python already names the header alias.

## Round 2

No findings.

## Round 3

5. Advisory: Unproven: item 1’s invite hook has no retry-lifecycle coverage.
   Raise: Test. `plans/FORGE-AGENTREADY-1.md:80` relies on the projects hook’s test, but that test imports only project hooks (`src/forge/templates/starter/libs/projects/web/src/hooks/projects-hooks.test.tsx:4`). `useInvite` is a separate implementation (`src/forge/templates/starter/libs/organisations/web/src/hooks/members-hooks.ts:39`). Omitting its header or generating a new key on every attempt would pass the planned API tests, which supply keys themselves, and the existing browser invite case, which never retries a failed response.
   Case: normal use - an invite succeeds but its response is lost; retrying from the dialog sends another email because the hook supplies no stable key.
   Gain 3, Work 2, Harm 3
