---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-27T08:01:17.752797+00:00
seconds: 74.125
read_hash: 343994768d014cd897878c9caae9a8ae56b8ba9d
round: 2
passed: yes
doc_seen: 343994768d014cd897878c9caae9a8ae56b8ba9d
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: b25a6c746c11dd936d64f0a35b0c7e02b46b2cf1
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a17c4f-e5f6-7313-a587-ff60725a95c0
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

1. Blocking: Trap: the Python SDK client does not open the proposed stateless notice stream.
   Raise: Plan gap.
   Case: normal use - a Python agent connects, subscribes and waits for an item change.
   [The plan](/plans/FORGE-MCPRES-1.md:160) requires stateless transport and its SDK client for the notice test at line 248. The [Python SDK’s `handle_get_stream`](https://github.com/modelcontextprotocol/python-sdk/blob/v1.26.0/src/mcp/client/streamable_http.py#L226-L239) returns immediately without a session ID. A notification handler alone cannot establish this stream; the specified client path receives no notices.
   Gain 5, Work 3, Harm 3
   Disposition: cut: notices removed by owner decision.

2. Blocking: The no-prompts source check rejects the required prompt test.
   Raise: Test.
   Case: normal use - the builder implements the prescribed prompt registration test.
   [Lines 255–265](/plans/FORGE-MCPRES-1.md:255) require a unit test that calls `definePrompt`, then forbid `definePrompt(` anywhere under `libs/` or `apps/` except `prompts.ts`. The required `tools.test.ts` lives under `libs/`; Python’s `test_tools.py` lives under `apps/`. Ordinary implementations of those tests fail the source check.
   Gain 4, Work 1, Harm 1
   Disposition: cut: the no-prompts source check excludes test files (tests may call definePrompt).

3. Blocking: Unproven: item 2 does not test delete or restore notices.
   Raise: Test.
   Case: normal use - a person deletes or restores an item that an agent subscribed to.
   [The notice case](/plans/FORGE-MCPRES-1.md:242) exercises only updates. Delete and restore have separate transaction paths in [TypeScript](/src/forge/templates/starter/libs/projects/server/src/projects.service.ts:261) and [Python](/src/forge/templates/starter-python/apps/api/app/projects/service.py:311). Omitting both notice hooks would pass every prescribed notice assertion while leaving an explicit part of item 2 unmet.
   Gain 3, Work 2, Harm 3
   Disposition: cut: no notices, so no delete/restore notice tests.

4. Blocking: Unproven: item 1’s contract cannot detect missing resources for a generated feature.
   Raise: Test.
   Case: normal use - the feature command adds jobs, but jobs exposes no resources.
   [Lines 225–229](/plans/FORGE-MCPRES-1.md:225) check only resources already returned by the server. An omitted feature contributes nothing to inspect. The explicit address assertions cover projects alone. Furthermore, the prescribed [live runner](/tests/test_starter_tree.py:303) copies the starter without generating another feature. A projects-only implementation passes these checks.
   Gain 3, Work 2, Harm 3
   Disposition: cut: the contract builds the expected list of features from the tools list (each <feature>_search tool) and fails when any feature has no resources; the live feature run covers a generated feature, not only projects.

5. Advisory: The field-guide rule includes the tool’s response-format option as a feature field.
   Raise: Functional.
   Case: normal use - an agent reads the projects field guide before creating a project.
   [Lines 135–140](/plans/FORGE-MCPRES-1.md:135) derive fields and choice lists from the create tool’s input schema, excluding only `idempotency_key`. The prerequisite [tool contract](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-MCP-1/plans/FORGE-MCP-1.md:241) also adds `response_format`. Following both rules advertises `response_format` as a project field and creates an allowed-value resource for it.
   Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

6. Advisory: Split: RES and RESPY → resources/notices and prompts.
   Raise: Plan gap.
   Case: normal use - either starter implementation proceeds through its assigned task.
   [Both task scopes](/plans/FORGE-MCPRES-1.md:327) combine two new core modules, resource and prompt handlers, stream lifecycle, subscription state, transaction hooks, app tests and Forge tests. That scope suggests substantially more than the roughly 400 changed lines permitted per task. Prompts provide a distinct split from resources and notices.
   Gain 3, Work 2, Harm 1
   Disposition: keep - below the bar (follow-up)

## Round 2

No findings.
