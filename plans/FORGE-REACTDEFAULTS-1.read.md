---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-24T08:36:13.366908+00:00
seconds: 413.308
read_hash: 6f8f26882a050689aa65331b372da2ff0fc82d96
round: 1
passed: no
doc_seen: 6f8f26882a050689aa65331b372da2ff0fc82d96
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a16d07-5ccb-75d1-b9ba-7f0a08201f16
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

1. Advisory: Unproven: item 1: the build marker does not prove React Compiler ran.
   Raise: Test  
   Case: normal use - a configuration change disables compilation for production builds.  
   `plans/FORGE-REACTDEFAULTS-1.md:105-107` accepts `react.memo_cache_sentinel` anywhere in the built JavaScript. The pinned React DOM 19.2.0 production runtime already contains that string without compiling app components; React’s [hook implementation](https://github.com/facebook/react/blob/v19.2.0/packages/react-reconciler/src/ReactFiberHooks.js) uses the sentinel itself. A conditional Vite configuration can retain the plugin name checked at lines 112-118 while disabling production compilation, and both checks pass.
   Gain 3, Work 2, Harm 1
   Disposition: keep - below the bar (follow-up)

2. Advisory: Trap: cached crash data prevents the specified recovery flow: item 5.
   Raise: Plan gap  
   Case: normal use - run the planned crash-and-recovery browser flow.  
   `plans/FORGE-REACTDEFAULTS-1.md:205-212` caches a successful response containing `items: null`, then expects removing the interception and clicking Projects to recover. `src/forge/templates/starter/apps/web/src/features/projects/hooks/projects-hooks.ts:30-32` caches that response, and `projects-page.tsx:199` dereferences it. Query [immediately returns cached data on remount](https://tanstack.com/query/latest/docs/framework/react/guides/caching); Projects consequently throws again before committing the subscription that starts its refetch. Removing the interception does not remove the cached payload.
   Gain 3, Work 1, Harm 1
   Disposition: keep - below the bar (follow-up)

3. Advisory: The pagination flow’s expected row contradicts its fixture.
   Raise: Plan gap  
   Case: normal use - run the planned shared-link browser flow.  
   `plans/FORGE-REACTDEFAULTS-1.md:180-184` creates 21 projects through the existing naming loop and expects `Pagination project 19` on page 2. That loop at `src/forge/templates/starter/apps/web/e2e/starter-shell.spec.ts:96-102` numbers from zero. With 21 such projects and ascending Name order, page 2 contains project 20. The existing test’s project-19 expectation depends on its separately created `Migration review` record at lines 83-89.
   Gain 2, Work 1, Harm 4 (floor: migration)
