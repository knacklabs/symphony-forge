# Client apps can deploy several services from one repo

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Each app repo can keep one small file, `services.toml`, that lists the services our deploy
  platform runs from it. Each service has a name, a Dockerfile path, a port, a health path and one
  exposure: public at the app's main address, public at its own subdomain (named by a prefix such
  as `api`), or internal only, such as a worker. A service can also name its own start command.
- A new app from either starter, or from `forge init` with Forge's Dockerfile, lists one service:
  the root Dockerfile on port 3000 with `GET /health`, public at the main address.
- When Forge adopts an existing app, the agent writes the list from the app's Dockerfiles and asks
  you to confirm it.
- Close stops a change when the list names a Dockerfile that is not in the repo, or when the list
  does not have exactly one service at the main address.
- The deploy guide names the list. You still pick the main subdomain on the platform at the first
  deploy, so the list does not hold it.
- An existing app gets no list on upgrade, and no app file changes. Before the next deploy that you
  ask for, the agent writes the list from the Dockerfiles and asks you to confirm it.
- The planned background-jobs story can use a service's start command to run the same image as a
  worker. This story does not build that.

Design: none (no screens; it adds one file to client repos, one close check and guide text)

## Why

The deploy guide and both starters describe one root Dockerfile, port 3000 and `GET /health`. An
app with an API, a web app and a worker has no way to tell the platform about its other services.
The platform could guess from the Dockerfiles, but a guess can put a worker on the internet or miss
a service. A list that the agent writes, the owner confirms and close checks gives the platform one
fact to read.

## Done when

1. **A new app from `forge init --starter`, `forge init --starter python`, or `forge init` that writes Forge's Dockerfile has `services.toml` in its first commit, with one service: the root Dockerfile, port 3000, health path `/health`, public at the main address.**
2. **Close refuses a change whose `services.toml` is not valid TOML, names a Dockerfile that the branch does not have, or does not have exactly one service public at the main address. The refusal names the problem and the next step. A list with a main service, a service at its own subdomain and an internal service with its own start command passes. A repo with no `services.toml` closes as today.**
3. **The deploy guide, the agent's guide and the worker brief name the list. The agent's guide says to write the list from the Dockerfiles at adoption and before the first requested deployment of a repo without one, and to get the owner's confirmation. A new repo gets this at init. An existing repo gets it on upgrade with `forge sync`, and gets no `services.toml`.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request.

Trade-off: close checks only that each named Dockerfile is in the repo and that one service is at
the main address. It does not check ports, health paths, start commands, or that every Dockerfile
is in the list. A wrong port shows at the deploy.

Trade-off: an existing app has no list until its agent writes one before the next deploy that you
ask for. Until then, the platform deploys it as it does today.

Trade-off: a service's start command is one shell line. The jobs story decides how a worker gets
its role.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-SERVICES-1"`. Tests run the forge command and never
import forge; reading a file with `tomllib` is fine.

### Why one root file

The list is `services.toml` at the repo root, next to the root Dockerfile.

- It is the app's deploy description, not a Forge setting. forge.toml is Forge's file: its strict
  key check in `repo._config_problem` would stop every forge command on a bad service entry, and
  the platform would have to read Forge's version pin and models table to find the services.
- A fixed root path needs no lookup on the platform side, and the agent edits it in the same
  change as a Dockerfile.
- It reaches every new app through the docs skeleton (`src/forge/templates/skeleton/`), so the
  starters need no copy of their own.

### The format (pinned by SVCLIST)

`src/forge/templates/skeleton/services.toml`, exactly:

```toml
# The services our deploy platform runs from this repo. One release builds them all.
# expose: "main" serves the app's main address (exactly one service), "subdomain" serves its own
# subdomain named by its subdomain prefix (for example subdomain = "api"), and "internal" has no
# address (for example a worker; it needs no port or health). command, when set, replaces the
# Dockerfile's start command.

[[service]]
name = "app"
dockerfile = "Dockerfile"
port = 3000
health = "/health"
expose = "main"
```

Fields: `name`, `dockerfile` (a repo-relative path), `port`, `health`, `expose` (`main`,
`subdomain` or `internal`), and the optional `subdomain` (a prefix) and `command` (one shell line).
The main subdomain is not in the list: the owner picks it on the platform. Do not add `APP_ROLE`
or a `role` field; the jobs story decides that.

### Done-when details

1. New apps list one main service (SVCLIST).
   - `src/forge/init.py`, `_scaffold`: add `"services.toml"` to the names that go with the
     Dockerfile, so the filter reads
     `path.name not in ("Dockerfile", ".dockerignore", "services.toml")`. A starter init and a
     plain init on a Node or empty repo get the file; a plain init on another stack gets no
     Dockerfile and no list. `_adopt` does not change: the agent writes the list (item 3).
   - Init writes the list only beside a Dockerfile that it writes itself. `init` keeps a file
     that is already there, so in `init`, before the write loop, add
     `if (top / "Dockerfile").exists(): scaffold.pop("services.toml", None)`. The popped path then
     also stays out of the first commit. A repo whose own Dockerfile was there before init gets
     no list; the agent writes one from that Dockerfile before the first requested deployment
     (item 3). A starter init already refuses a repo that has a Dockerfile (`starter_app`).
     Both starters already `EXPOSE 3000` and answer `GET /health`, so the skeleton file is true
     for them.
   - Test: `tests/test_services_list.py::test_1_new_apps_list_one_main_service`, parametrised
     `react`, `python` (`_fresh_client(repo, gh, tmp_path, "--starter", kind)` from
     `tests/test_setup.py`, as `tests/test_database_starters.py` does) and `plain`
     (`_fresh_client` with no starter). Each: `tomllib.loads` of `services.toml` gives
     `{"service": [{"name": "app", "dockerfile": "Dockerfile", "port": 3000, "health": "/health", "expose": "main"}]}`,
     the root Dockerfile has `EXPOSE 3000`, and `git ls-files` lists `services.toml`. A fourth
     case, `plain-own-dockerfile`, writes `package.json` (`{}`) and a Dockerfile with
     `EXPOSE 8080` before `forge init`: after init the Dockerfile is unchanged and the repo has no
     `services.toml`.
   - Change existing tests for the same scaffold rule: `tests/test_setup.py` `SCAFFOLD` gets
     `"services.toml"`; `tests/test_client_setup_matches_stack.py::test_1` loops over
     `("Dockerfile", ".dockerignore", "services.toml")`, so a non-Node repo proves it gets no list.
2. Close checks the list (SVCLIST).
   - `src/forge/app_baseline.py` (72 lines; it already holds close's client-app check) gets
     `services(top, cfg)`, and its module docstring names it. `src/forge/close.py` calls
     `app_baseline.services(top, cfg)` on the line after `app_baseline.check(...)`.
   - It returns when `cfg.get("repo") != "client"` or `git ls-tree` of `HEAD` has no
     `services.toml`. It reads the file with `git show HEAD:services.toml` and the paths from the
     same `ls-tree -r --name-only -z HEAD` listing, as `check` does, so it checks what is
     committed.
   - One refusal, `REFUSALS["services"] = ("services.toml {problem}.", "fix services.toml to match the Dockerfiles, then forge close {item}")`,
     with `item` as `check` finds it. Problems, in the order of the services in the file, joined
     with `; ` when there are several:
     - `is not valid TOML: <tomllib's message>` (then stop);
     - `has a service with no dockerfile` for a service without a `dockerfile` string, and
       `names <path>, which this branch does not have` for a service whose `dockerfile` is not in
       the listing;
     - `has <n> services with expose = "main"; it needs exactly one`, when the count is not 1.
       A `service` key that is not a list counts as no services.
   - Mark it with a `ponytail:` comment: no port, health, command or subdomain checks; add one
     when a deploy shows the need.
   - Test: `tests/test_services_list.py::test_2_close_checks_the_list_against_its_dockerfiles`,
     parametrised `new-client` and `adopted-v1.2.2` with `_client_repo` from
     `tests/test_score_notes.py` and `env.start` / `env.close` as in
     `tests/test_shadcn_only.py`, with a clean review (`CLEAN`, `GREEN`).
     - New client, one fix, in order: (a) commit `apps/api/Dockerfile`, `worker/Dockerfile` and a
       list with `app` (main), `api` (`expose = "subdomain"`, `subdomain = "api"`, port 3000,
       `/health`) and `worker` (`expose = "internal"`, `command = "exec node worker.js"`, no port
       or health): close does not refuse on the list. (b) remove the `dockerfile` line of `api`
       and delete `worker/Dockerfile`: close exits 1 with
       `services.toml has a service with no dockerfile; names worker/Dockerfile, which this branch does not have.`
       and the Next line. (c) restore both and set `expose = "main"` on `api`: close refuses with
       `has 2 services with expose = "main"; it needs exactly one`. (d) write `[[service]` as the
       file: close refuses with `is not valid TOML:`.
     - Adopted client (the fixture has no `services.toml`): a fix that changes an ordinary file
       closes with no services refusal. This is the only path that differs for an existing repo.
3. The guides name the list (SVCGUIDE).
   - `src/forge/templates/conventions/deploy.md`: replace the two sentences
     ``Our platform builds the repository's root Dockerfile and provides Postgres through `DATABASE_URL`.``
     and
     ``The platform routes traffic to container port 3000 and checks `GET /health` for HTTP 200.``
     with:
     "`services.toml` at the repo root lists the services our platform runs from this repository.
     Each `[[service]]` has a `name`, a `dockerfile` path, a container `port`, a `health` path that
     answers HTTP 200 when the service is ready, and an `expose` value: `main` for the app's main
     address, `subdomain` for its own subdomain, named by its `subdomain` prefix (for example
     `api`), or `internal` for a service with no address, such as a worker, which needs no port or
     health path. An optional `command` replaces the Dockerfile's start command. Exactly one
     service is `main`. One release builds every service, and a rollback rolls them all back. The
     platform provides Postgres through `DATABASE_URL`. Forge's starters list one `main` service:
     the root Dockerfile on port 3000 with `GET /health`."
     Keep the sentence about the Mainline Deploy skill, and change its end to
     "choose its main subdomain; the list does not hold it." The rest of the page stays.
   - `src/forge/templates/skill.md`: a new paragraph after the Mainline Deploy block at the top
     (after the line that ends `needs no separate routine deployment approval.`, before the table):
     "Our deploy platform reads `services.toml` at the repo root: one `[[service]]` per service,
     with `name`, `dockerfile`, `port`, `health`, `expose` (`main`, `subdomain` or `internal`) and,
     when needed, `subdomain` and `command`; deploy.md in Forge's conventions has the details.
     Close refuses a list that names a Dockerfile the branch does not have or does not have
     exactly one `main` service. When a client repo has a Dockerfile and no `services.toml`, write
     it before the first deployment the owner asks for: one service per Dockerfile the app runs,
     the port from its `EXPOSE` line and the health path from the code. Show it to the owner and
     ask with options: confirm it, or change a service's exposure. Then merge it in a fix. The
     owner picks the main subdomain on the platform, so the list does not hold it."
     And in `## Adopt a live app`, a new last step after step 9:
     "10. When the repo has a Dockerfile, write `services.toml` as the deploy paragraph at the top
     of this guide says, get the human's confirmation, and add it to the adoption fix."
   - `src/forge/templates/brief.md`, after the line
     `conventions apply only to a repo on the default stack.`:
     "In a repo that has `services.toml`, when a change adds, moves or removes a Dockerfile, or
     changes a service's port, health path or start command, update `services.toml` in the same
     change. Close refuses a `services.toml` that names a Dockerfile the branch does not have, or
     that does not have exactly one service with `expose = \"main\"`. In a repo without
     `services.toml`, do not create one: the coordinator writes the first list with the owner's
     confirmation."
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - Test: `tests/test_services_guide.py::test_3_the_guides_name_the_services_list`, parametrised
     `new init` and `previous release` (the `tests/fixtures/adopted-v1.2.2/client` repo moved to
     this release and synced), following
     `tests/test_deployment_requires_an_explicit_request.py::test_1`: the synced
     `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` have the top paragraph's
     write-and-confirm sentence and step 10; the worker brief from `forge work` (`install_claude`,
     `calls(log)[-1]["brief"]`) has both brief sentences, the update rule and `do not create one`; the installed deploy.md has
     `services.toml` and the three `expose` values. Previous release: after `forge sync`, the repo
     has no `services.toml`.

### New and existing repos

- **New repos** (`forge init --starter`, `forge init --starter python`, and plain `forge init` on
  a Node or empty repo): `services.toml` with one main service in the first commit, the close
  check, and the guide, brief and deploy guide text. A plain init on another stack gets no
  Dockerfile and no list; the agent writes the list when the repo gets a Dockerfile and a deploy
  is asked for. A newly adopted app (`forge init` on a repo with history) gets the list from the
  agent at adoption (step 10).
- **Existing repos** (on upgrade to this release, after `forge sync`): no `services.toml` and no
  app file change. Sync writes no list: a default could state a wrong port or miss a service, and
  sync would need a new write-once kind of file. Close skips the check while the repo has no list.
  The guide paragraph arrives with sync, and the brief and deploy guide with the release, so the
  agent writes the list before the next requested deploy. Tested on the adopted earlier-release
  fixture in items 2 and 3.

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
| SVCLIST | The services list and its close check | The skeleton `services.toml`, its place in the first commit beside the Dockerfile, and close's check of the list against the committed Dockerfiles, on new and existing repos | 1, 2 | `src/forge/templates/skeleton/services.toml` (new), `src/forge/init.py` (`_scaffold` only), `src/forge/app_baseline.py`, `src/forge/close.py` (one call), `tests/test_services_list.py` (new), `tests/test_setup.py` (`SCAFFOLD`), `tests/test_client_setup_matches_stack.py` (`test_1`) | `tests/test_services_list.py` (`test_1`, `test_2`); the changed `SCAFFOLD` and `test_client_setup_matches_stack.py::test_1` | | no | |
| SVCGUIDE | The guides name the services list | The deploy guide's list paragraph, the agent guide's paragraph and adoption step, the worker brief sentence and the synced skill copies, on new and existing repos | 3 | `src/forge/templates/conventions/deploy.md`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_services_guide.py` (new) | `tests/test_services_guide.py::test_3` (new) | | no | |

The two parts share no file. SVCLIST pins the file format above; SVCGUIDE's text uses the same
names and needs no SVCLIST code, so both can run at the same time.

New moving parts: none

## Notes

- Owner decisions (26 Oct 2026, settled): a client repo keeps a services list that Forge writes and
  our deploy platform reads, not a platform guess from Dockerfiles; each service has a name, a
  Dockerfile path, a role or start command, a port, a health path and one of three exposures; new
  apps from both starters list one public service on port 3000 with `GET /health`; at adoption the
  agent writes the list from the Dockerfiles and confirms it with the owner; the deploy guide
  names the list; the jobs story's `APP_ROLE` is not built here.
- Platform decisions (Mainline, a separate product; context only): the customer picks the main
  subdomain at the first deploy and can change it; one release builds every service and a
  rollback rolls them all back.
- Planner choices the owner did not make: (1) the list is `services.toml` at the repo root, not a
  table in forge.toml, so a bad entry does not stop every forge command and the platform reads no
  Forge settings; (2) the role is held as an optional `command`, one shell line that replaces the
  Dockerfile's start command, with no `role` field; (3) close checks only that the file parses,
  that each named Dockerfile is committed, and that exactly one service is `main`; (4) on upgrade,
  sync writes no list, and the agent writes one before the next requested deploy; (5) plain
  `forge init` gets the list wherever it writes Forge's Dockerfile, because that Dockerfile has
  the same port and health path.
- Assumption for the platform side: an app with no `services.toml` deploys as today (the root
  Dockerfile as one public service on port 3000 with `GET /health`).
