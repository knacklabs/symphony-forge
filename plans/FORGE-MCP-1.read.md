---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-27T06:14:01.658795+00:00
seconds: 624.963
read_hash: b13d7fc46c4f70a9fe2e3568a01f57a67e803482
round: 1
passed: no
doc_seen: b13d7fc46c4f70a9fe2e3568a01f57a67e803482
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a17bf5-04de-71a2-8d5b-5bd92531ad78
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

1. Blocking: The older-starter fallback still copies dependencies that the older app does not have.
   Raise: Functional.
   Case: normal use - a developer upgrades Forge and generates a feature in an app made before MCP support.
   The [fallback](/plans/FORGE-MCP-1.md:441) removes the tools file and module wiring, but still copies the Agent access component and MCP tests. A real older app lacks that component, the agent routes and `agentClient`. The renderer copies tests from the installed starter ([feature_api.py:481](/src/forge/feature_api.py:481)). The proposed current-starter-minus-MCP fixture retains these newer dependencies, so it misses the broken build and test run.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the fallback now leaves out every MCP file, the Agent access dialog line and the MCP cases and flow, and the older-starter case checks the copy names none of them.

2. Blocking: The required tool-list assertions fail as soon as another feature exists.
   Raise: Test.
   Case: normal use - the feature live run adds clients and jobs alongside projects.
   The [projects cases](/plans/FORGE-MCP-1.md:425) require exactly four projects tools, and four or six tools for an admin. The same plan requires copying those cases to every generated feature. The registry contains all features’ permitted tools, so these assertions reject a correct multi-feature app. The API runner collects every feature suite ([vitest.config.ts:7](/src/forge/templates/starter/apps/api/vitest.config.ts:7)).
   Gain 4, Work 2, Harm 3
   Disposition: cut - the cases now check only the tools that start with the feature's own prefix.

3. Blocking: The contract test rejects truthful annotations on hand-written tools.
   Raise: Plan gap.
   Case: normal use - a developer adds a read-only `projects_count` tool with the projects view permission.
   The [hand-written interface](/plans/FORGE-MCP-1.md:217) accepts custom verbs and explicit annotations. However, the [all-tools contract](/plans/FORGE-MCP-1.md:479) permits `readOnlyHint: true` only for search and get, and `destructiveHint: true` only for delete. A custom read-only or destructive action must therefore fail the test or publish inaccurate hints.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the contract checks the expected hint values only on the six generated tools; a hand-written tool is checked for a title and four true-or-false hints.

4. Advisory: The documented timeout retry can create a second item.
   Raise: Not done.
   Case: normal use - a create remains blocked for twenty seconds and the agent follows the returned retry instruction.
   The [timeout rule](/plans/FORGE-MCP-1.md:308) returns after ten seconds without stopping work; the error instructs a retry after five seconds. The [idempotency algorithm](/plans/FORGE-MCP-1.md:295) stores the key only after creation, so that retry finds no entry and starts another create. The current service commits creation independently ([projects.service.ts:213](/src/forge/templates/starter/libs/projects/server/src/projects.service.ts:213)). This contradicts the explicit promise that a retry after a timeout makes one item; the sequential retry test cannot detect it.
   Gain 4, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

5. Advisory: A full replacement does not make the TypeScript update a no-op on retry.
   Raise: Not done.
   Case: normal use - an agent repeats an unchanged update.
   The [retry rule](/plans/FORGE-MCP-1.md:303) says the second update changes nothing. The existing [update implementation](/src/forge/templates/starter/libs/projects/server/src/projects.service.ts:234) always writes before checking whether fields changed. Its database trigger advances `updatedAtUtc`, changing the returned result and search ordering. No planned case repeats an update and checks this guarantee.
   Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

6. Advisory: Split: AGENTS, TOOLS and TOOLSPY each exceed the intended task size.
   Raise: Plan gap.
   Case: normal use - builders implement the complete scopes in the task table.
   The [scopes](/plans/FORGE-MCP-1.md:588) bundle two account APIs and several dialogs into AGENTS, and a tool engine, transport, persistence and generation changes into each tools task. These exceed roughly 400 production lines independently of regenerated artifacts. The [size note](/plans/FORGE-MCP-1.md:618) supplies no recorded allowance for that production work. The concrete splits are account APIs versus screens for AGENTS, and tool rules versus transport and generation for TOOLS and TOOLSPY.
   Gain 3, Work 3, Harm 2
   Disposition: keep - below the bar (follow-up)
