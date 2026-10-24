# Four frontend defaults for new client React apps

2 parts · Risks: none one-way · New moving parts: babel-plugin-react-compiler as a dev dependency of the starter

## What changes for you

- A new client React app starts with React Compiler on, and its review flags hand-written memoization in its own code.
- A new client React app follows a composition rule that its review checks: layout through children, shared-state parts as compound components, logic without markup in custom hooks, and no boolean props that switch a component between modes.
- Filters, tabs, sort order and the page number of a list live in the web address, so a shared link or a page refresh shows the same view.
- Each route in a new client app has its own error page, so a crash on one screen shows that screen's error page and the other screens keep working. React Router stays.
- An existing client app gets these rules for new code only; its current code is not changed or flagged.

Design: none (no new screen; the error page of a route is a state of an existing screen)

## Why

The starter sets no frontend defaults beyond its layout. Its projects page writes memoization by hand, only that page keeps its list in the web address, no rule says how components are composed, and no route has an error page, so one crash on a screen can blank the whole app. On 24 October 2026 the owner chose these four defaults for new client React apps, kept React Router, and chose that existing apps get the rules for new code only.

## Done when

1. **A new client React app starts with React Compiler turned on, and its own code has no hand-written useMemo, useCallback or React.memo.**
2. **Its review flags a change that adds useMemo, useCallback or React.memo to the app's own code, but not to the shadcn/ui copies.**
3. **Its review flags a component that a change adds and that breaks the composition rule.**
4. **Reloading or sharing a link to a sorted or paged list shows the same view.**
5. **A crash on one route shows that route's error page, and the other routes still work.**
6. **An existing client app keeps its current code on upgrade, and its review checks these rules only on new code.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. A client app owns its copy of the
starter after set-up, so no existing app changes.

Trade-off: React Compiler does not optimize a component that uses a library it cannot memoize
safely, such as the table library on the projects page. That component runs as it does today,
and the lint shows a warning for it.

Trade-off: the review scores a memoization or composition finding like any other finding. A
finding with a low score becomes a follow-up, and the merge does not wait for it.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-REACTDEFAULTS-1"`. Each test runs the forge
command or, for the starter's own behaviour, reads the starter's files or runs its own commands,
and never imports forge. One test per Done-when item, named `test_<n>_...`. Browser behaviour
(items 4 and 5) is proven by named Playwright flows in the starter, which `starter-smoke` runs
live through `tests/test_starter_tree.py` (`FORGE_STARTER_LIVE=1`). Forge-command tests run on a
new repo and on `tests/fixtures/adopted-v1.2.2` moved to this release, through `_client_repo as
setup_client` from `tests/test_score_notes.py`, with the stubs that `tests/test_shadcn_only.py`
uses (`env`, `finding`, `blocked`, `CLEAN` from `tests/test_close.py`; `install_claude` and
`calls` from `tests/test_worker.py`).

**Plan against FORGE-MODULAR-1's starter.** STARTER starts after FORGE-MODULAR-1/STARTER merges.
That part moves the starter to pnpm workspaces and Nx libs: `apps/web` stays where it is,
`libs/shared` becomes `@app/shared`, `package-lock.json` becomes `pnpm-lock.yaml`, every pnpm call
is `corepack pnpm ...`, the starter gets its own `Dockerfile`, and `eslint.config.mjs` gets
`@nx/enforce-module-boundaries`. Read the merged starter before you start; where a path below
differs from the merged tree, follow the merged tree.

**Words this story pins.** Each part owns its own words; no part needs the other part's code.

- Review finding titles (RULES): `Memo: <the component>` and `Composition: <the component>`.
  No score floor: `src/forge/score.py` does not change.
- Playwright flow names (STARTER), exact, in `apps/web/e2e/starter-shell.spec.ts` and in
  `BROWSER_FLOWS` of `tests/test_starter_tree.py`:
  - `a reloaded or shared list link shows the same view`
  - `a crash on one screen shows its error page and the other screens still work`
- The route error page (STARTER): `apps/web/src/components/route-error-page.tsx`, export
  `RouteErrorPage`. Heading `This page could not load`; a `Try again` button that reloads the
  page; a `Go to Projects` link. It renders no `<main>`, because a route inside the app shell
  already sits in the shell's `<main>` (`SidebarInset`).

### Done-when details

1. React Compiler is on in the starter (STARTER).
   - `package.json` `devDependencies`: `"babel-plugin-react-compiler": "1.0.0"` (exact; published
     7 October 2025; React 19 needs no runtime package). Update `pnpm-lock.yaml` with
     `corepack pnpm install`, so `tests/test_starter_tree.py::test_1` still finds the lock's root
     importer equal to `package.json`.
   - `apps/web/vite.config.ts` and `apps/web/vitest.config.ts`:
     `react({ babel: { plugins: ['babel-plugin-react-compiler'] } })`. `@vitejs/plugin-react`
     5.0.4 already runs Babel, so nothing else is needed.
   - ESLint: `eslint-plugin-react-hooks` 7.0.1 is already a dev dependency but is not used. Add
     `reactHooks.configs.flat.recommended` (the name in its README) to `eslint.config.mjs` for
     `apps/web/src/**/*.{ts,tsx}`, and leave `apps/web/src/components/ui/**` out of it (the
     shadcn copies: `sidebar.tsx` calls `Math.random()` inside `useMemo`, which the purity rule
     reports). Fix any app code outside `components/ui` that the rules report as an error; do not
     turn a rule off. `incompatible-library` is a warning on `useReactTable`; `eslint .` passes
     with warnings, so leave it.
   - Remove the hand memoization in
     `apps/web/src/features/projects/pages/projects-page.tsx`: line 68
     `useMemo(() => readListQuery(searchParams), [searchParams])` becomes a plain call, and the
     `columns` `useMemo` (line 109) becomes a plain array. TanStack Query hashes the query key,
     and the table is in manual sorting and pagination mode, so a new object or array on each
     render is safe. `apps/web/src/components/ui/sidebar.tsx` keeps its `useMemo` and
     `useCallback` calls.
   - The starter keeps its own composition rule: `SortLabel` (projects-page.tsx line 57) takes a
     boolean `active` that switches it between two renderings. Replace `active` and `order` with
     one prop `sorted: false | 'asc' | 'desc'`, the value of `column.getIsSorted()`, so each
     header passes `sorted={column.getIsSorted()}`.
   - No build-output marker check: `react.memo_cache_sentinel` is also in React DOM's own
     runtime, so its presence in the bundle proves nothing. Vite fails the build if the plugin
     cannot load, so the static check below plus the live build are the proof.
   - `stack.md`: the Frontend row becomes `React with Vite, React Router and React Compiler`.
     `README.md` "How it works": one sentence that React Compiler memoizes, so the code has no
     `useMemo`, `useCallback` or `React.memo` outside `components/ui`, and one that each route
     has an error page.
   - Test (new repo): `tests/test_react_starter.py::test_1_a_new_app_starts_with_react_compiler_on`
     reads the starter tree: `package.json` pins `babel-plugin-react-compiler` exactly;
     `apps/web/vite.config.ts` names `babel-plugin-react-compiler`; `eslint.config.mjs` names
     `reactHooks.configs.flat.recommended`; no `.ts` or `.tsx` file under `apps/web/src` outside
     `components/ui` contains `useMemo`, `useCallback` or `memo(`. No platform marker: it only
     reads files. The `starter-smoke` run builds the app with the plugin loaded.
   - Existing repo: the starter is written only by `forge init --starter`;
     `tests/test_starter_app.py::test_3` (adopted case) already shows that upgrade and sync write
     no starter file. Item 6's test covers the review side.
2. Review flags new hand memoization (RULES).
   - `review.md`, `<!-- rules -->` block, a new paragraph after the motion paragraph (the one that
     ends "Motion that follows these rules is not a `Simpler:` finding."), this text (the test
     checks it, whitespace joined): `In a React app with React Compiler turned on
     (`babel-plugin-react-compiler` in a `package.json`), report a `useMemo`, `useCallback` or
     `React.memo` that this change adds as a P1 finding titled `Memo: <the component>`. The
     compiler memoizes. Code under `components/ui/` (the shadcn/ui copies) is not a finding, and
     neither is code the default branch already has.`
   - `brief.md`, `## Build simple`, a new paragraph after the line "Joining lines or removing blank
     lines never counts as a reduction.", this text (the test checks it): `In a React app with
     React Compiler turned on, do not add useMemo, useCallback or React.memo; the compiler
     memoizes. Compose components as the frontend convention says: children for layout, compound
     components for parts that share state, custom hooks for logic with no markup, and no boolean
     prop that switches a component between modes. Review flags new code that breaks either
     rule.` (FORGE-MODULAR-1/REVIEW adds a line next to the shadcn line; this paragraph is lower
     down, so the two do not touch the same lines.)
   - `conventions/frontend.md`: a new `## Components` section after `## Server data`:
     - React Compiler is on (`babel-plugin-react-compiler` in the Vite config) and memoizes. Do
       not add `useMemo`, `useCallback` or `React.memo`. The shadcn/ui copies in
       `components/ui/` keep theirs.
     - Pass layout content as `children`.
     - Build parts that share state as a compound component: one parent holds the state in a
       context, and its parts (`<Filters>`, `<Filters.Status>`) read it.
     - Put logic that renders no markup in a custom hook.
     - Do not add a boolean prop that switches a component between modes (`<Card compact>`,
       `isEditing`). Make two components, or a compound component.
   - Test: `tests/test_react_review_rules.py::test_2_review_flags_new_hand_memoization`, with
     `adopted` in `[False, True]` (ids `new-client`, `adopted-v1.2.2`), through `setup_client`.
     Commit on main a `package.json` with `babel-plugin-react-compiler` in `devDependencies`.
     Start a fix as `_fix` in `tests/test_shadcn_only.py` does. `forge work` gives a brief with
     the brief paragraph (`install_claude`, `calls(log)[-1]["brief"]`). The fix adds a
     `useMemo` to `apps/web/src/features/home.tsx`. Autoreview returns a P1 finding titled
     `Memo: Home` with `Gain 4, Work 1, Harm 1`. Close exits 1 with "The review left serious
     findings open" and the title, and close's review prompt (`env.prompt()`) has the review
     paragraph.
3. Review flags a new component that breaks the composition rule (RULES).
   - `review.md`, right after item 2's paragraph, this text (the test checks it): `In a React
     app, report a component or prop that this change adds and that breaks the frontend
     convention's composition rule as a P1 finding titled `Composition: <the component>`: layout
     passes content as `children`; parts that share state are a compound component that shares it
     through context; logic with no markup is a custom hook; and no boolean prop switches a
     component between modes. Code under `components/ui/` is not a finding, and neither is code
     the default branch already has.`
   - The brief paragraph and the `## Components` section from item 2 carry the worker side.
   - Test: `tests/test_react_review_rules.py::test_3_review_flags_a_component_that_breaks_the_composition_rule`,
     same `adopted` parameter and set-up as test_2. The fix adds `apps/web/src/features/status-card.tsx`
     with a `compact` boolean prop. Autoreview returns `Composition: StatusCard` with
     `Gain 4, Work 1, Harm 1`. Close exits 1 with the title, and `env.prompt()` has the
     composition paragraph.
4. A reloaded or shared list link shows the same view (STARTER).
   - The projects page already keeps `page`, `sortBy` and `sortOrder` in the search params
     (`readListQuery`, `setQuery`). No filter or tab exists in the starter, and this story adds
     none.
   - `conventions/frontend.md` (RULES writes it): a `## Screen state in the web address`
     section: keep filters, tabs, sort order and the page number in the search params with React
     Router's `useSearchParams`, so a reload or a shared link shows the same view; read them with
     a default for a missing or wrong value, as `readListQuery` in the starter's projects page
     does; keep only short-lived state, such as an open dialog, in `useState`.
   - Playwright flow `a reloaded or shared list link shows the same view`: sign up, add 21
     projects through the API with the `create, edit, and delete a project` flow's naming loop
     (move that loop into a helper both flows call, taking the count), so they are `Pagination
     project 00` to `Pagination project 20` and no other project exists. Sort by Name, go to page
     2. Reload: the URL keeps `page=2`, `sortBy=name` and `sortOrder=asc`, the `Pagination project
     20` row shows, the text
     `Page 2 of 2` shows, and the Name header has `aria-sort="ascending"`. Then open the same
     URL in a new page of the same browser context (the same signed-in person): the same three
     checks pass.
5. A crash on one route shows that route's error page (STARTER).
   - `errorElement` works only with React Router's data router, and the starter uses
     `<BrowserRouter>` with `<Routes>`. Move to `createBrowserRouter` with
     `createRoutesFromElements`, so the routes stay JSX and
     `tests/test_starter_tree.py::test_2`'s route checks on `app.tsx` still pass. `app.tsx`
     exports `router`; `App` becomes the root layout route (the `<title>`, the skip link and an
     `<Outlet />`). `main.tsx` renders `<RouterProvider router={router} />` where
     `<BrowserRouter><App /></BrowserRouter>` is now, and keeps `<Toaster />`.
   - Every `<Route>` gets `errorElement={<RouteErrorPage />}`: the root layout route, each public
     route, the protected layout route and each route inside it. An error in `/projects` then
     renders inside the app shell, so the menu still works. React Router clears a route's error
     when the person goes to another route.
   - `conventions/frontend.md` (RULES writes it): replace "Start with React Router for the app
     shell, sign-in, protected routes, and 404/403 pages." with: `Start with React Router for the
     app shell, sign-in, protected routes, and 404/403 pages. Build the routes with
     createBrowserRouter and RouterProvider, and give each route errorElement={<RouteErrorPage
     />}, so a crash on one screen shows that screen's error page and the other screens still
     work.`
   - Playwright flow `a crash on one screen shows its error page and the other screens still
     work`: sign up; route `GET **/api/v1/projects?*` to a 200 envelope
     `{ success: true, data: { items: null, pagination: { page: 1, limit: 20, totalItems: 0,
     totalPages: 1 } }, error: null }`, so the projects page throws while it renders
     (`projects.data.items.length`). Go to `/projects`: the `This page could not load` heading
     shows, and the sidebar's Settings link shows. Click Settings: the Settings heading shows.
     Remove the route, then load `/projects` again with `page.goto` (a full page load, which
     drops TanStack Query's in-memory cache of the bad response; clicking Projects would render
     the cached `items: null` and crash again): the Projects heading and `No projects yet.` show.
     The flow changes no app code to cause the crash. For the same reason, the error page's `Try
     again` button does a full reload (`window.location.reload()`), not a router navigation.
   - UI: the error page uses the 404 page's shadcn/ui parts and theme tokens. The impeccable pass
     and the emil-design-eng checklist apply to it as to any UI change.
6. An existing app keeps its code, and only new code is checked (RULES).
   - `conventions/frontend.md` (RULES), a last section `## In an app set up before this
     release`: `These rules apply to code that a change adds. The app's current code stays as it
     is, and the review does not flag it. An app without React Compiler keeps its own
     memoization, and an app on <BrowserRouter> keeps it.`
   - The memo rule applies only where `babel-plugin-react-compiler` is in a `package.json`, so an
     existing app without the compiler is never told to remove memoization.
   - Test: `tests/test_react_review_rules.py::test_6_an_existing_app_keeps_its_code_and_only_new_code_is_checked`,
     adopted case only (the item is about existing apps). Before `setup_client(..., True)`, write
     `apps/web/src/features/home.tsx` with a `useMemo` and a `compact` boolean prop, so the
     fixture's adoption commit holds it. After upgrade and sync, the file on main is byte for byte
     the same. A fix changes another file; Autoreview returns `CLEAN`; close succeeds; and
     `env.prompt()` has both review paragraphs, with their sentence "neither is code the default
     branch already has". The brief's conventions folder (`is in \`...\`` in the brief, as
     `tests/test_starter_app.py::test_3` reads it) has `frontend.md` with the
     `## In an app set up before this release` text.

### New and existing repos

- **New repos** (`forge init --starter`): the starter has React Compiler, the hooks lint, no hand
  memoization, the data router with an error page on each route, and the two new browser flows.
  The review rules, the brief paragraph and the frontend convention arrive with setup. Plain
  `forge init` gets the rules and the convention, and no starter.
- **Existing repos** (on upgrade to this release, after `forge sync`): no app file changes. The
  review rules, the brief paragraph and the frontend convention arrive with sync, and they apply
  only to code a change adds. The memo rule applies only in an app that has React Compiler.
  Tested on the adopted earlier-release fixture moved to this release (items 2, 3 and 6).

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
| RULES | Review and worker rules for React code | The memo and composition review rules, the worker brief paragraph, and the frontend convention's components, web-address, route error page and existing-app sections, on new and existing repos. | 2, 3, 6 | `src/forge/templates/review.md`, `src/forge/templates/brief.md`, `src/forge/templates/conventions/frontend.md` | `tests/test_react_review_rules.py` (`test_2`, `test_3`, `test_6`, new) | | no | |
| STARTER | React defaults in the starter | React Compiler and the hooks lint, no hand memoization, the data router with an error page on each route, and the two browser flows, in the starter that `forge init --starter` writes. | 1, 4, 5 | `src/forge/templates/starter/**`, `src/forge/templates/conventions/stack.md`, `tests/test_starter_tree.py` (`BROWSER_FLOWS` only) | `tests/test_react_starter.py` (`test_1`, new); Playwright flows `a reloaded or shared list link shows the same view` and `a crash on one screen shows its error page and the other screens still work` in `apps/web/e2e/starter-shell.spec.ts`, required live by `tests/test_starter_tree.py::test_2` | FORGE-MODULAR-1/STARTER | yes | |

New moving parts: babel-plugin-react-compiler 1.0.0, a dev dependency of the starter that turns on React Compiler (item 1).

## Notes

- **Order.** RULES and STARTER share no file and run in parallel. STARTER waits only for
  FORGE-MODULAR-1/STARTER, which rewrites the starter's package manager, lockfile, lint config
  and layout. RULES waits for nothing: FORGE-MODULAR-1/STARTER changes one line of
  `frontend.md` (`libs/shared` to `@app/shared`) and FORGE-MODULAR-1/REVIEW adds lines next to
  the shadcn rules in `review.md` and `brief.md`; RULES writes other lines of those files. Both
  parts ship in one release.
- **Item 4 says sorted or paged, not filtered.** The starter's list has no filter or tab, so no
  browser flow can show one. The convention keeps filters and tabs in the web address for new
  code. If the owner wants a filter in the starter too, STARTER adds a status filter to the
  projects list: about 30 lines, plus a `status` query field on the projects API.
- **No score floor.** Unlike the shadcn rule, `Memo:` and `Composition:` findings keep the
  reviewer's scores, as the owner's lean-review rule asks. Add a floor in `score.normalise` only
  if reviews keep scoring them too low to matter.
- **The light review does not change.** A prototype fix's light review and a docs-only review do
  not check the two rules.
- **Changes no flow.** No command, option, `forge.toml` setting or stored state. `skill.md`
  does not change; the brief paragraph carries the worker side.
- **Not in this story.** A lint rule that forbids `useMemo` (the review flags it); a move away
  from React Router; a change to an existing app's router or memoization; error pages for the
  API.
- No client repo is named anywhere in this story's code, tests, texts or commits.
