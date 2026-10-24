---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-24T06:03:24.152983+00:00
seconds: 493.488
read_hash: 6851ff0ab404f71f5275b7ea695e246b48c2766b
round: 1
passed: no
doc_seen: 6851ff0ab404f71f5275b7ea695e246b48c2766b
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a16c7a-37ba-7450-b7e5-474b847b8477
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

1. Blocking: Trap: item 1's nested commands still require a pnpm shim on the host.
   Raise: Plan gap
   Case: normal use - a developer runs the starter tests with Node 24 and Docker, without previously enabling Corepack's shims.
   `plans/FORGE-MODULAR-1.md:134` requires bare `pnpm run` commands inside package scripts, while lines 135–136 wrap only their outer invocation with Corepack. The current nested test command is at `src/forge/templates/starter/package.json:15`. Calling `corepack pnpm` does not install the PATH shim; [Corepack documents that as a separate operation](https://github.com/nodejs/corepack#corepack-enable--name). Consequently, the outer command starts, but its nested `pnpm run lint` fails with `pnpm: not found`. Only the Dockerfile explicitly enables the shims.
   Gain 4, Work 2, Harm 2
   Disposition: cut Item 1 now has every pnpm call, including root scripts that run other scripts, use `corepack pnpm`, so no shim or new set-up step is needed.

2. Blocking: Trap: item 2's upward-import test creates a circular dependency before testing its tag constraint.
   Raise: Test
   Case: normal use - the live smoke workflow runs the planned negative lint case.
   `plans/FORGE-MODULAR-1.md:192` adds `core → projects` and requires output containing `type:core`. Projects already depends on `PrismaService` (`src/forge/templates/starter/apps/api/src/projects/projects.service.ts:3`), which the plan places in core at line 93. This produces `core → projects → core`, with circular checks explicitly enabled at line 109. [Nx's rule reports circularity and returns before checking tag constraints](https://github.com/nrwl/nx/blob/master/packages/eslint-plugin/src/rules/enforce-module-boundaries.ts). The planned assertion therefore expects a tag diagnostic from a case intercepted by another check.
   Gain 4, Work 2, Harm 1
   Disposition: cut The negative case is now the web app importing `@app/projects`, which makes no cycle, so the test expects the `type:web` tag diagnostic; Done-when 2 says the same.
