# New client apps start from the client notes and a fixed modular stack

3 parts · Risks: none one-way · New moving parts: pnpm in place of npm in new client apps; Nx's lint plugin as a dev dependency of the starter

## What changes for you

- For a new app, the FDE puts all the client notes in the repo. The agent reads all of them, fills
  in the product brief and the problem cards, and lists the contradictions and gaps it finds.
- The agent then asks the FDE one question at a time, and only about points that change a screen,
  a field or a flow. There is no fixed number of questions. Every other open point gets a
  default, and the agent lists it as an assumption that the FDE can change.
- Questions that the FDE cannot answer go on the recap's list for the client. The prototype does
  not wait for them.
- Every new app is one app split into modules, on pnpm and Prisma, from the first prototype. Each
  module owns its tables. Other modules use it only through its public service, never through its
  tables.
- The starter turns on Nx's module-boundary lint, so an import across modules fails the tests. A
  review holds a new query on another module's tables as a serious finding, and a cold read holds
  a plan that has one. The sign-off review checks the whole product for such queries once.
- The constitution starts with the 21 product defaults filled in, and it lists the module rules
  above as fixed rules. The agent asks nothing about the fixed rules, and it raises a default
  only when the notes contradict it. You still approve the constitution once, after sign-off.
- Existing apps keep their package manager and folder layout, and nothing moves on upgrade.
  Reviews hold only new cross-module queries, and the constitution records the stack that the
  app already uses.

Design: none (no screens; it changes the starter, rules and guide)

## Why

The module rule is only text in the shipped backend page today, and the starter has no lint rule
that enforces it. The starter uses npm, not pnpm. Before the prototype, the agent asks the product
questions one by one, with the eight-question limit of a story, also when the client notes already
answer most of them. The constitution shows its defaults only after sign-off. On 24 October 2026
the owner chose these changes: start from the client notes, ask only what changes a screen, a
field or a flow, build one app split into modules on pnpm and Prisma from the first prototype,
enforce the module rule with lint and review, and leave existing apps as they are.

## Done when

1. **A new client app starts as one app split into modules on pnpm and Prisma: sign-in and the example records are separate modules, each module owns its own tables, and the starter's tests, its built image and its browser flows pass. An existing app keeps its package manager, lockfile, Dockerfile, test command and folder layout after upgrade and sync.**
2. **In a new client app, the tests fail when a module imports another module's internal files or when the web app imports a backend module, and the failure names the module-boundary rule.**
3. **A review reports a query that a change adds on another module's tables as a serious finding, and Forge holds the work until it is fixed. The sign-off review does the same for the whole product, and a cold read reports a plan that has such a query the same way. A normal review never reports a query that the default branch already has, so an existing app is held only for new ones.**
4. **The guide tells the agent to start a new app from the client notes: read every note, fill the brief and the problem cards, list the contradictions and gaps, ask the FDE one question at a time only about points that change a screen, a field or a flow, with no fixed number, mark every other open point as an assumption, and put what the FDE cannot answer on the recap's list for the client without holding the prototype. New repos get this at init, and existing repos on upgrade and sync.**
5. **The guide tells the agent to start the constitution with the 21 defaults filled in and, in an app made from the starter, the fixed module rules; to raise a default only when the notes contradict it; and, in any other app, to record the stack, package manager and layout that the app already uses. The owner still approves it once after sign-off. New repos get this at init, and existing repos on upgrade and sync.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. The starter's tables do not change:
the schema moves into one file per module, and there is no new migration. A client app owns its
copy of the starter after set-up.

Allowance: the part that changes the starter goes over the 400-line part limit. Most of its lines
are the new pnpm lockfile, which replaces the npm lockfile, and files that move into their
modules without change. Approving this story gives that one part permission to go over the limit.
When close asks the size question for it, the answer is this approval. The other two parts keep
the limit.

Trade-off: a prototype fix keeps its light review, which holds only the most serious findings, so
it does not hold a cross-module query. The module-boundary lint still runs in the prototype's
tests, and the sign-off review checks the whole product for such queries once.

Trade-off: a new app's test script and its image get pnpm through Corepack, which Node 24
includes. A developer machine needs only Node 24 and Docker, as now.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-MODULAR-1"`. Each test runs the forge command or,
for the starter's own behaviour, the starter's own commands, and never imports forge. One test
per Done-when item, named `test_<n>_...`. Forge-command tests run on a new repo (`_fresh_client`
in `tests/test_setup.py`, or `setup(repo, kind="client")` in `tests/test_story.py`) and on
`tests/fixtures/adopted-v1.2.2` moved to this release. Only the existing stubs are faked:
Autoreview and GitHub (`env`, `finding`, `blocked`, `CLEAN` in `tests/test_close.py`, and
`_client_repo as setup_client` from `tests/test_score_notes.py`, as `tests/test_shadcn_only.py`
uses them) and the readers (`say` in `tests/test_readloop_gates.py` for Claude).

**Words this story pins.** Each part owns its own words; no part needs another part's code.

- The starter's layout (STARTER):

  ```
  pnpm-workspace.yaml     packages: apps/*, libs/*
  apps/api/               the NestJS app: main.ts, app.module.ts, health/; wires the modules
  apps/api/prisma/schema/ base.prisma (generator, datasource), auth.prisma (Account, Session,
                          PasswordResetToken), projects.prisma (Project, ProjectStatus)
  apps/web/               the React app; imports @app/shared
  libs/core/              @app/core: config, common (filter, envelope, correlation, logger,
                          CSRF guard, validation pipe), the Prisma service      tag type:core
  libs/auth/              @app/auth: sign-in, sessions, the session guard, CurrentAccount and
                          AccountPrincipal                                       tag type:module
  libs/projects/          @app/projects: the example records                     tag type:module
  libs/shared/            @app/shared: schemas and types both apps use           tag type:shared
  ```

  `apps/api` has the tag `type:api` and `apps/web` has the tag `type:web`. Each lib's
  `src/index.ts` is its public entry, and its package's `exports` has only `.`. A module's entry
  exports its Nest module, its service, and the public types and decorators that other modules
  use; nothing else.
- The lint rule (STARTER): `eslint.config.mjs` turns on `@nx/enforce-module-boundaries` as an
  error for every `*.ts` and `*.tsx` file, with these `depConstraints`: `type:web` on
  `type:shared`; `type:api` on `type:module`, `type:core`, `type:shared`; `type:module` on
  `type:module`, `type:core`, `type:shared`; `type:core` on `type:core`, `type:shared`;
  `type:shared` on `type:shared`. The rule's own checks (no relative import across projects, no
  import of an app, no circular import) stay on.
- The finding title (REVIEW): `Module tables: <the query>`, after a read note's optional
  `Blocking:` or `Advisory:` label. Its score line is marked `(floor: module tables)`.
- The constitution's new section (GUIDE): `## Fixed rules`, between `## Defaults` and
  `## Architecture choices` in the guide's outline, only in an app whose tests run Nx's
  module-boundary lint:

  ```
  ## Fixed rules
  - One app on pnpm and Prisma, split into modules.
  - Each module owns its tables, in its own schema file.
  - A module uses another module only through its public service, never through its tables.
  - The tests run Nx's module-boundary lint, so an import across modules fails them.
  ```

  The approval check on `app-constitution` does not change: it neither requires nor reads this
  section.

### Done-when details

1. The modular starter on pnpm (STARTER).
   - pnpm: `package.json` gets `packageManager: "pnpm@<exact version>"`, and npm's `overrides`
     become pnpm's own (keep `playwright-core` pinned to `@playwright/test`'s version).
     `package-lock.json` goes; `pnpm-lock.yaml` and `pnpm-workspace.yaml` come. Every version
     stays exact. pnpm runs no dependency install script unless it is listed in
     `onlyBuiltDependencies`; list only the ones the tests need. Every call to pnpm uses the
     same Corepack form, `corepack pnpm ...`, with `COREPACK_ENABLE_DOWNLOAD_PROMPT=0`: the root
     scripts that run other scripts (such as `test`, which becomes
     `corepack pnpm run lint && corepack pnpm run typecheck && ...`), `scripts/test.mjs` and
     `scripts/test-build.mjs`. `corepack pnpm` installs no `pnpm` shim on the path, so a bare
     nested `pnpm run` would fail on a machine with only Node 24. `corepack pnpm install
     --frozen-lockfile` replaces `npm ci`. The developer needs no new set-up step.
   - New dev dependency: `@nx/eslint-plugin`, pinned to the same version as `nx` (22.0.1). The
     starter does not have it today.
   - Modules: move the files into the layout above, as they are, except for their imports.
     `common/session.guard.ts` reads the Session table, so it moves into `libs/auth`, and
     `apps/api/src/app.module.ts` registers it from `@app/auth`. `libs/projects` gets
     `CurrentAccount` and `AccountPrincipal` from `@app/auth`. Every import across projects uses
     the package name; none uses a relative path. Use Nx 22's TypeScript project-references
     layout, so the API's `tsc` build and the image resolve each package at run time, and Vite
     and Vitest read the sources. The API keeps `tsc`, because Nest needs decorator metadata.
     `scripts/test-build.mjs` loads the compiled projects controller from its new path.
   - Schema: `prisma.config.ts` points `schema` at `apps/api/prisma/schema` and keeps the
     migrations path. The split changes no table, so the existing migration stays the only one.
   - Dockerfile: the starter tree gets its own `Dockerfile`, a copy of the skeleton's with pnpm
     (`corepack enable`, `pnpm install --frozen-lockfile && pnpm run build`,
     `pnpm exec prisma migrate deploy`, `exec pnpm run start:prod`). `init._scaffold` writes the
     starter's files after the skeleton's, so the starter's `Dockerfile` replaces the skeleton's
     with no code change. The skeleton's npm `Dockerfile` stays for plain `forge init`.
   - Convention pages: `stack.md` (a pnpm row and a modules row in the table, the new layout,
     the deploy contract with `pnpm run`, and the line "An app set up before this release keeps
     its package manager, lockfile and folder layout." next to the Nx keep line), `backend.md`
     (the layout above; its Modules section names the public entry, the tags, the lint rule and
     the schema file per module), `database.md` (`pnpm exec prisma`, one schema file per module),
     `deploy.md` (`pnpm-lock.yaml`, `pnpm run build`, `pnpm run start:prod`), `testing.md`
     (`pnpm test`), `frontend.md` (`@app/shared` where it names `libs/shared`), `demo-data.md`
     (one line: the loader in `apps/api/src/demo/` is app code, not a module, and may read every
     table). `src/forge/standards.md` names the modules next to `libs/shared`.
   - README: pnpm in "Run it"; "How it works" names the modules and the rule.
   - New repo test: `tests/test_starter_tree.py::test_1_the_starter_is_a_runnable_stack` changes
     to check `pnpm-lock.yaml` (its root importer's specifiers equal `package.json`'s, and the
     pinned packages, read as text with no new YAML library), `packageManager` with an exact
     version, `pnpm-workspace.yaml`, the four libs with one `type:` tag each, the three schema
     files, and the starter's own `Dockerfile` with the pnpm lines. Its live run
     (`FORGE_STARTER_LIVE=1`) uses the starter's `Dockerfile` in place of the skeleton's, keeps
     `npm_config_*` scrubbed and pnpm's store in the temporary folder, and keeps all its API and
     browser cases.
   - Existing repo test: `tests/test_starter_app.py::test_3_init_writes_the_starter_and_the_nx_pages`,
     adopted case: before the upgrade, the fixture commits a `package.json` and a
     `package-lock.json` of its own. After upgrade and sync, both are byte for byte the same;
     `pnpm-lock.yaml`, `pnpm-workspace.yaml` and `libs/` do not exist; the Dockerfile and the
     test command are unchanged (as today). Its new case still checks every starter file byte for
     byte, which now includes the `Dockerfile`, and its wheel case covers the new files.
2. The lint rule fails a cross-module import (STARTER).
   - Test: `tests/test_modular_starter.py::test_2_an_import_across_modules_fails_the_starter_tests`,
     marked `@pytest.mark.platform`, with the parameter `case` in ("clean", "reach into a module",
     "the web app imports a backend module").
     - Always: `eslint.config.mjs` names `@nx/enforce-module-boundaries`, and the root `test`
       script runs lint first.
     - Live only (`FORGE_STARTER_LIVE=1` and Node 24 on the path; skip otherwise, as test_1 does):
       a module-scoped fixture copies the starter to a temporary folder and runs
       `corepack pnpm install --frozen-lockfile` once. Then, for each case:
       - clean: `corepack pnpm run lint` exits 0.
       - reach into a module: add `libs/projects/src/reach-in.ts` with
         `import { AuthService } from '../../auth/src/auth.service';` and a use of it. Lint exits
         non-zero, and its output names `@nx/enforce-module-boundaries`.
       - the web app imports a backend module: add `apps/web/src/reach-in.ts` with
         `import { ProjectsService } from '@app/projects';` and a use of it. Lint exits non-zero,
         and its output names the rule and `type:web`. No project depends on an app, so this
         import makes no cycle, and Nx reaches its tag check (an import from core into a module
         would make a cycle, because every module imports core, and Nx reports the cycle first).
       Remove the added file after each case.
   - `.github/workflows/starter-smoke.yml` runs this file with `tests/test_starter_tree.py`, and
     its `paths` add `tests/test_modular_starter.py`.
   - Existing repos get no lint change; item 1's existing repo test covers them.
3. Reviews, sign-off and cold reads hold a query on another module's tables (REVIEW).
   - `review.md`, `<!-- rules -->` block, after the shadcn rule, this text (the test checks it,
     whitespace joined): `In an app with a database, report a query that this change adds in one
     module on a table another module owns as a P1 finding titled `Module tables: <the query>`. A
     module owns the tables in its own schema file; in an app without one schema file per module,
     it owns the tables that only its code writes. Other modules reach those tables only through
     its public service. A query the default branch already has is not a finding, and neither is
     app code outside the modules, such as the demo-data loader.`
   - `review.md`, `<!-- signoff -->` block, one sentence: `Report a query in one module on a
     table another module owns as a P1 finding titled `Module tables: <the query>`.` The sign-off
     diff starts from an empty root, so it covers the queries that the prototype added.
   - `cold-read.md`, after the `What counts` list: `In a client app, report a plan whose part has
     one module query a table another module owns as a note titled `Module tables: <the part>`.`
   - `score.normalise`: a title that matches
     `^(?:\d+\.[ \t]*)?(?:(?:Blocking|Advisory):[ \t]*)?Module tables: ` gets the same floor as a
     constitution or shadcn finding (Gain 4 or more, Work 2 or less), and its line ends
     `(floor: module tables)`. Harm does not change. A `Later:` finding and a `Case: rare` note
     keep today's handling.
   - `brief.md`, next to the shadcn line: `In an app with modules, use another module only
     through its public service, and never query a table it owns. The tests' module-boundary lint
     fails an import across modules, and a review holds a new query on another module's tables.`
   - The light review of a prototype fix and of a change to documents only does not change.
   - Test: `tests/test_module_tables_review.py::test_3_reviews_and_reads_hold_a_query_on_another_modules_tables`,
     with the parameter `adopted` (`[False, True]`, ids `new-client` and `adopted-v1.2.2`, through
     `setup_client`), run as `test_5` of `tests/test_shadcn_only.py` runs.
     - A fix changes a file. `forge work` gives a brief with the brief sentence
       (`install_claude`, `calls(log)[-1]["brief"]`). Close's review prompt (`env.prompt()`) has
       the rules text. Autoreview returns a P1 finding titled
       `Module tables: ProjectsService reads Session` with `Gain 2, Work 3, Harm 1`. Close exits
       1 with "The review left serious findings open", the title and
       `Gain 4, Work 2, Harm 1 (floor: module tables)`.
     - A story's first cold read (the Claude reader with `say`, after `approved_constitution`
       from `tests/test_story.py`) gets a prompt with the cold-read sentence. A note
       `Blocking: Module tables: The plan has projects read Session` scored
       `Gain 2, Work 1, Harm 1` holds the read: the notes show `(floor: module tables)` and no
       below-the-bar disposition, and `forge read` reports it as open.
     - New repo only, because the sign-off path is the same on both: the sign-off review's
       prompt, started with `forge decision accept client-signoff` as
       `tests/test_proto_signoff.py` starts it, has the sign-off sentence.
4. Notes-first discovery for a new app (GUIDE).
   - `skill.md`, `## Discovery`, the **A new project.** paragraph: remove "run this discovery
     with the story limit". Keep the pre-meeting brief, `## Words they use`, the spreadsheet
     headers and the recap. Add these sentences, which the test checks (whitespace joined):
     - `On a new app, the FDE puts every client note in docs/context/. Read all of them before you
       ask anything.`
     - `Fill docs/product/BRIEF.md and the problem cards in docs/product/DISCOVERY.md from the
       notes, and list each contradiction and gap for the FDE.`
     - `Ask the FDE one question at a time, and only about a point that changes a screen, a field
       or a flow. A new app has no fixed number of questions.`
     - `Give every other open point a default, mark it (assumed) where you write it, and list
       these assumptions in one message for the FDE to change.`
     - `Put each question the FDE cannot answer on the recap's Still to find out list, and build
       the prototype without waiting for the answer.`
   - The everyday limit stays: "Ask at most two questions for a fix and eight for a story", and
     `tests/test_discovery.py` keeps its text. The recap outline in `fde.md` keeps its
     `Still to find out` line, which is the list for the client, so `fde.md` does not change.
   - Test: `tests/test_notes_first_discovery.py::test_4_a_new_app_starts_from_the_client_notes`,
     with the parameter `adoption` in ("new init", "previous release upgrade and sync"), set up as
     `test_4` of `tests/test_app_constitution.py` is. For `.claude` and `.codex`,
     `skills/forge/SKILL.md` has the five sentences, and its Discovery section no longer has
     "with the story limit".
5. The constitution starts prefilled, with fixed rules (GUIDE).
   - `skill.md`, `## App constitution`: replace three sentences that `GUIDE_SENTENCES` in
     `tests/test_app_constitution.py` pins, and remove them from that list:
     - "Before the prototype, ask only the product questions: ..." becomes `Before the
       prototype, take the product answers from the client notes: what the app is for, who uses
       it, what it keeps track of with each thing's fields, and the options of each choice list.`
     - "After the customer's sign-off and before the first story, write the app's constitution in
       docs/product/CONSTITUTION.md." becomes `After the customer's sign-off and before the first
       story, finish the app's constitution in docs/product/CONSTITUTION.md.`
     - "Show every default in one message, and let the person change any of them." becomes `At
       the start, write docs/product/CONSTITUTION.md with every default from Constitution defaults
       filled in, and raise a default with the FDE only when the notes contradict it.`
   - Add `In an app whose tests run Nx's module-boundary lint, copy the fixed rules into the
     constitution's ## Fixed rules section, and ask nothing about them.` and `In any other app,
     record the stack, package manager and folder layout that the app already uses, and leave out
     ## Fixed rules.` The section's outline gets `## Fixed rules` as pinned above. The approval
     sentences stay: the owner approves once with `forge decision accept app-constitution`.
   - Test: `tests/test_notes_first_discovery.py::test_5_the_constitution_starts_with_the_defaults_and_fixed_rules`,
     with the same `adoption` parameter. For both hosts, `SKILL.md` has the three new sentences,
     the two added ones and the `## Fixed rules` outline with its four lines, and `fde.md` has
     `## Constitution defaults`.

### New and existing repos

- **New repos** (init): `forge init --starter` writes the modular pnpm starter, its own
  Dockerfile and the lint rule. The guide, the review, sign-off and cold-read rules and the brief
  line arrive with setup. Plain `forge init` keeps the npm Dockerfile and its test command.
- **Existing repos** (on upgrade to this release, after `forge sync`): no app file, lockfile,
  Dockerfile or test command changes. The guide, the review rules and the brief line arrive with
  sync. The review holds only queries that a change adds. An app made from an earlier release's
  starter keeps npm and its layout, and its constitution records them. Tested on the adopted
  earlier-release fixture moved to this release (items 1, 3, 4 and 5).

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| STARTER | The modular starter on pnpm | The starter as pnpm workspace packages, with sign-in and the example records as modules, one schema file per module, the module-boundary lint with tags, its own pnpm Dockerfile, the convention pages and the live workflow. New repos get it from `forge init --starter`; existing repos keep their files. The one part allowed over the line limit (see Risks). | 1, 2 | `src/forge/templates/starter/**`, `src/forge/templates/conventions/stack.md`, `src/forge/templates/conventions/backend.md`, `src/forge/templates/conventions/database.md`, `src/forge/templates/conventions/deploy.md`, `src/forge/templates/conventions/testing.md`, `src/forge/templates/conventions/frontend.md`, `src/forge/templates/conventions/demo-data.md`, `src/forge/standards.md`, `.github/workflows/starter-smoke.yml`, `pyproject.toml` (only if the wheel misses a new starter file) | `tests/test_starter_tree.py` (`test_1`), `tests/test_starter_app.py` (`test_3`), `tests/test_modular_starter.py` (`test_2`, new) | | no | |
| REVIEW | Reviews hold a query on another module's tables | The review, sign-off and cold-read rules, the `Module tables:` score floor and the worker brief line, on new and existing repos. | 3 | `src/forge/templates/review.md`, `src/forge/templates/cold-read.md`, `src/forge/score.py`, `src/forge/templates/brief.md` | `tests/test_module_tables_review.py` (`test_3`, new) | | no | |
| GUIDE | Notes-first discovery and a prefilled constitution | The guide's notes-first discovery for a new app, the prefilled constitution with its fixed rules, and the existing app's recorded stack, on new and existing repos. | 4, 5 | `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_app_constitution.py` (`GUIDE_SENTENCES` only) | `tests/test_notes_first_discovery.py` (`test_4`, `test_5`, new) | | no | |

New moving parts: pnpm, in place of npm, as the package manager of new client apps (item 1); `@nx/eslint-plugin`, a dev dependency of the starter that supplies the module-boundary rule (item 2).

## Notes

- **Order.** The three parts share no file and run in parallel. Each has its own new test file.
  STARTER pins the layout and the tags. The texts of REVIEW and GUIDE name no starter path, so
  neither waits for STARTER. All three ship in one release.
- **Why packages, not folders.** Nx's rule works on Nx projects, and it refuses a relative import
  across projects. So each module is a lib with a package name, and pnpm workspaces link the
  packages, which is the layout Nx 22 makes by default. The shared Nest code (`libs/core`) must be
  a lib too, because a lib cannot import an app.
- **Why one schema file per module.** It shows which module owns a table, so a review can tell a
  query on another module's table from the diff. Foreign keys across modules stay; the rule is
  about queries in code.
- **STARTER changes no flow.** It adds no command, option, setting or flow step. The convention
  pages carry the layout to workers, and REVIEW's brief line tells them the rule.
- **Sign-off sentence.** The owner's decisions name the review and the cold read. This plan also
  adds the rule to the sign-off review, because a prototype fix's light review does not hold it
  and the prototype's code grows into production. REVIEW drops that one sentence and its test
  case if the owner does not want it.
- **Not in this story.**
  - Moving an existing app to pnpm or to modules, or a lint rule for an existing app.
  - Frontend feature folders as modules; the web app is one project.
  - A check in `forge close` for cross-module queries; the review holds them.
  - A change to the 21 defaults or to the approval check on the constitution.
- **Not to do.**
  - No new command, option, `forge.toml` setting, skeleton file or stored state.
  - No change to the light review, or to an existing repo's app files on upgrade or sync.
  - No Nx Cloud, remote cache or telemetry.
- No client repo is named anywhere in this story's code, tests, texts or commits.
