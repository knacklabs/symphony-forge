# Agents teach the seven-step journey to new users

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- The shipped guide has one journey with seven steps: ideas and client notes, brief, canvas design, sign-off, build, deploy on Mainline, and run and improve. Each step has one sentence that says what happens and one plain sentence that you can say to the agent.
- The guide also explains the loops in one short paragraph each: the cold read of a plan, build and review, and the CI checks. Each paragraph says why the loop exists.
- The README journey section has the same seven steps and loops. It replaces the ten-stage table.
- After `forge init`, the agent explains the seven steps and asks for the first input: the client notes or the idea.
- Each `forge next` starts with one line that names the repo's current step, for example "Step 3 of 7: canvas design."
- For each running item, `forge next` adds one plain line that says what the item waits on, why, and for how long. For example: "Review round 2: 2 problems found (export ignores filters; focus on empty link). The worker is fixing them, 6 minutes so far."
- When you ask what you can do, or seem unsure, the agent shows the phrases for the current step.
- When Forge refuses something, the agent tells you the reason and the fix in plain words. When the refusal looks like a Forge fault, the agent offers to file a Forge bug.
- A new repo gets all of this at init. An existing repo gets the guide text with `forge sync` after the upgrade, and the step and wait lines with the new release.

Design: none (no screens; guide text and two kinds of `forge next` line)

## Why

New users learn the journey from the owner. The repo has no single journey: the README has a ten-stage table, the guide's Prototype section tells a different route, and `forge next` shows each item's stage but not the stage of the whole repo. When a loop takes a long time, nobody can see what it waits on, so people ask the owner or stop the work.

## Done when

1. **The shipped guide has one journey section with the seven steps in order. Each step has one sentence of what happens and one sentence that the person can say. The section has one short paragraph each for the cold read loop, the build and review loop, and the CI checks, and each paragraph says why the loop exists. The README journey section lists the same seven steps and loops and no longer has the ten-stage table. A new repo gets the guide at init, and an existing repo gets it with `forge sync`.**
2. **The guide tells the agent to explain the seven steps after `forge init` and ask for the client notes or the idea. It tells the agent to show the current step's phrases when a person asks what they can do or seems unsure. It tells the agent to explain each refusal's reason and fix in plain words, and to offer to file a Forge bug with the existing bug template when the refusal looks like a Forge fault. `forge init` prints the same first instruction before its next step. The worker brief tells workers to report each refusal's reason and fix in plain words.**
3. **Each `forge next` starts with one line, "Step N of 7: <step>.", taken from facts that Forge already has. Forge's own repo shows step 5. A repo past sign-off with work in progress shows step 5. The `--json` view and the board do not change.**
4. **For each running item, `forge next` prints one plain line directly under the item's status line. The line says what the item waits on, why, and for how long. It covers a worker that builds it, a review round with its problems, a Codex capacity retry until its retry time, queued or running CI checks, and a cold read round with its notes or its running reader. Rounds that run as subagents of the agent's own session get the same line. It uses only facts that Forge already records. An item that waits on nothing gets no line.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request.

Trade-off: the step comes from the default branch as last fetched. Work on a branch that has not merged does not move the step. Work counts as in progress while forge next lists any story or fix; when it says nothing is in progress, the repo moves past step 5.

Trade-off: the deploy step uses the demo address in the brief as the sign that the app runs on Mainline. An adopted live app never shows step 6, because it already runs somewhere.

Trade-off: Forge shows a rate-limit retry only for Codex turns. Forge records no Claude rate-limit retries.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-JOURNEY-1"`. Tests run the forge command and never import forge. A test can read files. Set the clock with `FORGE_NOW` (`repo.now`).

### The step names (pinned by both parts)

The step names, exactly and in this order: `ideas and client notes`, `brief`, `canvas design`, `sign-off`, `build`, `deploy on Mainline`, `run and improve`. The guide's step headings and the `forge next` line use these words. The two parts share no code, only these strings.

### Done-when details

1. The journey in the guide and the README (JOURNEY-GUIDE).
   - `src/forge/templates/skill.md`: add a new section `## The journey` after the paragraph that ends `...a question of fact gets neutral choices.` (line 117) and before `## Save decisions and ideas`. Its text:

     "Every client repo moves through seven steps. `forge next` names the current step in its first line.

     1. **Ideas and client notes.** The person gives you the client notes or an idea. Put each note in `docs/context/` and read them all before you ask anything. You can say: "Here are the client notes" or "I have an idea: <idea>".
     2. **Brief.** You write `docs/product/BRIEF.md` from the notes, and ask only about a point that changes a screen, a field or a flow. You can say: "The brief looks right" or "Change this in the brief: <change>".
     3. **Canvas design.** You make the screens on a design canvas, which the client can click through in Play mode, and the owner or FDE approves the canvas. You can say: "Show me the screens" or "Change this screen: <change>".
     4. **Sign-off.** The client's named person approves the canvas and the answers, and the owner chooses Build now or Later. You can say: "The client approved it; build now" or "The client approved it; build it later".
     5. **Build.** You plan stories and fixes, build each one with its tests and a review, and merge it. You can say: "Build this next: <idea>" or "What is ready to merge?".
     6. **Deploy on Mainline.** When the person asks, you set up Mainline and deploy dev. A person presses Promote in Mainline for production. You can say: "Deploy this on Mainline".
     7. **Run and improve.** People use the app, and each new request or problem goes back to step 5. You can say: "Users asked for <request>" or "This is broken: <problem>".

     **The cold read loop.** A reader who did not write the plan reads it cold and lists its gaps. You fix the plan, and the reader reads it again. After two rounds that still have open notes, Forge stops and the owner chooses: accept, read again, or split. It exists because a gap found in the plan costs minutes, but the same gap found in the code costs a build round.

     **The build and review loop.** A worker builds the part and its tests, then a separate review checks the change. A serious problem goes back to the worker for another round. A task gets two review rounds and a fix gets one. At the limit Forge stops and asks the owner, but a P0 problem keeps the loop going. It exists because a reviewer sees problems that the worker cannot see in its own work.

     **The CI checks.** GitHub runs the repo's checks on the pull request. Close waits while they are queued or running, and a red check goes back to the worker. They exist because the checks run the tests on a clean machine, the same way for every change.

     `forge next` adds one line under each running item that says what it waits on, why and for how long. Give that line to the person when they ask why something takes time.

     After `forge init` in a new repo, tell the person the seven steps in one line each, then ask for the first input: the client notes or the idea.

     When a person asks what they can do, or seems unsure, run `forge next`, name the current step from its first line, and show that step's "You can say" phrases. Name no commands.

     When a Forge command refuses, tell the person in plain words what Forge stopped, why, and the fix that it names. Then do the fix, or ask the choice. When the refusal looks like a Forge fault (a wrong or confusing message, a refusal of a correct step, a crash, or a success that did nothing), say so and offer to file a Forge bug as Reporting a Forge bug, below, says. File it when the person agrees.

     Before sign-off FORGE-SIGNOFF-1 adds Build now and Later; until then, record "build it later" with `forge start "Do this later: <the first story's idea>"`."

     Leave out the last paragraph if FORGE-SIGNOFF-1 has merged when this part starts. Make the step 4 sentence use that story's words.
   - `README.md`, `## From idea to production` (line 175): replace the table (lines 183 to 194) with the same seven numbered steps, each with its what-happens sentence and its "You can say" sentence, written to the reader ("you give the agent..."). Then add the three loop paragraphs. Keep the intro paragraph, its checklist link, and the paragraph after the table.
   - Test: `tests/test_journey_guide.py::test_1_the_guide_and_readme_teach_the_seven_steps`, parametrised `new init` (`_fresh_client` from `tests/test_setup.py`) and `previous release` (`tests/fixtures/adopted-v1.2.2/client` moved to this release, then `forge sync`, as `tests/test_services_guide.py::test_3` does). In both, the synced `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` have `## The journey`, the seven step names in order as bold headings, a `You can say:` sentence on each step, and the three loop headings each with an `It exists because` / `They exist because` sentence. The `new init` case also reads `ROOT/README.md` and checks that the `## From idea to production` section lists the same seven step names in the same order and has no `| Stage |` row.
2. The agent's first steps, the unsure case and refusals (JOURNEY-GUIDE).
   - The guide paragraphs above cover the after-init, unsure and refusal rules.
   - `src/forge/init.py`, `init`: before `print("Next: forge next")` (line 362), print `Tell the person the seven steps in the Forge guide's journey, then ask for the client notes or the idea.` `_adopt` does not change, because an adopted repo is live and does not start at step 1.
   - `src/forge/templates/brief.md`, under `## When you finish`, after the paragraph that ends `Report the work done only when every item you cover is.`, add: "When a forge command refuses, say in your last message what it refused, why, and the fix it named, in plain words. Say so when the refusal looks like a fault in Forge itself."
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` in this repo.
   - Test: `tests/test_journey_guide.py::test_2_the_agent_explains_the_steps_and_refusals`, parametrised `new init` and `previous release` as in test 1. Both: the synced guide has the after-init sentence, the "seems unsure" sentence and the refusal sentence with `offer to file a Forge bug`. The worker brief from `forge work` (`install_claude`, `calls(log)[-1]["brief"]` from `tests/test_worker.py`) has the refusal sentence. `new init`: the init stdout has the tell-the-person line directly before `Next: forge next`.
3. The step line (JOURNEY-NEXT).
   - New module `src/forge/journey.py`, because `src/forge/board.py` is at the 1,200-line ceiling and `src/forge/nextstep.py` is at 1,101 lines. It holds `STEPS` (the pinned names), `step_line(top, cfg, history=None) -> str` and `wait_line(...)` (item 4).
   - The rule, where the first match wins. `ref = story.landed_ref(top)`, and every file is read at `ref`:
     1. `cfg["repo"] == "forge-source"`: step 5.
     2. `repo.is_prototype(top, cfg, (ref,))` (a client prototype without an accepted sign-off):
        - `docs/context/` has no file at `ref` and the brief's `## Summary` is empty: step 1.
        - `## Summary` or `## Things it keeps track of` is empty: step 2.
        - `design.require_prototype(top, ref)` raises `repo.Refused`: step 3.
        - Otherwise: step 4.

        Read the sections with `records._sections` after you remove the HTML comments, as `records._signoff_design` does.
     3. `forge next` lists work (its lines are not `_idle(top)`'s "No story or fix is in progress."), or no story on `ref` has status `done`: step 5. `next_step` and `context_hook` pass `idle = _idle(top)[0] in lines` from their own `_report` result. A story that is done is already left out of `_report`, so a planning worktree that stays after the last merge does not hold step 5. Use `history["stories"]` when `next_step` has it, else `story.completed(top, key, ref)` for each `.factory/stories/<KEY>/story.json` on `ref`.
     4. `cfg["stage"] == "prototype"` and the brief at `ref` has no `- Address: https?://...` line under `## Demo` (the regex in `nextstep._needs_demo_address`): step 6.
     5. Otherwise: step 7.

     The line is `f"Step {n} of 7: {STEPS[n - 1]}."`. A repo with no `forge.toml` gets no line. Mark the rule with a `ponytail:` comment: "in progress" is forge next's own idle line, so the step follows what next lists.
   - `nextstep.next_step`: in the text path only, print the step line before `notice`: `print("\n".join([journey.step_line(...)] + notice + lines))`. `nextstep.context_hook` prints it first too. `machine_next`, `--json`, `handoff_hook` and the board do not change.
   - Change existing tests that check the first line of `forge next`: `tests/test_discovery.py` line 85 and `tests/test_retire_a_replaced_roadmap_item.py` line 165, and any others that the suite shows. They read the second line instead.
   - Test: `tests/test_journey_next.py::test_3_forge_next_names_the_journey_step`.
     - New client (`_fresh_client`). Commit and push each change on `main` with `repo.git`, then run `forge next` after each one:
       - (a) fresh: the first line is `Step 1 of 7: ideas and client notes.`
       - (b) `docs/context/notes.md`: step 2.
       - (c) a filled Summary and Things it keeps track of: step 3.
       - (d) `PRODUCT.md`, a PNG in `docs/design/prototype/`, and `docs/decisions/0001-prototype-design.md` with `status: accepted` and `design_tree: <git rev-parse HEAD:docs/design/prototype>`: step 4.
       - (e) `docs/decisions/0002-client-signoff.md` with `status: accepted`: step 5.
       - (f) `forge story new` for one story (its planning worktree stays), then its state with `status: done` committed on `main`, as the last task's merge records it: step 6.
       - (g) `## Demo` with `- Address: https://demo.example`: step 7.
       - `forge next --json`'s `next.line` does not start with `Step `.
     - Forge's own repo (the `repo` fixture with `repo = "forge-source"`): step 5.
     - Adopted client (`adopted-v1.2.2`, moved to this release): step 5, because no story is done.
4. The wait line (JOURNEY-NEXT).
   - `journey.wait_line(top, item, state, started, pr, checks, kind) -> str | None`. `started` is the live run's start time: the `at` of the live run from `board.active_runs(top, item, round_number=state.get("round"))`, or, for a round handed to a session subagent, the `started_at` (else `joined_at`) of the `machine.entries()` entry that `nextstep._native_round` matches. `kind` is `build` or `read`. The first case that holds gives the line:
     1. Codex capacity: the latest progress event of the live work run has a `retry_at` later than now. Line: `Codex is at capacity; Forge sends the turn again at {HH:MM}.`
     2. `review.blocking(state["review"])` is not empty. Line: `Review round {n}: {k} problems found ({titles}).`, and when a work run is live, add ` The worker is fixing them, {elapsed} so far.`
     3. A work run is live. Line: `The worker is building it, {elapsed} so far.`
     4. `checks == "running"`. If every unfinished check in `board._rollup(pr)` is `QUEUED`, `WAITING`, `PENDING` or `REQUESTED`, the line is `Waiting for a CI runner: queued {elapsed}.` Otherwise it is `CI checks are running, {elapsed} so far.` `elapsed` is from the earliest `startedAt` (or `createdAt`) among those checks, as `board.machine_board` reads it. Leave out the time when there is none.
     5. Otherwise `None`.

     Definitions: `n` is the number of `review` steps in `state["steps"]`, as `close.py` counts them. `titles` are the first three blocking titles joined with `; `, then `and {m} more` when there are more. `elapsed` is `time_records.plain(now - started)`.
   - `nextstep._item`: put the wait line between the status sentence and the `Next:` line on the last return (the generic status sentence). When `_native_round(top, item, label, "Build")` returns its two lines, put the wait line between them too. The hotspot, question, ready, merged and other-machine paths do not change. `machine_next` reads the first line that is not a `Next:` line, so the board's `next.line` and `waits_on` do not change.
   - Story reads, in `nextstep._story`. When `_native_round(top, key, title, "Grill")` holds a round, or a read run is live, add `Cold read round {r + 1} is running, {elapsed} so far.` under the first line. `r` is the notes' `round` (0 when there is none), and `elapsed` is from the same `started`. In `_next_round`, in the branch that says the round had findings, put `Cold read round {done} of 2: {k} notes to answer.` between the two lines. `k` is the number of findings in the latest round (`story._latest(record, findings)`).
   - `src/forge/codex.py`, in the `"retry" in said` branch (line 712): when `ran.get("run_id")` is set, also call `repo.record_progress(checkout, item, ran["run_id"], retry_at=<now plus said["retry"] seconds, ISO UTC>)`. This adds no new record: it is a field on the run's progress event. After the retry time the line goes away by itself, so no clearing update is needed.
   - Mark the function with a `ponytail:` comment: no machine-queue, test-progress or Claude rate-limit case; add one when people ask why such a wait takes time.
   - Test: `tests/test_journey_next.py::test_4_forge_next_says_what_each_running_item_waits_on`. Follow `tests/test_fix_forge_next_says_a_worker_is_building_ite.py` and `tests/test_worker_liveness_controls_next_step.py` for a live run. Follow `tests/test_fix_a_codex_turn_that_fails_because_the_mode.py` and `tests/stubs/codex-app-server` for a capacity retry. Set the clock with `FORGE_NOW`.
     - New client, one fix each:
       - (a) a blocked review with two titles and a live work run started 6 minutes ago: `Review round 1: 2 problems found (A; B). The worker is fixing them, 6 minutes so far.`
       - (b) a pull request whose rollup has one `QUEUED` check that started 12 minutes ago: `Waiting for a CI runner: queued 12 minutes.` Then the same check `IN_PROGRESS`: `CI checks are running, 12 minutes so far.`
       - (c) a capacity retry from the Codex stub during `forge work`: while `FORGE_NOW` is before the retry time, the line starts with `Codex is at capacity; Forge sends the turn again at`. With `FORGE_NOW` after it, there is no capacity line.
       - (d) a story with round 1 notes that have three findings: `Cold read round 1 of 2: 3 notes to answer.`
       - (e) a fix whose round is held by a session subagent (as in `tests/test_worker_liveness_controls_next_step.py`), with no review: `The worker is building it, ` between the held-round line and its `Next:` line.
       - (f) a fix with nothing running: no wait line.
       - In (a), `forge next --json`'s `next.line` equals the line that the item had before this change.
     - Adopted client (`adopted-v1.2.2`, moved to this release): case (b). This path is the same as on a new repo, so one case is enough.

### New and existing repos

- **New repos** (`forge init`, `forge init --starter`, `forge init --starter python`): the journey section and loop paragraphs in the installed guide, the refusal line in the worker brief, init's tell-the-person line, and the step and wait lines in `forge next`. Fresh, a new repo shows step 1.
- **Existing repos** (on upgrade to this release): `forge sync` writes the new guide and the release ships the new brief, step line and wait line. No repo file changes. An adopted live repo shows step 5, or step 7 when it is idle and a story is done. It never shows steps 1 to 4 or 6. Items 1, 2, 3 and 4 each test it on the adopted earlier-release fixture.

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
| JOURNEY-GUIDE | The journey in the guide and the README | The seven steps with what happens and what to say, the three loop paragraphs, the after-init, unsure and refusal rules, init's first instruction, the worker brief's refusal line, and the README journey section, on new and existing repos | 1, 2 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `src/forge/init.py` (one print in `init`), `README.md` (`## From idea to production`), `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_journey_guide.py` (new) | `tests/test_journey_guide.py` (`test_1`, `test_2`) | | no | |
| JOURNEY-NEXT | The step line and the wait lines in forge next | The first line that names the step out of seven, and one wait line for each running item, from facts Forge already records, on new and existing repos | 3, 4 | `src/forge/journey.py` (new), `src/forge/nextstep.py` (`next_step`, `context_hook`, `_item`, `_story`, `_next_round`), `src/forge/codex.py` (the capacity-retry branch), `tests/test_journey_next.py` (new), `tests/test_discovery.py` and `tests/test_retire_a_replaced_roadmap_item.py` (first-line checks), and other existing tests that check `forge next`'s first line or its exact item lines | `tests/test_journey_next.py` (`test_3`, `test_4`); the changed first-line checks | | no | |

The two parts share no file. Both use the step names pinned above, so they can run at the same time.

New moving parts: none

## Notes

- Owner direction (approved idea, 27 Oct 2026): one seven-step journey written once in the shipped guide, matched by the README. The agent explains it after init and asks for the first input. `forge next` names the step in one line, Forge's own repo shows step 5, and the board does not change. The agent shows the current step's phrases when a person is unsure, and explains refusals and offers a Forge bug. There is no tutorial, demo repo or video.
- Owner addition (27 Oct 2026): one plain wait line for each running item, from recorded facts only, with no new records. The journey page explains the cold read, build and review, and CI loops, and why each one exists.
- Planner choices the owner did not make:
  1. The step rule and its thresholds, as in item 3.
  2. "You can say" is what the person says to the agent.
  3. The wait line is an extra line under the status line, so the board and `--json` do not change.
  4. Codex capacity retries become the run's progress step, and Claude has no rate-limit case.
  5. The new module `journey.py` is there because `board.py` is at the 1,200-line ceiling.
- Overlap with FORGE-SIGNOFF-1 (in planning): its five sign-off steps fit inside steps 2 to 4 here. It builds Build now and Later. Whichever story lands second makes the step 4 sentence and the step rule's sign-off facts match.
