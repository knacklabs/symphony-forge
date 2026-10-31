# Starter ships no screens

4 parts · Risks: none one-way · New moving parts: none

## What changes for you

- New client apps from `forge init` get the API, the rules, the skills and the guide, with no sign-in, Members, Projects, Change history, Join or app shell screens, in both the React and Python starters. They also keep the web build setup that carries no screen: the build and test configuration, the theme file, the shadcn components and the API client. (Source: your decision, 31 Oct 2026: "We only save the important characteristics and best practices to build with forge, not the actual screens"; keeping the build setup is the planner's choice, see Notes)
- Each client's agent builds every screen in that client's own design. Every API that a person uses gets its screen, built by the agent when it builds the API, with no need to ask. APIs that only machines call (webhooks, endpoints for agents or other systems, background jobs) get no screen. (Source: your decision, 31 Oct 2026)
- The basic screens every app needs (sign-in, members, settings) are built at the start of the prototype, in the client's design. They replace the starter screens that this story removes. (Source: your decision, 31 Oct 2026)
- `forge task feature` builds a feature's API, agent tools, change history and tests. It writes no pages any more; the agent builds the feature's screens in the client's design. (Needed by: the removal of the starter screens, because the command copies the Projects pages)
- Forge's review reports a person-facing API that has no screen, in a client repo that has a web app. In Forge's own repo, the review reports any new screen in Forge's templates. (Source: your decision, 31 Oct 2026)
- A client repo that already exists keeps all its app code when it upgrades. It gets the new guide text and review rule with `forge sync`. (Source: the Forge review rules)

Design: none (this story removes screens and adds none; each client app's own design covers every screen)

## Why

Each client app has its own design. The starter's screens fit none of them, so the client's agent must remove or rebuild them before the real design can start. Forge should keep only what holds for every app: the API, the rules and the skills.

## Done when

1. **A new app from `forge init`, with either starter, has no screen files. Its API tests pass, the built app still serves its page, and the starter smoke run is green.**
2. **`forge task feature` builds a feature's API, tools, history and tests and writes no page, in both starters and in an app from an earlier release.**
3. **An existing client repo's app files do not change after upgrade and `forge sync`.**
4. **The guide and the app-baseline skill say: every person-facing API gets its screen in the client's design, built by the agent with the API; machine-only APIs get none; sign-in, members and settings are built first in the prototype. A new repo gets this at init and an existing repo with `forge sync`.**
5. **The review of a client repo that has a web app reports a person-facing API added with no screen, on a new repo and on an existing repo.**
6. **Forge's own `AGENTS.md` review rules tell the review to report a new screen in Forge's templates.**

## Risks

Risks: none one-way. Each part reverts with its pull request.

Trade-off: a new app has no screen to click until the agent builds the first ones, so the prototype's first step is longer. This is what you chose. A story that was planned against the removed Members or Projects screens needs its plan checked (see Notes).

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-NOSCREENS-1"`. Tests run the forge command and never import forge. One test per rule. For app behaviour they name the cases the app's own run reports, through `live_run` (`tests/test_starter_tree.py`), `live_python_starter` (`tests/test_python_starter.py`) and `_require_cases` (`tests/test_mcp.py`). Live tests carry `@pytest.mark.platform` and `@pytest.mark.timeout(1800)`. The existing-repo case uses `_adopted_files_after_sync` from `tests/test_mcp.py`. Pure deletions are large; a part that passes the 400-line limit only through deleted files records `forge fix allow-large "<reason>"`.

TS means `src/forge/templates/starter`, PY means `src/forge/templates/starter-python`. PY's web side is copied from TS at init (`src/forge/init.py::_starter_files` copies `apps/web`, `libs/shared/ui`, `libs/shared/util` and every `libs/*/web`), so one web change serves both.

### What exists (evidence)

- Web files today (TS): `apps/web/src/{app.tsx,main.tsx,index.css,components/app-shell.tsx,pages/not-found-page.tsx,pages/settings-page.tsx}`, `apps/web/e2e/*.spec.ts` (11 specs and `helpers.ts`), `apps/web/{index.html,package.json,project.json,tsconfig.json,vite.config.ts,vitest.config.ts,vitest.setup.ts,playwright.config.ts}`; screens and hooks in `libs/{auth,history,organisations,projects}/web/src`; `libs/core/web/src` (`api-client.ts`, `error-report.ts`, `form-errors.ts`, `permissions.ts`, `query-client.ts`, plus the screen parts `route-error-page.tsx` and `agent-access-dialog.tsx`); `libs/shared/ui/src` (shadcn components, `theme-provider.tsx`, and the screen part `components/auth-page-frame.tsx`).
- Who reads them:
  - `src/forge/init.py::_starter_files` copies the web files into a Python app. No change needed: it globs `libs/*/web`.
  - TS `Dockerfile` runs `pnpm run build` (`nx run-many -t build`); PY `Dockerfile` has a `web-build` stage that runs `vite build`; TS `apps/api/src/main.ts` and PY `app/main.py` serve `apps/web/dist` with a fallback to `index.html`; `scripts/test.mjs` and PY `scripts/test-browser.mjs` run `test:hooks` and `test:browser`, and `test-browser.mjs` throws when no spec file exists. All of these stay as they are if a build-only web setup stays.
  - `src/forge/feature.py` (`_wire_web`, lock file and package edits for `@app/<plural>-web`), `src/forge/feature_web.py` (699 lines, renders pages from the marked `libs/projects/web` files and `WEB_FILES`), `src/forge/templates/feature/link-picker.tsx`, `src/forge/feature_tests.py` (browser specs). `src/forge/feature_api.py` only names `projects.e2e-spec.ts`, which is an API case and stays.
  - `src/forge/review.py:369` and `src/forge/worker.py:588` read `apps/web/src/index.css` as the theme file, so the theme file stays.
  - `.github/workflows/starter-smoke.yml` lists the starter tests; names change only if a test file is deleted.
  - Guides that name screens: `src/forge/templates/skill.md` (the two "Built in" lines "An admin adds agent accounts ... on the Members screen", the prototype paragraph "Rename or remove the `Project` placeholder", the feature section), `docs/guide.md` (lines about the Members screen), `src/forge/templates/conventions/frontend.md` (Layout), both starter READMEs (route table, app shell, screens), `.codex/skills/app-baseline/SKILL.md` and its twin `.claude/skills/app-baseline/SKILL.md` (shipped by `src/forge/app_baseline.py::ships`).
  - Design-first prototype flow (`design.py`, `skill.md` canvas steps, `brief.md` "Build the screens marked `Build: now`"): no change. It already expects the agent to build screens from the canvas.
- Tests that assert starter screens or run the browser flows against them: `tests/test_starter_tree.py` (`test_2` shell), `tests/test_libs_layout.py` (`test_2`, `test_3`, `test_6`), `tests/test_react_starter.py`, `tests/test_proxy_error_pages.py`, `tests/test_defaults_formats.py` (`test_3` page scan), `tests/test_defaults_loading_rows_and_unsaved_forms.py`, `tests/test_one_company.py` (`one-company.spec.ts`), `tests/test_mcp.py` (browser and Members page cases), `tests/test_agent_ready.py` (`jobs-hooks.ts`), `tests/test_feature_command.py` (`test_2`), `tests/test_feature_projects.py` (`test_5`), `tests/test_feature_access.py`, `tests/test_database_kinds.py`, `tests/test_python_starter.py` (`test_3`), `tests/test_member_removal.py`, `tests/test_starter_app.py`. The board tests (`tests/test_board_*.py`) name Forge's own board screens, not the starter. Not changed.

### Settled (with the reason)

1. **The web app folder keeps a build-only setup and loses every screen.** Kept: `apps/web` config files, `index.html`, a `main.tsx` that mounts only the providers (no router, no routes), `index.css`, `libs/core/web` without its two screen parts, `libs/shared/ui` without `auth-page-frame.tsx`, one new browser spec. Reason: deleting the whole folder would also change both Dockerfiles, both API servers, both test scripts, the Nx project list and the lock files, and would lose pinned and tested rules (React Compiler on, shadcn only, theme tokens, axe check) that every client agent would then rebuild by hand; the tested build setup is a characteristic, not a screen. The summary asks the owner if he wants the harder cut.
2. **Delete the module web libraries completely** (`libs/{auth,history,organisations,projects}/web`), including their hooks and hook tests. Reason: hooks serve the screens; the client's agent writes hooks for its own screens as `frontend.md` shows, and unused hooks are dead code.
3. **API sign-in routes, members routes, projects routes and history routes stay.** Reason: owner decision, only screens go. The Projects module stays as the model that `forge task feature` copies for the API.
4. **`forge task feature` stops writing web files.** Delete `src/forge/feature_web.py`, `src/forge/templates/feature/link-picker.tsx`, `_wire_web` and the web lines of `feature.py`, and the browser specs of `feature_tests.py`. Reason: the command copies the Projects pages, which are going; the new rule makes the client's agent build the screens in the client's design. This removes about 700 lines of Forge code (principle 6).
5. **One new spec, `apps/web/e2e/served-app.spec.ts`,** keeps the browser step alive: the built page loads with its title and the `app-env` meta tag, an unknown path falls back to `index.html`, `/api/...` keeps answering JSON, and the axe check passes. `vitest.config.ts` gets `passWithNoTests: true` because `test:hooks` has no test left. Reason: proves the Docker build still serves the web page; no screen is needed.
6. **`libs/*/contracts` and the Python `libs/shared/api-types` stay.** Reason: the client's screens use them; they are rules about the API, not screens.
7. **The boundary lint for module web libraries and the screen layout in `frontend.md` stay** as rules for the screens the agent adds. Reason: the rules still hold; only the starter example goes. Their tests add a small module web library to the fresh app, as an agent would, and expect the lint to catch a cross-module import.
8. **`tests/test_python_starter.py::test_3` ("tests fail when the API changes a field the web app uses") is deleted.** Reason: no web code uses the field any more; no test without a rule.
9. **The review rule for a person-facing API with no screen is a shipped review block, and applies only to a repo with a web app** (`apps/web`, `web` or `frontend` with a `package.json`, as `doctor.py:465` checks). Reason: an API-only client has nowhere to put a screen; a screen marked `Build: later` in SCREENS.md does not count as missing. A plan names a machine-only route in its own words; no new marker.
10. **The Forge-only rule goes in `AGENTS.md` under `## Review rules` and has no test or check.** Reason: principle 4 (rules are stated, not policed); it is about Forge's own templates and no client repo needs it.

### Done-when details

1. No screens in a new app (SCREENS, SCREENSPY).
   - `tests/test_noscreens_starters.py::test_1_a_new_app_has_no_screens_and_keeps_its_api`, parameters `typescript`, `python`, `earlier adopted`.
   - Setup: `forge init --starter` and `forge init --starter python` in a temp repo, as `tests/test_starter_app.py::test_3` does.
   - New-repo cases assert on the written tree: no `*-page.tsx`, no `pages/` folder, no `app-shell.tsx`, no `app.tsx`, no `libs/{auth,history,organisations,projects}/web`, no `auth-page-frame.tsx`, no `route-error-page.tsx`, no `agent-access-dialog.tsx`; present: `apps/web/{index.html,vite.config.ts,playwright.config.ts,src/main.tsx,src/index.css,e2e/served-app.spec.ts}`, `libs/core/web/src/api-client.ts`, `libs/shared/ui/components.json`, and every `libs/*/server` or `apps/api/app/*` module.
   - Live (`FORGE_STARTER_LIVE=1`): the run reports the API cases and the case `the built app serves its page` from `served-app.spec.ts`; `test:hooks` passes with no test.
   - The lock files come from `corepack pnpm install --lockfile-only` in each starter (TS and PY), not by hand; `--frozen-lockfile` in both Dockerfiles proves them.
   - Rewrite or delete the screen-only tests as listed above, keeping a rule only when its code survives: `test_react_starter.py` keeps "React Compiler on" in `vite.config.ts` and `vitest.config.ts`; `test_proxy_error_pages.py` becomes a vitest case on `libs/core/web/src/api-client.ts` (non-JSON reply raises the normal request error with its status); `test_libs_layout.py::test_2` and `::test_3` follow Settled 7; `test_defaults_formats.py::test_3` keeps the helper-only rule on a page the test adds; `test_one_company.py` drops `one-company.spec.ts` and keeps its API and setup cases; `test_member_removal.py` keeps the API cases only (see Notes).
2. `forge task feature` writes no page (FEATURE).
   - `tests/test_feature_command.py::test_2_the_new_feature_works_like_projects` is rewritten: the generated tree holds the feature's contracts, server, tools, migration, API cases and history, and no file under `libs/<plural>/web` and no edit to `apps/web`, `apps/web/package.json` or the lock file's web importer. Live: the API and tools cases pass in both starters.
   - `tests/test_feature_projects.py::test_5` keeps the API list, detail and history cases; the browser part goes. `test_feature_access.py`, `test_database_kinds.py`, `test_mcp.py::test_3` and `test_agent_ready.py` drop the generated `jobs-hooks.ts` and `jobs.spec.ts` assertions and keep their API and tool cases.
   - Adopted case, `earlier adopted`, in `test_2`: an app from the previous release (with its web files) gets a feature with no web file written and its `apps/web/src/app.tsx` unchanged.
3. Existing repos keep app code (SCREENS). Case `earlier adopted` of `test_1`: after upgrade and `forge sync` on the earlier-release fixture, `git status --porcelain` lists no file under `apps/`, `libs/` or the lock files.
4. Guide and skill (RULES). `tests/test_noscreens_guide.py::test_4_the_guide_says_who_builds_the_screens`, parameters `new init` and `previous release`, with the setup of `tests/test_mcp_resources_guide.py::test_3`. Compare with whitespace collapsed.
   - `app-baseline` skill (both copies), new section "Screens for the API": every API a person uses gets its screen in the client's design, built by the agent with the API, no request needed; webhooks, endpoints only agents or systems call, and background jobs get none; the first screens of a prototype are sign-in (with forgot and reset password and accepting an invite), members and settings, in the client's design, on the canvas as `Build: now`.
   - The same section names the API each basic screen needs, so an agent can build it without the removed code: sign-in, sign-up, forgot and reset password, accept invite; members (list, invite, change role, add agent account with a key shown once, revoke key, remove member, export); settings. It states the behaviours the removed screens proved and that no other text keeps: refetch the account on each page change so a removed member lands on sign-in; the CSRF header on writes; show the API's `message`; loading, empty and error states; confirm before destructive actions; warn about unsaved forms.
   - `skill.md`: the two "Built in" lines say "An admin adds agent accounts with a role and a key that shows once through the Members API; the agent builds the Members screen in the client's design"; the prototype paragraph says "Build the basic screens first in the client's design; the starter has none, and has a `Project` API"; the feature section says the command writes no pages. `docs/guide.md` and `frontend.md` Layout and the two starter READMEs match.
   - `previous release`: after `forge sync`, `git status --porcelain` lists only synced skill and guide files, no app file.
5. Review rule (RULES). `tests/test_noscreens_guide.py::test_5_the_review_reports_a_person_facing_api_with_no_screen`, parameters `new init` and `previous release`, in the prompt-delivery style of `tests/test_react_review_rules.py` (only the worker, Autoreview and GitHub edges are fake). The new `review.md` block sits beside the shadcn and Icons rules in the rules block and is chosen in `src/forge/review.py` for a client repo that has a web app. Rule text: report as P1, titled `Screen: <route>`, a route this change adds that people use, when the change adds no screen for it; webhooks, agent-only routes, MCP, system endpoints and jobs are not findings, nor is a screen marked `Build: later`. The worker brief (`src/forge/templates/brief.md`) gets the same one-line rule for builders, as the Review rules ask. The prompt of an API-only client repo does not hold the rule.
6. Forge's own rule (RULES). One bullet under `## Review rules` in `AGENTS.md`, outside the forge:begin and forge:end lines: report as P1 any screen, page, route table or app shell that a change adds under `src/forge/templates/starter` or `src/forge/templates/starter-python`. No test.

### New and existing repos

- **New repos** (`forge init --starter`, `--starter python`): the API, the rules, the skills, the guide and the build-only web setup; no screen. Plain `forge init` and a newly adopted app get the guide text, skill and review rule only.
- **Existing repos** (on upgrade, after `forge sync`): the new skill, guide and review rule. No app file, no migration, no change to any screen they have. `forge task feature` in an existing starter app now writes no pages too (the earlier adopted case of rule 2). The review rule applies to them only when they have a web app.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| FEATURE | `forge task feature` writes no page | The feature command, its tests and the smoke list stop generating web files; the browser parts of the generated specs go. | 2 | `src/forge/feature.py`, `src/forge/feature_web.py` (delete), `src/forge/feature_tests.py`, `src/forge/templates/feature/link-picker.tsx` (delete), `src/forge/templates/feature/kinds.toml` (web keys only), `tests/test_feature_command.py`, `tests/test_feature_projects.py`, `tests/test_feature_access.py`, `tests/test_database_kinds.py`, `tests/test_mcp.py`, `tests/test_agent_ready.py`, `.github/workflows/starter-smoke.yml` | `tests/test_feature_command.py::test_2` (rewritten, with `earlier adopted`) | | no | |
| SCREENS | The React starter ships no screens | Delete the screens, hooks, shell and screen specs; keep the build-only web setup; add `served-app.spec.ts` and `passWithNoTests`; regenerate the TS lock file. | 1, 3 | `src/forge/templates/starter/apps/web/**`, `starter/libs/{auth,history,organisations,projects}/web/**` (delete), `starter/libs/core/web/src/**`, `starter/libs/shared/ui/src/components/auth-page-frame.tsx` (delete), `starter/pnpm-lock.yaml`, `starter/README.md`, `tests/test_noscreens_starters.py` (new), `tests/test_starter_tree.py`, `tests/test_react_starter.py`, `tests/test_libs_layout.py`, `tests/test_proxy_error_pages.py`, `tests/test_defaults_formats.py`, `tests/test_defaults_loading_rows_and_unsaved_forms.py`, `tests/test_one_company.py`, `tests/test_member_removal.py`, `tests/test_starter_app.py` | `tests/test_noscreens_starters.py::test_1` (`typescript`, `earlier adopted`) | FEATURE | no | |
| SCREENSPY | The Python starter ships no screens | The Python starter's lock file and README, its smoke tests and the removal of the web-field test. | 1 | `src/forge/templates/starter-python/pnpm-lock.yaml`, `starter-python/README.md`, `starter-python/package.json` (only if a script lists a deleted path), `tests/test_noscreens_starters.py`, `tests/test_python_starter.py`, `tests/test_libs_layout.py` | `tests/test_noscreens_starters.py::test_1` (`python`) | SCREENS | no | |
| RULES | The guide and the review say who builds the screens | The app-baseline skill (both copies), `skill.md`, `docs/guide.md`, `frontend.md`, the worker brief, the shipped review block and its selection, and Forge's own review rule. | 4, 5, 6 | `.codex/skills/app-baseline/SKILL.md`, `.claude/skills/app-baseline/SKILL.md`, `src/forge/templates/skill.md`, `docs/guide.md`, `src/forge/templates/conventions/frontend.md`, `src/forge/templates/brief.md`, `src/forge/templates/review.md`, `src/forge/review.py`, `AGENTS.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_noscreens_guide.py` (new), `tests/test_mcp_guide.py`, `tests/test_built_in_defaults_guide.py`, `tests/test_one_company_guide.py` | `tests/test_noscreens_guide.py::test_4`, `::test_5` (new) | | no | |

FEATURE goes first because the feature command reads the Projects web files that SCREENS deletes. SCREENSPY follows SCREENS because the Python app copies its web files from the React starter. RULES shares no file with the other parts and needs no code from them.

New moving parts: none

## Notes

- **Scores (F x H >= 2 x C).**
  - Remove the starter screens: F 3 (every new app), H 2 (a broken first step), C 3 (many files, two lock files) gives 6 >= 6. Kept.
  - The review rule and the guide text: F 3, H 2, C 1 and 2 give 6 >= 2 and 6 >= 4. Kept.
  - Delete the whole web folder, not only its screens: F 3, H 1 (the agent can rebuild the setup), C 3 gives 3 < 6. Cut.
- **Planner choices the owner did not make.**
  1. The build-only web setup stays (Settled 1). The owner's wording was "remove all starter screens", and the planner read the web build setup as a characteristic, not a screen.
  2. The basic screens are sign-in, members and settings, as the owner said; forgot and reset password and accepting an invite count as part of sign-in.
  3. The review rule applies only where the repo has a web app, and a screen marked `Build: later` in the canvas does not count as missing.
  4. `forge task feature` writes no pages, so the agent builds each feature's screens with its API.
- **Order with other work.**
  - FORGE-MAIL-1's last part REMOVEWEB adds a Remove button to the Members screen and a browser case. This story deletes that screen, so REMOVEWEB must be dropped or merged first. Its API and guide parts are already on main. `tests/test_member_removal.py` keeps only the API cases here.
  - FORGE-AGENTREADY-1 (RETRY changes `members-hooks.ts`, `useInvite`) and FORGE-GUIDES-1 (starter READMEs, `skill.md` lines) touch files this story deletes or edits. Merge them first, or the part that follows resolves the clash.
  - A story planned against the Members, Projects or Change history screens needs its Done-when items re-read: those become the agent's job in the client's design.
- No client repo is named in this story's code, tests, texts or commits.
