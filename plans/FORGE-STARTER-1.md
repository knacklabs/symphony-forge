# Starter app for new client React apps

3 parts · Risks: none one-way · New moving parts: Nx in new client apps; a starter check in Forge's own CI

## What changes for you

- A new client React app starts from a runnable starter app. The agent sets up the repo with
  `forge init --starter`, and the first commit holds the whole stack: an Nx workspace with a
  React app (Vite, React Router), a NestJS API with sign-in, Postgres, one example record type
  from the database to the screen, its tests, and CI that runs them.
- The starter is structure only. Its app shell layout is built from shadcn/ui components: a
  sidebar that collapses to icons, with a toggle button and Cmd/Ctrl+B; a top bar with
  Cmd/Ctrl+K search and a user menu; and the sign-in, settings and 404 routes. The code uses
  feature folders with example hooks, so the prototype grows in the same shape.
- The starter has no look of its own. It uses shadcn/ui's neutral theme tokens, and it sets no
  brand look and no fixed screen design. Each app gets its own design (theme tokens, type,
  colours and its own screens) in the next story: a design canvas per app, made from its
  interview with impeccable and emil-design-eng. That story's build applies the design to the
  starter.
- Forge's stack pages change from npm workspaces to Nx, and from TanStack Router to React
  Router. A Python backend (FastAPI) is used only when the person asks for it, and it has no
  starter yet.
- In a client app that uses shadcn/ui, `forge close` refuses a change that adds a second UI
  component library, or a hand-made copy of a shadcn/ui component. The review reports any other
  hand-built UI component as a serious finding, unless the change says why shadcn/ui cannot do
  it.
- An existing client app keeps its own stack and code on upgrade. The check and the review rule
  apply only to what later changes add, so a library the app already has is never refused.

## Why

Each new client app starts empty, so the agent rebuilds sign-in, the app shell, the test set-up
and CI by hand for every client, and each copy differs. Forge's stack page still says npm
workspaces, while the guide already says Nx. Without a check, an agent can add a second component
library or hand-build a dialog, and the look and accessibility drift. The owner chose these
defaults on 22 October 2026, from section 2 of the research checklist
(`/Users/ravikiranvemula/Workdir/app-checklist-research.md`).

Forge ships the starter as a fixed set of files with exact versions and a lockfile, and does not
run the Nx and shadcn tools at set-up. Set-up then takes seconds, works offline, gives the same
app on every machine, and Forge's tests can check it without the network.

## Done when

1. **The starter app is a runnable stack: an Nx workspace with a React app (Vite, React Router), a NestJS API with sign-in on Postgres, and one example record type carried from the database to the screen. Its test command runs lint, type checks, API tests on a real database and browser tests, and they pass. One account never sees or changes another account's records, and a deployed app never writes a password-reset link to its log. The Dockerfile builds and starts it through the root `build` and `start:prod` scripts.**
2. **The starter's app shell layout is built from shadcn/ui components with shadcn/ui's neutral theme tokens and no brand look: a sidebar that collapses to icons, with a toggle button and Cmd/Ctrl+B; a top bar with Cmd/Ctrl+K search and a user menu; sign-in, sign-up, forgot-password, settings and 404 routes; and feature folders with example hooks. Its browser tests walk each of these.**
3. **`forge init --starter` on a new repo writes the starter in the first commit, with a forge.toml whose test command runs the starter's tests, from an installed Forge as from its source. In a folder that already has an app, it refuses and names the file it found. Forge's stack, deploy, frontend, backend and testing pages name the Nx layout (`apps/web`, `apps/api`, `libs/shared`) and React Router in place of npm workspaces and TanStack Router, and the guide tells the agent to use the starter for a new React app.**
4. **In a client app with shadcn/ui set up, `forge close` refuses a change that adds a second UI component library, or a new file outside `components/ui/` named like a shadcn/ui component, and says what to do. What the default branch already has is never refused.**
5. **In such an app, the review reports a new hand-built UI component as P1, unless a `Not shadcn:` comment in the code says why shadcn/ui cannot do it, and Forge holds that finding until it is fixed. The worker brief states the rule.**

## New and existing repos

- **New repos** (init): the guide tells the agent to run `forge init --starter` for a new React
  app. The first commit holds the starter, the new Dockerfile and a forge.toml whose test command
  runs the starter's tests. The shadcn check and the review rule apply from the first fix. Plain
  `forge init` works as before, with the new Dockerfile.
- **Existing repos** (on upgrade to this release, after `forge sync`): no app file changes. The
  repo keeps its Dockerfile, its test command and its stack, and gets no starter. The new stack
  pages arrive with the release and say that an app on npm workspaces keeps them. The check and
  the review rule apply only in an app that has shadcn/ui's `components.json`, and only to what a
  change adds. Tested on the adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Each part reverts with its pull request, and a client app owns its copy of
the starter after set-up.

Allowance: the part that adds the starter's files goes over the 400-line part limit. Most of its
lines are the shadcn/ui component files and the lockfile, which are copied as they are and must
not be cut or split; the app code on top of them is small. Approving this story gives that one
part permission to go over the limit. When close asks the size question for it, the answer is
this approval. The other two parts keep the limit.

Trade-off: the starter's versions age. Forge refreshes them in its own releases; a client app
updates its copy like any other dependency.

Trade-off: the close check matches file names. A file named like a shadcn/ui component for
another reason (for example `features/billing/card.tsx`) is refused, and the agent renames it.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Every Done-when item has exactly one test function, `test_<n>_...`. APP's tests (1, 2) are in
`tests/test_starter_tree.py`; INIT's test (3) is in `tests/test_starter_app.py`; GUARD's tests
(4, 5) are in `tests/test_shadcn_only.py`. Each file starts with `STORY = "FORGE-STARTER-1"`. No
test imports forge. Tests 3 to 5 run the forge command, on a new repo (`_fresh_client` in
`tests/test_setup.py`) and on `tests/fixtures/adopted-v1.2.2` moved to this release
(`_repo_adopted_on_the_previous_release` in `tests/test_upgrade_command.py`). Tests 1 and 2 are
about the tree itself, which only new repos get: they read `src/forge/templates/starter/` and run
the starter's own commands on a copy of it; the adopted case of the starter is in test 3. Only
the existing stubs are faked: Autoreview and GitHub (`env`, `finding`, `blocked`, `CLEAN` in
`tests/test_close.py`, and `client as setup_client` from
`tests/test_close_keeps_reviews_for_unchanged_branch_diffs.py`).

**No network in the main CI.** The fast halves read files and JSON only, and test 3's wheel
check builds the wheel offline with `uv build`, as `tests/test_client_setup_and_migration.py`
test_1 already does. The live half of tests 1 and 2 (npm install, Postgres, Playwright, the
Docker build) runs only when `FORGE_LIVE_STARTER=1`, read at collection time like
`LINUX_CONTAINERS` in `tests/test_proto_deploy.py` (conftest removes `FORGE_*` variables later).
One module-scoped fixture copies the tree and the skeleton's `Dockerfile` and `.dockerignore`
into a temp folder and runs the testing page's command there once, with Playwright's JSON
reporter. A new workflow, `.github/workflows/starter-smoke.yml`, copies the shape of
`codex-smoke.yml`: optional, never a required check, run by hand or on pull requests that change
`src/forge/templates/starter/**`, `src/forge/templates/skeleton/**`, `src/forge/init.py`,
`tests/test_starter_tree.py`, `tests/test_starter_app.py` or the workflow itself, with
`timeout-minutes: 20`. Forge's main CI stays under 5 minutes.

**Words this story pins.**
- Versions, exact, each the newest stable release that was at least two weeks old on
  22 October 2026 in the npm registry: `shadcn` 4.21.4; `nx` and every `@nx/*` 23.3.0; `react`
  and `react-dom` 19.3.0; `react-router` 8.4.0; every `@nestjs/*` that has it 12.1.2; `vite`
  8.3.3; `prisma` and `@prisma/client` 7.10.0. Every other dependency is the newest stable
  release at least two weeks old on the day APP builds the tree, written as an exact version.
  The shadcn/ui component files, the blocks and GUARD's component name list all come from
  shadcn 4.21.4's registry.
- The starter lives in `src/forge/templates/starter/`. Init copies it as it copies `skeleton/`,
  never over a file that is already there, into the one first commit. The skeleton keeps the
  Dockerfile and `.dockerignore`; the starter has none.
- Layout: one root `package.json` (exact versions only, no `workspaces` field), its
  `package-lock.json`, `nx.json`, `tsconfig.base.json`, `prisma.config.ts` (it names
  `apps/api/prisma/schema.prisma`, so `npx prisma migrate deploy` runs from `/app`), `apps/web/`
  (React, Vite, React Router; `components.json`; `src/components/ui/` holds shadcn/ui files only;
  `src/components/` holds shared composites; `src/features/<name>/{components,hooks,api,schemas,routes}`),
  `apps/api/` (NestJS; `prisma/schema.prisma` and its first migration), `libs/shared/` (types and
  zod validators both apps use), `e2e/` (Playwright), `compose.test.yml`, `docker-compose.yml`,
  `.env.example`, `.gitignore`, `README.md` and `NOTICE.md` (shadcn/ui's MIT notice).
- Root scripts: `build` builds both apps; `start:prod` starts the API, which serves the web
  build at `/` and answers `GET /health`; `test` runs lint, typecheck and unit tests for every
  project through Nx, then `playwright test`.
- The option is `forge init --starter` (a flag, no value). It adds the starter only on the
  new-repo path of `init.init`. Refusal `REFUSALS["starter"]`: `"The starter app goes only into
  a new repo with no app: {why}."`, next step `forge init without --starter`. `{why}` is
  `{marker} is already here` (`package.json`, `pyproject.toml` or `go.mod` in the folder) or
  `this repo already has commits` (the adoption path). It refuses before anything is written.
  With `--starter`, forge.toml's `test` is the command in `conventions/testing.md` ("npm ci &&
  npx playwright install --with-deps chromium && docker compose ... && npm test"). Without it,
  `NODE_TEST` is unchanged.
- The UI library list and the shadcn/ui component name list are two constants in
  `src/forge/app_baseline.py`. The libraries: `@mui/material`, `@mui/joy`, `antd`,
  `@chakra-ui/react`, `@mantine/core`, `react-bootstrap`, `bootstrap`, `primereact`,
  `semantic-ui-react`, `@nextui-org/react`, `@heroui/react`, `flowbite-react`,
  `@blueprintjs/core`, `@fluentui/react-components`, `@radix-ui/themes`, `daisyui`,
  `@headlessui/react`, `react-aria-components`, `@ark-ui/react`, `rsuite`, `grommet`. The
  component names are every `registry:ui` item name in shadcn 4.21.4's registry (`button`,
  `dialog`, `dropdown-menu`, `sidebar`, `table`, and the rest), compared after a PascalCase file
  stem is turned to kebab-case.
- A review finding against the rule has a title that starts `shadcn: `. `score.normalise` gives
  it the constitution floor (Gain 4 or more, Work 2 or less) and marks it `(floor: shadcn)`.

### Done-when details

1. The runnable stack (APP).
   - The API: sign-up, sign-in and sign-out with a server session in Postgres and an httpOnly
     `SameSite=Lax` cookie; passwords hashed with Node's `crypto.scrypt` (no new library). One
     example record type, `Project` (name; status `active` or `archived`; the audit fields of
     `conventions/database.md`), with list, create, edit and delete under `/api/v1/projects`,
     each scoped to the signed-in account; another account's project answers 404. Follow
     `conventions/backend.md`, `api.md` and `security.md`.
   - Forgot and reset password. The forgot-password request always answers 200 with the same
     message, whether or not the email has an account. The API picks the log mail provider,
     which writes the reset link to the log, only when `APP_ENV` is `development` or `test`.
     With any other `APP_ENV` and no mail service set, it sends nothing and logs no link or
     token. A real email service comes with the story that names it. `compose.test.yml` sets
     `APP_ENV=test`.
   - `skeleton/Dockerfile`: `RUN npm ci && npm run build`, `WORKDIR /app`, and the CMD keeps
     the migration line, then `exec npm run start:prod`.
   - The starter's own tests: Supertest API tests against the running API and a fresh database
     for sign-up, sign-in, sign-out and each project action; Vitest for the hooks; lint and
     typecheck. Two API tests carry the security rules:
     - Account isolation: account A creates a project. Account B gets 404 on reading, changing
       and deleting it, and A then reads it unchanged.
     - No reset link in a deployed log: an API instance started with `APP_ENV=production` and
       its log captured answers a forgot-password request for an existing account and for an
       unknown email with the same status and body, and the captured log has neither the reset
       path nor the token.
   - Test: `test_1_the_starter_is_a_runnable_stack`. Fast half: the layout above exists; every
     version in the root `package.json` is exact (digits and dots only) and the pinned
     packages have the pinned versions; `package-lock.json`'s root entry has the same
     dependencies; the skeleton Dockerfile has `npm run build` and `npm run start:prod` and no
     `--workspace`. Live half: the testing page's command exits 0 on the copy, and its report
     shows the two security tests passed. Then the image that `compose.test.yml` built answers
     `GET /health` with 200.
2. The shell (APP).
   - Structure only. The theme is shadcn/ui's neutral tokens as `npx shadcn@4.21.4 init` writes
     them (the `neutral` base colour, the default radius and the system font stack). No brand
     colour, logo, custom font, illustration or styling beyond the shadcn/ui components and the
     layout. The next story's design replaces the tokens and the screens.
   - From shadcn/ui components and blocks of 4.21.4, copied as source: `SidebarProvider`,
     `Sidebar collapsible="icon"`, `SidebarInset`, `SidebarTrigger` in the top bar and
     `SidebarRail` on the edge, and Cmd/Ctrl+B from the block; the sheet on mobile; the open
     state kept as the block keeps it. The top bar: trigger, breadcrumbs, a search box that opens
     `CommandDialog` on Cmd/Ctrl+K (wired by the starter), and a user menu with profile,
     settings, theme (light, dark, system) and sign out. Pages: sign in (with a "Forgot
     password?" link), sign up, forgot password, reset password, settings (profile, password,
     appearance), the projects list (data table with sort and pagination in the URL, a create
     and edit dialog with react-hook-form and the shared zod schema, an `AlertDialog` before
     delete, Sonner toasts) and 404. A skip link and one `<main>`.
   - Example hooks in `apps/web/src/features/projects/hooks/`: `useProjects`, `useProject`,
     `useCreateProject`, `useUpdateProject`, `useDeleteProject` over TanStack Query.
     Components never call fetch.
   - Test: `test_2_the_starter_shell_comes_from_shadcn_components`. Fast half: the shell file
     has `collapsible="icon"`, `SidebarTrigger` and `SidebarRail`; the router has the paths
     `/sign-in`, `/sign-up`, `/forgot-password`, `/reset-password`, `/settings`, `/projects`
     and `*`; no `.tsx` file outside `apps/web/src/components/ui/` has the stem of a file inside
     it; the theme file's colour tokens are the neutral values of `shadcn init` 4.21.4, kept in
     the test as one fixed list. Live half: the report from the shared run shows these
     Playwright tests passed: sign up, then sign in; from sign-in, the "Forgot password?" link
     opens the forgot-password page, an email is sent, and the page shows the confirmation;
     Ctrl+B collapses and expands the sidebar; Ctrl+K opens search and goes to Projects;
     create, edit and delete a project; the theme changes in settings; an unknown address
     shows the 404 page; axe finds no serious problem on the shell.
3. Init, packaging, pages and guide (INIT).
   - `conventions/stack.md`: the Workspace row says Nx ("one build tool for the web app and the
     API; no Nx Cloud"); the Frontend row says React with Vite and React Router; the layout and
     the deploy contract above; one line: "An app set up before Nx keeps its npm workspaces and
     its Dockerfile."
   - `deploy.md`, `frontend.md` (`apps/web/src/`, React Router), `backend.md` (`apps/api/src/`),
     `testing.md` (the root test script through Nx), `demo-data.md` (`apps/api/src/demo/`), and
     the client stack paragraph of `src/forge/standards.md` say the same.
   - `skill.md`: the "Set up a new repo" row says `forge init --starter` for a new React app and
     plain `forge init` for any other stack; the Prototype section says to build the prototype
     on the starter and rename or remove `Project`; the stack-default line says the FastAPI
     backend has no starter yet.
   - Test: `test_3_init_writes_the_starter_and_the_nx_pages`, with the parameter `case` in
     ("new", "wheel", "pyproject", "package.json", "adopted").
     - new (`_fresh_client` with `--starter`): exit 0. The first commit has every file of
       `src/forge/templates/starter/`, byte for byte, dotfiles included. forge.toml's `test` is
       the testing page's command. The conventions folder that the worker brief names (found as
       `client_templates` in `tests/test_client_setup_matches_stack.py` does) has `Nx` and
       `apps/web` in `stack.md` and `React Router` in `frontend.md`, and no page says
       `npm workspaces` except the keep line. `.claude` and `.codex` `skills/forge/SKILL.md`
       have `forge init --starter`.
     - wheel: `uv build --wheel` into a temp folder. The wheel has
       `forge/templates/starter/<path>` for every path that `git ls-files
       src/forge/templates/starter` lists, dotfiles included. This is the proof for an
       installed Forge: init copies the folder it finds in its own package.
     - pyproject and package.json: the marker file is in the folder before init. Init exits 1
       with the refusal line naming it, and writes nothing.
     - adopted: `forge init --starter` in the adopted fixture exits 1 with `this repo already
       has commits`. After upgrade and `forge sync`, no starter file exists, the Dockerfile and
       the test command are unchanged, and the conventions and SKILL.md checks of "new" pass.
4. Close check (GUARD).
   - `app_baseline.check(top, cfg, base)`, called by `close.close` next to `spotted.check`
     (one line in `close.py`, which stays under 1,200 lines). It runs only when
     `cfg["repo"] == "client"` and a tracked file named `components.json` is at `HEAD`. It
     reads files through git only.
   - A library problem: a listed library that a `package.json` at `HEAD` names under
     `dependencies` or `devDependencies`, and that no `package.json` at the merge base names.
   - A copy problem: a file added since the merge base (`--diff-filter=A`), ending `.tsx` or
     `.jsx`, with no `components/ui` folder in its path, whose stem is a shadcn/ui component
     name.
   - One refusal, `REFUSALS["shadcn"]`: `"This app uses shadcn/ui only, and this change adds
     {problems}."`, next step `use the shadcn/ui component (npx shadcn@4.21.4 add <name>) and
     remove the copy or the library, then forge close {item}`. `{problems}` names each library
     and each file, joined by "; ".
   - Test: `test_4_close_refuses_a_second_ui_library_and_shadcn_copies`, with the parameter
     `adopted`. On main first: `components.json` and `apps/web/src/components/ui/button.tsx`
     (adopted: also `antd` in `package.json`). A fix that adds `@mui/material` exits 1 naming
     it. A fix that adds `apps/web/src/features/orders/Button.tsx` exits 1 naming the file. A
     fix that adds `apps/web/src/components/ui/dialog.tsx` and an `orders-table.tsx` goes on
     to review. Adopted: a fix that changes the `antd` version goes on to review. A repo with
     no `components.json` that adds `@mui/material` goes on to review.
5. Review rule (GUARD).
   - `review.md`, Build simple, after the impeccable paragraph: "In an app with shadcn/ui set up
     (a `components.json`), report a new UI component that hand-builds what a shadcn/ui
     component or block already does as a P1 finding titled `shadcn: <the component>`, unless a
     `Not shadcn: <why>` comment at the component says why shadcn/ui cannot do it. A composite
     built from shadcn/ui components is not a finding, and neither is a library or component the
     default branch already has."
   - `score.normalise`: the constitution floor also matches a title that starts `shadcn: `,
     marked `(floor: shadcn)`.
   - `brief.md`: "In a client app with shadcn/ui set up, use shadcn/ui only. Close refuses a new
     UI component library and a new file outside components/ui/ named like a shadcn/ui
     component. Review holds a hand-built UI component unless a `Not shadcn: <why>` comment
     says why."
   - Test: `test_5_review_holds_a_hand_built_component`, with the parameter `adopted`. A fix
     with `components.json` on main changes a screen and closes. The review prompt has the rule
     sentence. Autoreview returns a P1 finding titled `shadcn: DatePicker` scored `Gain 2, Work
     3, Harm 1`; close exits 1 with "The review left serious findings open", and the finding
     shows `(floor: shadcn)`. The worker brief that `forge work` sends has the brief sentence.

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
| APP | The starter app tree | The starter tree with its API, sign-in, example record type, shell and tests, the Dockerfile that builds and starts it, and the live starter workflow. The one part allowed over the line limit (see Risks). | 1, 2 | `src/forge/templates/starter/**` (new), `src/forge/templates/skeleton/Dockerfile`, `.github/workflows/starter-smoke.yml` (new), `tests/test_proto_deploy.py` | `tests/test_starter_tree.py` (`test_1`, `test_2`), `tests/test_proto_deploy.py` (test_10's fake app) | | no | |
| INIT | Init with the starter, and the Nx pages | `forge init --starter` with its refusal and packaging, the stack, deploy, frontend, backend, testing and demo-data pages, the standards paragraph, and the guide lines. | 3 | `src/forge/init.py`, `pyproject.toml` (only if the wheel misses starter files), `src/forge/templates/conventions/stack.md`, `src/forge/templates/conventions/deploy.md`, `src/forge/templates/conventions/frontend.md`, `src/forge/templates/conventions/backend.md`, `src/forge/templates/conventions/testing.md`, `src/forge/templates/conventions/demo-data.md`, `src/forge/standards.md`, `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_fix_forge_says_end_to_end_tests_come_first_b.py` | `tests/test_starter_app.py` (`test_3`) | APP | no | |
| GUARD | shadcn-only check and review rule | The close check on a second UI library and shadcn/ui copies, the review rule with its score floor, and the brief line. | 4, 5 | `src/forge/app_baseline.py`, `src/forge/close.py`, `src/forge/templates/review.md`, `src/forge/score.py`, `src/forge/templates/brief.md` | `tests/test_shadcn_only.py` (`test_4`, `test_5`) | | no | |

New moving parts: Nx, as the build tool of new client apps (items 1, 3); the optional starter-smoke workflow in Forge's own CI, which keeps the starter's live run out of the main CI (item 1).

## Notes

- **Order.** APP first, then INIT, which copies APP's tree and tests it byte for byte. GUARD
  shares no file with either and runs in parallel. The pinned shadcn version is the one fact
  APP and GUARD share, and this doc pins it, so neither waits for the other. Test 2 has its own
  small check (no `.tsx` outside `components/ui/` with the name of a file inside it), so the
  starter never trips GUARD's check.
- **Why files, not tools.** Running `create-nx-workspace` and `npx shadcn add` at set-up needs
  the network, takes minutes, asks questions, and gives a different app when either tool
  releases. A fixed tree with exact versions and a lockfile follows principle 7 and lets the
  fast tests run offline. APP makes the tree once with the pinned tools, then commits the
  result. A later Forge release refreshes it.
- **Why a flag.** About 90 test files run `forge init`. A starter by default would put a
  Docker test command and a large tree into each of them. The flag keeps plain `forge init` as
  it is, and the guide gives the agent the flag for a new React app.
- **Packaging (INIT).** The wheel must carry the dotfiles in `templates/starter/`
  (`.env.example`, `.gitignore`); test 3's wheel case proves it. If hatch drops a dotfile, add
  the folder to `pyproject.toml`'s force-include, as the app-baseline skill is added.
- **Existing tests.** APP: `tests/test_proto_deploy.py` test_10 keeps its checks; its fake app
  moves to root `build` and `start:prod` scripts, `apps/web` and `apps/api`, the pinned Prisma
  version and a root `prisma.config.ts`, with no `workspaces` field. INIT:
  `tests/test_fix_forge_says_end_to_end_tests_come_first_b.py` checks the new root test script
  line; `tests/test_client_setup_matches_stack.py` test_1 stays as it is. Run every test that
  runs `forge init`; plain `forge init` must give the same files as today, except the
  Dockerfile.
- **Not in this story.**
  - Each app's own design: its theme tokens, type, colours and its own screens. The next story
    makes it on a design canvas per app, from the app's interview, with impeccable and
    emil-design-eng, and that story's build applies it to the starter. The next story also has
    the Opus completeness check of the prototype and the impeccable and emil-design-eng gate.
    No part of this story is user-facing, so it has no design folder.
  - A FastAPI starter for a Python backend: a later story, when a client asks for Python. Until
    then the agent builds it in a fix, as the guide says today.
  - A starter for an existing repo that was set up on an earlier release and has no app yet.
  - Email sending, OIDC sign-in, notifications, CSV export and the other checklist items, each
    with the story that needs it.
- **Not to do.**
  - No new command and no `forge.toml` setting. The one new option is `--starter`.
  - No Nx Cloud, remote cache or telemetry in the starter.
  - No change to an existing repo's app files, Dockerfile or test command on upgrade or sync.
  - No escape option on the close check; the review rule has the `Not shadcn:` comment.
- No client repo is named anywhere in this story's code, tests, texts or commits.
