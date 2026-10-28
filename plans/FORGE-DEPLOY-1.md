# Client apps get a one-time deploy setup: dev first, production only by a person's Promote

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- An engineer asks the agent once to set up the deploys of a client app on Mainline, our deploy
  platform. That request is the deploy setup.
- In the setup, the agent follows the installed Mainline Deploy skill in this order: the engineer
  signs in in the browser with Google or GitHub, and the agent waits until the sign-in succeeds.
  Then the agent connects the repo, reads `services.toml` or writes it and gets the engineer's
  confirmation, sets the subdomain and the variables that `.env.example` names, and deploys dev.
  The agent always deploys dev first.
- After the setup, no agent deploys. Mainline deploys dev at each merge to main and a preview for
  each pull request.
- Production changes only when a person presses Promote in Mainline. An agent never deploys or
  promotes production, also when someone asks it to.
- The rule that an agent deploys only when a person asks for it stays as it is. The setup is that
  request.
- The agent's guide, the worker brief and the deploy guide get this text. A new repo gets it at
  `forge init`. An existing repo gets it on upgrade with `forge sync`, and no app file changes.

Design: none (no screens; guidance text only)

## Why

Today the guide tells the agent to deploy only on a person's request, and each deploy is a
separate agent run. The guide does not say how to set up deploys once, which environment comes
first, or who changes production. After a one-time setup, Mainline deploys dev and previews by
itself, so an agent deploy after the setup is extra work and a risk to production.

## Done when

1. **The agent's guide gives the one-time deploy setup in this order: browser sign-in with Google or GitHub and a wait until it succeeds, the repo connection, `services.toml` read or written with the engineer's confirmation, the subdomain, the variables that `.env.example` names, and dev first, always. The existing rule that an agent deploys only on an explicit request, and its test, stay unchanged, and the guide says that the setup is that request.**
2. **The agent's guide, the worker brief and the deploy guide say that after the setup Mainline deploys dev at each merge and a preview for each pull request, that production changes only when a person presses Promote in Mainline, and that an agent never deploys or promotes production.**
3. **A new repo from `forge init` gets this text at init, and an existing repo adopted on an earlier release gets it on upgrade with `forge sync`.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. The part reverts with its pull request.

Trade-off: Forge only tells the agent. It cannot stop an agent that deploys or presses Promote.
Mainline's own permissions decide who can promote production.

Trade-off: the automatic dev and preview deploys are Mainline's behaviour after the setup. This
story does not build them, and Forge does not check that they run.

Trade-off: the board, `forge next` and the pull request do not show deploy state, and a failed dev
deploy opens no fix. The owner cut these from this story.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

The new test file starts with `STORY = "FORGE-DEPLOY-1"`. Tests run the forge command and never
import forge.

This part waits for FORGE-SERVICES-1/SVCGUIDE: it changes the same three template files, and the
setup text refers to its `services.toml` paragraph. Write the new text after that part merges,
on top of its text.

### Done-when details

1. and 2. The guide text (DEPLOYSETUP).
   - `src/forge/templates/skill.md`: do not change the Mainline Deploy block at the top. Add this
     paragraph after SVCGUIDE's `services.toml` paragraph (the one that ends
     `so the list does not hold it.`), before the `| The human says | Run |` table:

     ```
     The first deployment that the owner asks for in a client repo is its deploy setup, and that
     request is the explicit request above. Follow the installed Mainline Deploy skill in this
     order, and skip a step that is already done:

     1. Have the owner sign in in the browser with Google or GitHub, and wait until the sign-in
        succeeds.
     2. Connect the client GitHub repository.
     3. Read `services.toml`. When the repo has none, write it as the paragraph above says and get
        the owner's confirmation.
     4. Set the main subdomain that the owner picks.
     5. Set each variable that `.env.example` names, with the values the owner gives, except the
        ones that the platform provides, such as `DATABASE_URL`.
     6. Deploy dev, and wait until dev reports healthy. Always deploy dev first.

     After the setup, do not deploy. Mainline deploys dev at each merge to the default branch and
     a preview for each pull request. These deploys are Mainline's, not an agent's, and need no
     request. Production changes only when a person presses Promote in Mainline. Never deploy or
     promote production, also when the owner asks: tell them to press Promote in Mainline. When
     the owner asks for another deployment after the setup, tell them that Mainline deploys dev at
     the next merge.
     ```

     The prototype text that starts ``When `forge next` says to connect the repo`` does not
     change: its `use Mainline Deploy as above` now includes the setup.
   - `src/forge/templates/brief.md`: do not change the Mainline Deploy block. Add this paragraph
     after its last line (`"deploy this to staging" or "publish this on Mainline" needs no separate routine deployment approval.`),
     before `$review_loop`:

     ```
     A worker never deploys. After a client repo's one-time deploy setup, Mainline deploys dev at
     each merge to the default branch and a preview for each pull request, and production changes
     only when a person presses Promote in Mainline. Never deploy or promote production.
     ```
   - `src/forge/templates/conventions/deploy.md`: do not change the Mainline Deploy paragraph.
     Add this paragraph after SVCGUIDE's line `Keep one instance running while migrations are made.`:

     ```
     The first deployment that the owner asks for is the deploy setup, once for each repository:
     browser sign-in with Google or GitHub, then the repository, `services.toml`, the main
     subdomain, the variables that `.env.example` names, and dev first. After the setup, Mainline
     deploys dev at each merge to the default branch and a preview for each pull request.
     Production changes only when a person presses Promote in Mainline. An agent does not run
     these deploys, and an agent never deploys or promotes production.
     ```
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
3. New and existing repos (DEPLOYSETUP).
   - Test: `tests/test_deploy_setup_guide.py::test_1_the_guides_give_the_one_time_deploy_setup`,
     `@pytest.mark.platform`, parametrised `new init` and `previous release`, with the setup of
     `tests/test_services_guide.py::test_3`: `install_claude(repo)`; `new init` uses
     `_fresh_client(repo, gh, tmp_path)`; `previous release` copies
     `tests/fixtures/adopted-v1.2.2/client`, moves `forge.toml` to this release, commits and
     pushes; then `forge fix start "Check deploy setup guidance" --done "The deploy setup guidance is delivered" --kind mechanical`,
     `workers = "claude"` in the fix's forge.toml, `forge sync` in the `previous release` case,
     a commit, and `forge work check-deploy-setup-guidance`. Compare text with whitespace
     collapsed (`" ".join(text.split())`).
     - The synced `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`, in the part
       before `| The human says |`, have: `is its deploy setup, and that request is the explicit request above`,
       `sign in in the browser with Google or GitHub, and wait until the sign-in succeeds`,
       `Connect the client GitHub repository`, `get the owner's confirmation`,
       ``Set each variable that `.env.example` names``, `Always deploy dev first`,
       `After the setup, do not deploy`,
       `Mainline deploys dev at each merge to the default branch and a preview for each pull request`,
       `Production changes only when a person presses Promote in Mainline`,
       `Never deploy or promote production`. The sign-in phrase comes before
       `Connect the client GitHub repository`, which comes before `Always deploy dev first`.
     - The worker brief (`calls(log)[-1]["brief"]`) has `A worker never deploys`,
       `Production changes only when a person presses Promote in Mainline` and
       `Never deploy or promote production`.
     - `ROOT / "src/forge/templates/conventions/deploy.md"` has `is the deploy setup, once for each repository`,
       `and dev first` and `an agent never deploys or promotes production`.
   - `tests/test_deployment_requires_an_explicit_request.py` and `tests/test_services_guide.py`
     keep passing unchanged. A change to either one is a sign that the existing text changed.

### New and existing repos

- **New repos** (`forge init`, with or without a starter): the guide paragraph arrives with init,
  and the brief and the deploy guide with the release. No app file changes.
- **Existing repos** (on upgrade to this release, after `forge sync`): the guide paragraph arrives
  with sync, and the brief and the deploy guide with the release. No app file changes. A repo that
  Mainline already deploys skips the setup steps that are already done, as the guide says. Tested
  on the adopted earlier-release fixture in item 3.

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
| DEPLOYSETUP | The one-time deploy setup in the guides | The setup steps and the after-setup rules in the agent's guide, the worker brief paragraph, the deploy guide paragraph and the synced skill copies, on new and existing repos | 1, 2, 3 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `src/forge/templates/conventions/deploy.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_deploy_setup_guide.py` (new) | `tests/test_deploy_setup_guide.py::test_1` (new) | FORGE-SERVICES-1/SVCGUIDE | no | |

New moving parts: none

## Notes

- Owner decisions (26 Oct 2026, settled): an engineer asks the agent once to set up deploys on
  Mainline, a separate product that Forge does not build; the agent follows the installed Mainline
  Deploy skill: browser sign-in with Google or GitHub and a wait for success, the repo connection,
  `services.toml` read or written with the engineer's confirmation, the subdomain, the
  `.env.example` variables, and dev first, always; after the setup Mainline deploys dev at each
  merge and a preview for each pull request; the agent never deploys or promotes production, and
  production changes only when a person presses Promote; the explicit-request rule and its test
  stay, and the setup is that request.
- Owner cut (26 Oct 2026): one part, guidance only. Deploy state on the board, in `forge next` and
  in the pull request, reading GitHub deployments, and a fix for a failed dev deploy are out of
  this story.
- Planner choices the owner did not make: (1) the guide says to skip a setup step that is already
  done, so an existing repo that Mainline already deploys does not connect again; (2) when the
  owner asks for production, the agent tells them to press Promote in Mainline; when the owner
  asks for another deploy after the setup, the agent says that dev deploys at the next merge;
  (3) the agent sets each `.env.example` variable except the ones the platform provides, such as
  `DATABASE_URL`; (4) the worker brief gets one short paragraph, because workers have no user who
  can ask for a deploy.
