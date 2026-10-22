---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-22T17:25:43.131545+00:00
seconds: 373.981
read_hash: c28c2789042650d9a3852c756ba05318ac3a71a8
round: 1
passed: no
doc_seen: c28c2789042650d9a3852c756ba05318ac3a71a8
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a164a0-031f-7251-b109-d6bdc5a5cf3a
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

1. Blocking: Password-reset links would enter production logs.
   Raise: Security. `plans/FORGE-STARTER-1.md:139-145` requires logging reset links without restricting that provider to development. This contradicts `src/forge/templates/conventions/security.md:32`, which forbids tokens in logs.
   Case: normal use - a user requests a password reset in a deployed starter; access to application logs exposes the credential that resets their password.
   Gain 5, Work 2, Harm 4
   Disposition: cut - only the development and test mail provider (APP_ENV development or test) logs the link; any other APP_ENV sends nothing and logs no link or token, forgot-password answers the same either way, and an API test proves it (item 1 and its details).

2. Blocking: Unproven: item 1: another account’s projects remain private.
   Raise: Test. `plans/FORGE-STARTER-1.md:144` requires another account’s project to return 404, but the API coverage at lines 146-147 specifies sign-in and project actions without an account-isolation case. Every specified test could pass with unscoped project queries. The existing testing convention explicitly requires this refusal proof (`src/forge/templates/conventions/testing.md:47-48`).
   Case: normal use - two users create projects, and one requests or changes the other’s project.
   Gain 4, Work 2, Harm 4
   Disposition: cut - an API test has account B get 404 on reading, changing and deleting account A's project, and A then reads it unchanged; item 1 names the rule.

3. Blocking: Split: STARTER → starter application; init, packaging and stack integration.
   Raise: Plan gap. `plans/FORGE-STARTER-1.md:267` assigns the workspace, authentication, database, shell, CRUD, tests, Docker integration, documentation and workflow to one task. Lines 71-72 acknowledge that it substantially exceeds the part limit but defer the allowance decision. `src/forge/close.py:201-216` enforces that limit when no allowance is recorded.
   Case: normal use - the builder completes the planned task and close stops for an additional owner decision.
   Gain 4, Work 2, Harm 3
   Disposition: cut - STARTER is split into APP (the tree, Dockerfile, live workflow) and INIT (init --starter, packaging, pages, guide; After APP); Risks states that APP alone goes over the line limit, because of the copied shadcn/ui files and the lockfile, as the one allowance the owner gives at approval.

4. Blocking: The parallel tasks depend on a shadcn version that neither task pins first.
   Raise: Plan gap. `plans/FORGE-STARTER-1.md:130-132` derives GUARD’s component inventory from “the pinned shadcn version”; lines 162-167 derive STARTER’s source and theme from that same version. No version is specified, both After cells are empty at lines 267-268, and lines 274-276 require parallel execution.
   Case: normal use - the two builders independently select the source version and component inventory, producing inconsistent enforcement.
   Gain 4, Work 1, Harm 2
   Disposition: cut - the doc pins shadcn 4.21.4, nx and @nx/* 23.3.0, react and react-dom 19.3.0, react-router 8.4.0, @nestjs/* 12.1.2, vite 8.3.3 and prisma 7.10.0 (newest stable at least two weeks old in the npm registry), and both APP and GUARD take the component list from shadcn 4.21.4's registry.

5. Blocking: Unproven: item 2: the forgot-password route works in a browser.
   Raise: Test. Item 2 at `plans/FORGE-STARTER-1.md:46` requires browser tests to walk every listed route. The planned browser flows at lines 184-187 omit forgot-password; its only explicit check is that the router contains its path at lines 181-182. A route that crashes when opened satisfies those checks.
   Case: normal use - a signed-out user follows “Forgot password” from sign-in.
   Gain 3, Work 2, Harm 3
   Disposition: cut - test 2's browser walk now goes from the sign-in page's "Forgot password?" link to the forgot-password page, sends an email and sees the confirmation.

6. Blocking: The proposed packaging proof runs from source, so it cannot prove the installed starter exists.
   Raise: Test. `plans/FORGE-STARTER-1.md:285-287` says test 1 proves wheel dotfiles arrive, but lines 85 and 150-155 use the repository command harness. That harness explicitly loads checkout source (`tests/conftest.py:59-68`), rather than an installed wheel. Omitting starter files from the wheel would leave this proof green.
   Case: normal use - a client installs a released Forge wheel and runs `forge init --starter`.
   Gain 3, Work 2, Harm 3
   Disposition: cut - test 3's wheel case builds the wheel with uv build, as test_1 of tests/test_client_setup_and_migration.py already does, and checks every git-tracked starter file, dotfiles included, is in it.

7. Advisory: The offline setup promise contradicts the retained init path.
   Raise: Not done. `plans/FORGE-STARTER-1.md:39-41` promises offline setup. The new-repo path still pushes the first commit and configures GitHub protection (`src/forge/init.py:293-300`); the plan changes neither requirement. Local bare remotes and the GitHub stub hide this dependency.
   Case: normal use - an agent initializes a new GitHub-backed repository without network access.
   Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

8. Advisory: React Router is missing from the new moving-parts inventory.
   Raise: Moving part. `plans/FORGE-STARTER-1.md:20-21` replaces TanStack Router with React Router, which item 3 requires, but line 270 names only Nx and the smoke workflow. The current frontend convention names TanStack Router (`src/forge/templates/conventions/frontend.md:19`), so React Router is a newly introduced dependency.
   Gain 2, Work 1, Harm 1
   Disposition: keep - below the bar (live with)
