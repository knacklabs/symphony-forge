---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-25T17:48:29.235185+00:00
seconds: 76.726
read_hash: f18fcc34d65efd094f19bbdf4fb045c0d08cedb9
round: 2
passed: no
doc_seen: f18fcc34d65efd094f19bbdf4fb045c0d08cedb9
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 2e0c85eec297b838992e986998e4a929302f8152
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a17422-3ff2-7450-a68e-a8633e7e2ef7
session:
loop_choice: accept
loop_reason: The owner accepted the one advisory note as a known issue: show the sign-up link when the options request fails
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

1. Blocking: P1 — `Design: none` excludes a changed onboarding flow.
   Raise: Gate. Case: normal use - a visitor opens `/sign-up` in a one-company app.
   `plans/FORGE-SINGLECO-1.md:22` declares no design, but lines 164–168 replace account creation with a redirect. The current form submits and navigates to Projects (`src/forge/templates/starter/apps/web/src/features/auth/pages/sign-up-page.tsx:22`). This changes a flow; `src/forge/templates/skill.md:842` requires design evidence before its cold read.
   Gain 4, Work 2, Harm 3
   Disposition: cut The doc now has the design folder and a closed sign-up page.

2. Blocking: Trap: copying the Python API service starts concurrent migrations: item 5.
   Raise: Plan gap. Case: normal use - the live runner starts a fresh test database.
   `plans/FORGE-SINGLECO-1.md:112` specifies copying `api` onto the same database. That service waits only for the database (`src/forge/templates/starter-python/compose.test.yml:22`), while its entrypoint runs `alembic upgrade head` (`src/forge/templates/starter-python/Dockerfile:19`). Both copies can create the same schema concurrently; the migration runner has no serialization (`src/forge/templates/starter-python/apps/api/migrations/env.py:35`). The existing production service already avoids this by waiting for `api` health. The proposed copy can fail before setup or either suite runs.
   Gain 4, Work 1, Harm 4
   Disposition: cut The one-company test service waits for api to be healthy, so only one service migrates.

3. Blocking: The infinite options cache prevents an open browser from observing the documented switch to many.
   Raise: Functional. Case: normal use - someone keeps sign-in open while the operator changes `APP_COMPANIES` to `many` and restarts the API.
   `plans/FORGE-SINGLECO-1.md:165` pins `staleTime: Infinity`. The browser retains one QueryClient and disables focus refetching (`src/forge/templates/starter/apps/web/src/main.tsx:10`). Its cached `false` therefore keeps hiding sign-up and redirecting `/sign-up` after the switch. The proposed switch test at plan line 180 uses another API service and never exercises this browser state.
   Gain 3, Work 2, Harm 3
   Disposition: cut The options request uses the normal query defaults and reads again on each page load.

4. Advisory: Unproven: item 2: setup credential validation has no command-level refusal test.
   Raise: Test. Case: normal use - an operator mistypes `ADMIN_EMAIL`.
   `plans/FORGE-SINGLECO-1.md:96` promises schema validation, an API-equivalent message and exit 1. Its setup cases at lines 147–153 cover valid credentials and duplicate email only. Both account-creation helpers accept their inputs without schema validation (`src/forge/templates/starter/libs/auth/src/auth.service.ts:87`; `src/forge/templates/starter-python/apps/api/app/auth/service.py:111`). A command that omits the promised validation could pass every named case while creating an unusable admin account.
   Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

## Round 2

5. Advisory: The options request has no defined failure state or recovery.
   Raise: Plan gap. Case: normal use - `/auth/options` fails transiently when someone opens sign-in.
   `plans/FORGE-SINGLECO-1.md:172` adopts the normal query defaults, which disable retries and focus refetching (`src/forge/templates/starter/apps/web/src/main.tsx:13`). The link appears only with `signUpOpen: true`, so a failed request hides account creation in a many-company app without an explanation or retry control. The new design explicitly excludes loading and error states (`docs/design/FORGE-SINGLECO-1/SCREENS.md:38`), and the browser cases cover successful responses only.
   Gain 3, Work 2, Harm 3
   Disposition: keep - The owner accepted the one advisory note as a known issue: show the sign-up link when the options request fails
