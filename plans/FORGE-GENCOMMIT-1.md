# Stop committing generated API types in Python apps

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A new Python client app no longer keeps two files in git: the API contract file (the file that lists every server call of the app) and the TypeScript types that a script makes from it. Git ignores both files. The type check and the tests make them first, so a fresh copy of the app works without them. (Source: your decision, 11 Nov 2026: "Stop committing them")
- Parts of different stories that change the API no longer list these two files, so they no longer wait for each other because of them.
- The web build does not make the two files. It does not need them, and the step that builds the web app inside the container has no Python. (Source: the planner's choice; see the open question in Notes)
- A fast test of only an API change now also type-checks the web code against the new API. Today this check runs only because the committed types change together with the API.
- Forge's stack guidance gets one rule for both stacks: a file that a script makes from the app's own code every time stays out of git. Database migrations and lock files are records, so they stay in git. The TypeScript starter already follows this rule, so nothing in it changes.
- An existing Python client app keeps its committed files when it upgrades and syncs. Forge changes no app file, and the app works as today. The guide gives the agent the steps to move the app over in one small fix, and says when to start it.
- The change adds no model call. Model cost: none. Each type check takes a few seconds more, because it makes the two files first (estimate, not measured).

## Why

In a client repo with several developers, every API part of two stories listed the same two files in its scope: the API contract file and the types made from it. Both files were kept in git. Forge does not start two parts that change the same file, so parts of different stories waited for each other. Forge's own guidance caused this: the Python guidance says to commit both files after each API change, and the Python starter ships both files in git.

You decided on 11 Nov 2026 to stop committing them. Not chosen: letting files marked as generated stop counting as shared between parts.

## Done when

1. **A new Python client app does not keep the API contract file or its generated types in git, and Git ignores both. The type check and the tests make them first, also in a fast test of only an API change or only a web change, and the full tests pass on a fresh copy of the app without them.**
2. **Forge's stack guidance says, for both stacks, that a file a script makes from the app's code every time stays out of git, and that migrations and lock files stay in git. The TypeScript starter is checked against this rule and keeps no such file in git.**
3. **An existing Python client app that upgrades and syncs keeps its two committed files, and Forge changes no app file.**
4. **The guide gives the agent the steps to move an existing Python app over in one small fix, and says when to start it. A new repo gets the steps at setup, and an existing repo gets them on sync.**

## Risks

Risks: none one-way. Each part reverts with its pull request. No data changes.

Trade-offs, in plain words:
- A reviewer no longer sees an API change as a change in the contract file. The review still sees the route and schema code that makes the contract, and the type check still fails when a web screen no longer matches the API. Nothing new keeps a copy of the contract to compare against.
- On a fresh copy of the app, the code editor shows the shared API types as missing until someone runs the type check, the tests, or the script that makes the two files. The starter's README says to run that script once after a clone.
- In an existing app, a branch that changed either file gets a merge conflict once the move-over fix merges. The guide says how to settle it: keep the deletion and run the tests.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Rules for every part. No new `forge` command, no new setting, no new dependency, no model call. No screen, page, route table or app shell is added under `src/forge/templates/starter` or `src/forge/templates/starter-python` (review rule, P1). Forge never edits a client's app file: an existing app moves over only through its own fix. Each new test file starts with `STORY = "FORGE-GENCOMMIT-1"`, and the test numbers stay unique across the two files. Tests run the forge command and never import forge. Before a round ends, run the two cheap checks from AGENTS.md.

### What exists (evidence)

Checked in this worktree on 11 Nov 2026 (base `eab58b367`). A part checks each name again before it starts.

- The two files. `src/forge/templates/starter-python/libs/shared/api-types/openapi.json` (about 100 KB) and `.../src/api-types.ts` (about 90 KB) are tracked. The folder also has `package.json` (`@app/shared-api-types`, export condition `@app/source` -> `./src/api-types.ts`) and `tsconfig.json` (`include: src/**/*.ts`). The release `v1.2.36` (commit `9d8defe842c8ecff983a5bc00e60786613840df5`) ships both files.
- How a new app gets them. `init._starter_files` (`src/forge/init.py:202-222`) copies every file under `templates/starter-python` (plus the shared web libraries from `templates/starter`) into the first commit. Deleting the two template files is enough for a new app not to get them.
- The script. Root `package.json` `api-types`: `uv --directory apps/api run python -m app.openapi ../../libs/shared/api-types/openapi.json && openapi-typescript libs/shared/api-types/openapi.json -o libs/shared/api-types/src/api-types.ts`. `apps/api/app/openapi.py` makes its output folder (`mkdir(parents=True)`). `test` runs `api-types` first today; `typecheck` and `build` do not. There is no `dev` script.
- Who reads the types. Only `import type { components } from '@app/shared-api-types'` in `libs/{auth,history,organisations,projects}/contracts/src/index.ts`. Type imports are removed when Vite (`build`) and Vitest (`test:hooks`) compile, so neither reads the files. `tsc --build` reads them, and it fails on a fresh clone without `src/api-types.ts` (TS18003, no inputs). ESLint uses `ts.configs.recommended`, not the type-aware rules, so `lint` does not read them. The Python API makes its OpenAPI at run time and reads neither file.
- The container. `Dockerfile` stage `web-build` is `node:24-bookworm-slim` with no uv or Python, and runs `pnpm install` then `pnpm run build`. So `build` must not call `api-types`, and no `postinstall` may call it.
- The fast test. `scripts/test.mjs` with a base: the `api` branch runs `api-types`, ruff, mypy, `test:imports` and `test:api`; the `web` branch runs ESLint, `tsc --build` over `libs/*/*/tsconfig.json` and `apps/web/tsconfig.json`, Vitest and the browser tests, and never runs `api-types`. `scripts/affected.mjs` marks `apps/api/` as `api` and `apps/web/` or `libs/` as `web`. Today an API change also changes the committed types under `libs/`, so `web` runs too; after this story it does not.
- No drift check exists. Nothing compares the committed files with a fresh copy (searched `src/forge/templates` and `tests` for "up to date", `--exit-code`, "drift").
- `forge feature` (Python, `src/forge/feature.py:220-318`) neither reads nor writes the two files. It adds `libs/<plural>/contracts/tsconfig.json ` before the anchor `apps/web/tsconfig.json` in `typecheck`; a prefix before `tsc` leaves the anchor in place. New feature contracts use `components['schemas'][...]` names that exist only after the types are made again, so `typecheck` making them first helps.
- `forge feature remove` lists files from `git ls-files -co --exclude-standard` (`src/forge/feature_remove.py:127`), so it skips ignored files. That is right for a generated file.
- Sync. `sync.ships` changes `.gitignore` only to add `forge.local.toml` (`src/forge/sync.py:374-381`). It writes no app file.
- Guidance. `src/forge/templates/conventions/python.md:23` (layout line), `:182-184` ("Commit both ..."), `:314` ("The root test script runs api-types before typecheck"). Workers read the conventions from the installed Forge package (`src/forge/worker.py:25`, `:700`; `brief.md:658`), so an existing repo sees the new text as soon as it runs the new release, before any sync. `conventions/stack.md` is the shared stack page; `python.md` says the other pages' rules still apply.
- TypeScript starter. `src/forge/templates/starter/.gitignore` has no generated file. Prisma uses `prisma-client-js` with no `output`, so the client goes to `node_modules`. `build` and `typecheck` both start with `prisma generate`. The OpenAPI spec is made at run time from decorators (`conventions/api.md:103`). There is no `openapi-typescript` and no committed generated file. Migrations are committed on purpose (`conventions/database.md:73`).
- The guide. `src/forge/templates/skill.md` has no line on these files. `## Refresh dependencies` (about line 1449) already uses the pattern "new apps get X; existing apps keep theirs on upgrade and sync; when needed, do these steps". `tests/test_trim_skills.py:21-22` requires `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` to equal the template.
- Tests that read the committed files and break when they go: `tests/test_python_starter.py:143-145`, `tests/test_member_removal.py:24-28`, `tests/test_assistant_historypy.py:25-27`, `tests/test_feature_remove.py:371-373` and `:387-388`. `tests/test_libs_layout.py:240-241` walks the template folder, so it still passes. `tests/test_affected_py_starter.py` still passes (its absent lists do not name `tsc` or `api-types`).
- The end-to-end proof. `.github/workflows/starter-smoke.yml` runs on any pull request that changes `src/forge/templates/**`; `scripts/smoke_select.py:12` runs `tests/test_python_starter.py` and others with `FORGE_STARTER_LIVE=1`, which copies the template tree (now without the two files) and runs the full `node scripts/test.mjs`, Docker image build included.

### Decisions

- Where the files are made. `typecheck` starts with `corepack pnpm run api-types && `. `test` drops its own leading `api-types` call, because `test` runs `typecheck` and nothing before it needs the files; this avoids making them twice. `build` does not change (see the container above). No `pre` scripts: one visible first command is simpler and does not depend on pnpm's pre/post setting. No `postinstall`.
- The fast test. In `scripts/test.mjs`, when `api || web`, run `api-types` once and then the `tsc --build` line (moved out of the `web` branch). The rest of each branch stays. This keeps the check that a web screen still matches a changed API. Score: F 2, H 2 (a broken screen found late), C 1. 4 >= 2.
- Git. Add `libs/shared/api-types/openapi.json` and `libs/shared/api-types/src/api-types.ts` to the starter's `.gitignore`. That nested `.gitignore` also applies inside Forge's own repo, so a local live run that makes the files there does not dirty Forge's tree.
- Lost protection. The contract no longer shows as a diff. The review still reads the route and schema code, and `tsc` still fails on a mismatch. No snapshot, no drift check.
- Windows. The new prefix is the same `&&` chain that `test` already runs through pnpm, and `test.mjs` already spawns with `shell: true` on Windows. No new shell syntax. The live run skips Windows, so Windows stays proven only as much as it is today.
- Existing repos. Forge changes no app file. `forge sync` and `forge doctor` say nothing new: the shared-file note from FORGE-GENFILE-1 already names a file that three or more parts share. Score for a doctor line: F 1, H 2, C 1. 2 >= 2, but it would repeat that note, so it is left out.
- FORGE-GENFILE-1 (approved 11 Nov 2026) advises, at plan read, to make a generated file at build time. This story makes Forge's own Python starter follow that advice. Nothing in FORGE-GENFILE-1 changes.

### Done-when details

1. New Python app.
   - Files: delete the two template files; add both paths to `src/forge/templates/starter-python/.gitignore`; in `package.json`, `typecheck` gets the prefix and `test` loses its own `api-types` call; in `scripts/test.mjs`, `api-types` and `tsc --build` run for `api || web` as above. `README.md` (line 74 area) gets one sentence: the type check and the tests make these types from the API, git does not keep them, and after a clone `corepack pnpm run api-types` makes them once for the editor. `conventions/python.md`: the layout line says the folder holds the package files and that `pnpm run api-types` writes `openapi.json` and `src/api-types.ts` there, not committed; lines 182-184 become: the type check and the tests run `pnpm run api-types` first; Git ignores both files; do not commit them and do not list them in a part's scope; contract libraries import the types through `@app/shared-api-types`; an app made before this release may still commit both files and keeps doing so until it moves over (the Forge guide has the steps). Line 314 says the type check runs api-types first.
   - `test_1` (new file `tests/test_gencommit_starter.py`, `@pytest.mark.platform`): `forge init --starter python` on a new repo. Neither path is in `git ls-files`; `git check-ignore -q` succeeds for both; `scripts["typecheck"]` starts with `corepack pnpm run api-types && `; `scripts["test"]` runs `typecheck` and does not run `api-types` itself; `scripts["build"]` has no `api-types`. With Node present, `node scripts/test.mjs --list <base>` after a change to `apps/api/app/projects/service.py` lists `api-types` before `tsc --build`, and after a change to `apps/web/src/index.css` lists `api-types` before `tsc --build`. The full pass on a fresh copy is the Python starter smoke run (above); the part checks that it passes on its pull request.
   - Changed tests: `tests/test_python_starter.py:143-145` drops the `api-types` order assertion on `test` and the `api-types.ts` file check (the new rule lives in `test_1`). `tests/test_member_removal.py` (Python case) checks the source instead: `apps/api/app/organisations/routes.py` has the `"/{account_id}"` delete route. `tests/test_assistant_historypy.py` checks `apps/api/app/history/schema.py` has the `via_agent` field. `tests/test_feature_remove.py` drops its Python lines that edit and expect `libs/shared/api-types/openapi.json`. Keep each test's audit comment true.
2. Guidance and the TypeScript check.
   - `conventions/stack.md`, after the paragraph on the root `package.json` `test` script: a file that a script makes from the app's code every time (the Prisma client, an API contract and the types made from it) stays out of git. It goes in `.gitignore`, and the build, type check and test scripts that need it run its script first, as `prisma generate` runs first in `build` and `typecheck`. Migrations and lock files are records: commit them. An app that already commits such a file keeps doing so until a fix moves it out.
   - No file in `src/forge/templates/starter` changes.
   - `test_2`, parametrized `typescript` and `earlier adopted`. New: `forge init --starter react` tracks no `openapi*.json`, no file under `node_modules`, and no `*.gen.*` file, and `build` and `typecheck` start with `prisma generate`. The conventions folder found through the worker brief (as `tests/test_python_guide.py:52-55` finds it) has the rule in `stack.md` and the new lines in `python.md`. Earlier adopted: `_adopted_files_after_sync` from `tests/test_mcp.py` gives `after == before`.
3. Existing Python app.
   - `test_3`: build an earlier Python app from the real release tree, as `_copy_earlier_starter` in `tests/test_feature_command.py:215` does: `git archive` of `9d8defe842c8ecff983a5bc00e60786613840df5:src/forge/templates/starter-python` (v1.2.36) over the `tests/fixtures/adopted-v1.2.2/client` fixture, with the version set to the installed one. Commit, then `forge sync` on a fix branch. Both files are byte-identical and still tracked; `.gitignore` gains at most the `forge.local.toml` line; `package.json` and `scripts/test.mjs` are unchanged; no file under `apps/` or `libs/` changed. The CI checkout must have that commit (the existing precedent at `:220` uses a raw commit the same way).
4. Guide steps.
   - `src/forge/templates/skill.md`, in `## Refresh dependencies`, one short paragraph in its existing pattern. New Python starter apps keep the API contract file and its types out of git. Existing apps keep theirs on upgrade and sync. When to start: the first time a plan read names `libs/shared/api-types/openapi.json` or `libs/shared/api-types/src/api-types.ts` as shared, or a part waits on another part because of them, or the owner asks. Start one fix with `forge start` before more API parts, and tell the owner in one line. The steps: `git rm --cached` both files; add both paths to `.gitignore`; start `typecheck` with `corepack pnpm run api-types && ` and drop a separate `api-types` call from `test` when `test` runs `typecheck`; if `scripts/test.mjs` picks parts, run `api-types` before any `tsc` and run `tsc --build` for an API-only change too; remove the two paths from the scope of planned parts; prove it with `git clean -fdX libs/shared/api-types`, then the repo's test command. A branch that changed either file gets a modify/delete conflict when it merges the default branch: keep the deletion (`git rm` both), then run its tests. Copy the result to `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - `test_4` (new file `tests/test_gencommit_guide.py`), parametrized `new` (`forge init`) and `earlier adopted` (`forge sync` on the v1.2.2 fixture). Both hosts' synced `skills/forge/SKILL.md` name both paths, `git rm --cached`, `.gitignore`, the `api-types` prefix on `typecheck`, the plan-read trigger and the conflict step.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| STARTER | The Python starter makes its API types | The two template files removed and ignored; `typecheck` and the fast test make them first; the README sentence; the Python and stack guidance; the tests that read the old files updated; the new, TypeScript and earlier-adopted cases. | 1, 2, 3 | `src/forge/templates/starter-python/libs/shared/api-types/openapi.json`, `src/forge/templates/starter-python/libs/shared/api-types/src/api-types.ts`, `src/forge/templates/starter-python/.gitignore`, `src/forge/templates/starter-python/package.json`, `src/forge/templates/starter-python/scripts/test.mjs`, `src/forge/templates/starter-python/README.md`, `src/forge/templates/conventions/python.md`, `src/forge/templates/conventions/stack.md`, `tests/test_gencommit_starter.py`, `tests/test_python_starter.py`, `tests/test_member_removal.py`, `tests/test_assistant_historypy.py`, `tests/test_feature_remove.py` | `tests/test_gencommit_starter.py` (`test_1`, `test_2`, `test_3`, new); `tests/test_python_starter.py`, `tests/test_member_removal.py`, `tests/test_assistant_historypy.py`, `tests/test_feature_remove.py` (changed) | | no | |
| GUIDE | The guide moves an existing app over | The move-over paragraph with its trigger, steps and conflict step in the shipped guide and both synced copies, with the new and earlier-adopted cases. | 4 | `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `tests/test_gencommit_guide.py` | `tests/test_gencommit_guide.py` (`test_4`, new) | STARTER | no | |

Order. STARTER first: it fixes the script names and the `typecheck` prefix that the guide quotes. GUIDE waits for it so the steps match the starter. STARTER can start at once, because its Scope shares no file with work in flight. GUIDE's files are also in the Scope of FORGE-GENFILE-1/NOTE, which is in progress, and of other parts that edit the guide, so Forge makes GUIDE wait for those parts as well. The column says no for user-facing because no part changes a screen.

New moving parts: none

## Notes

- **Owner decision (11 Nov 2026, settled).** "Stop committing them": the guidance and the Python starter make these files when needed and do not commit them. Not chosen: letting files marked generated stop counting as shared between parts.
- **Open owner questions, recommendation first.**
  1. The web build. You said the files are made at build, type check and test time. Recommended: make them at type check and test time only. The web build does not read them, and the build step inside the container has no Python, so making them there would need Python added to that step. Other option: add Python to that step and make them at build time too.
  2. When an existing Python app moves over. Recommended: the agent starts the small fix the first time a plan read names one of the two files as shared, or a part waits because of them, and tells you in one line. Other options: the agent offers it once after the upgrade and waits for your yes; or only when you ask.
  3. What sync and doctor say about it. Recommended: nothing new. The plan read's shared-file note already names the files when they cause waits. Other option: one doctor line in an existing Python app that still commits them.
- **Scores (F x H >= 2 x C).** The fast test runs `tsc --build` for an API-only change: F 2, H 2, C 1, kept. The guide paragraph: F 2, H 2, C 1, kept. A doctor line: F 1, H 2, C 1, left out (it repeats the plan-read note).
- **Not verified.**
  - That `openapi-typescript` 7.13.0 makes the missing `src` folder when it writes `-o libs/shared/api-types/src/api-types.ts`. If it does not, STARTER makes the folder in the `api-types` script with a cross-platform command (for example `node -e "require('fs').mkdirSync('libs/shared/api-types/src',{recursive:true})"`), not a shell `mkdir -p`.
  - The time that `api-types` adds to each type check: not measured.
  - Generation on a Windows laptop: no test runs the starter on Windows today, and this story adds none.
  - That the `tests` workflow checkout has commit `9d8defe8` for `test_3` (the existing raw-commit precedent suggests it does).
