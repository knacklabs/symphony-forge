# Setup interview and app constitution for client repos

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Before the prototype, the agent asks the person four product questions, one at a time and in
  plain words: what the app is for, who uses it, what it keeps track of with the fields of each
  thing, and the options of each choice list. The answers go into the product brief
  (`docs/product/BRIEF.md`) and the prototype uses them. Prototype work does not wait for
  anything new. The order stays: discovery, prototype, customer sign-off, then stories.
- After the customer signs off, and before the first story, the agent writes the app's
  constitution in `docs/product/CONSTITUTION.md`. It asks whether any data is private or
  regulated, when the brief does not answer that yet. It shows the safe defaults for all other
  questions in one message, and the person can change them. It makes the architecture choices
  itself, one plain line each with its reason, and writes one decision record for each choice.
- You approve the constitution once. Forge accepts the approval only when the constitution and
  the brief answer every question that has no safe default, and each architecture choice has its
  accepted decision record.
- No new story starts in a client app until its constitution is approved. Forge says what to do
  next. Stories, parts and fixes that already started go on. Prototype work and Forge's own repo
  are never stopped.
- A code review or a cold read in an app with an approved constitution gets its text. Work
  against it is a serious finding that holds the work.
- A live app that joins Forge gets both halves of the interview together. The agent asks only
  what the code cannot answer, and records the stack that the code already uses.
- New repos get the guide and the brief's new section at init. Existing repos get the guide on
  upgrade and sync.

## Why

A new or adopted app starts with its product facts and its stack choices unrecorded, so later
stories rest on guesses. A non-technical owner has no single place to confirm them. On 21 and 22
October 2026 the owner chose an interview in two halves: the product questions before the
prototype, and the constitution after sign-off and before the first real story. The research
checklist (`/Users/ravikiranvemula/Workdir/app-checklist-research.md`, section 1) lists the
questions and their defaults.

## Done when

1. **In a client app past the prototype, `forge story new` and `forge start` refuse to start a story until the app's constitution is approved, and the refusal and `forge next` name the next step. Stories, parts and fixes that already started go on, and prototype work is never stopped.**
2. **The owner's approval of the constitution is accepted only when the constitution has its defaults and architecture choices, each choice links an accepted decision record, and the brief answers what the app is for, who uses it, what it keeps track of and whether data is private or regulated.**
3. **A code review or cold read in an app with an approved constitution gets the constitution's text, and Forge holds a finding or note against it as P1.**
4. **The guide tells the agent how to run both halves of the interview and the live-app version, and the reference page lists the defaulted questions. New repos get the guide and the brief's new section at init, and existing repos get the guide on upgrade and sync.**

## New and existing repos

- **New repos** (init): the repo starts as a prototype, so nothing new stops its work. The guide
  and the reference page arrive with setup. The brief has a new `## Things it keeps track of`
  section for the product answers. After the customer's sign-off, the first story waits for the
  approved constitution.
- **Existing repos** (on upgrade to this release, after `forge sync`): the guide and the
  reference page arrive with sync. The brief keeps its sections; the approval refusal names the
  missing `## Things it keeps track of` section, and the agent adds it during the interview. A
  client repo past the prototype, which includes every adopted live app, starts no new story
  until its constitution is approved. Stories, parts and fixes that started before the upgrade
  go on. A repo that is still a prototype is not stopped. Tested on the adopted earlier-release
  fixture moved to this release.

## Risks

Risks: none one-way. Each part reverts with its pull request.

Trade-off: after the upgrade, an existing live app can start no new story until the owner
approves its constitution. That costs one short interview, with most answers taken from the code,
and one approval.

Trade-off: the stack default for parts that have no code yet is an Nx workspace with React (Vite,
React Router) and NestJS, on Postgres. Forge's stack page still says npm workspaces until the
starter-app story changes it. A prototype is already built when the constitution is written, so
the agent records the stack that the code uses, and the default applies only to parts that have
no code.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Every Done-when item has exactly one test function, `test_<n>_...`, in one new file,
`tests/test_app_constitution.py`, which starts with `STORY = "FORGE-CONSTITUTION-1"`. Each test
runs the forge command and never imports forge. Each runs on a new repo (`_fresh_client` in
`tests/test_setup.py`, or `setup(repo, kind="client")` in `tests/test_story.py`) and on
`tests/fixtures/adopted-v1.2.2` moved to this release. Only the existing stubs are faked:
Autoreview and GitHub (`env`, `finding`, `blocked`, `CLEAN` in `tests/test_close.py`, and
`client as setup_client` from `tests/test_close_keeps_reviews_for_unchanged_branch_diffs.py`)
and the readers (`say` in `tests/test_readloop_gates.py` for Claude, and the set-up of
`_first_round_prompt` in `tests/test_readloop_prompt.py` for Codex). Guide delivery reuses
`unsynced_up` and `_repo_adopted_on_the_previous_release` from `tests/test_upgrade_command.py`,
as test_4 of `tests/test_stuck_worker_asks.py` does.

**Words this story pins.** GATE commits these first; REVIEW uses them.
- The constitution is `docs/product/CONSTITUTION.md`. Its outline, which the guide shows:

  ```
  # <App name> constitution

  The product facts are in docs/product/BRIEF.md.

  ## Defaults
  - <the question in plain words>: <the default or the person's answer>

  ## Architecture choices
  - <the choice>: <its reason, in one plain line> (docs/decisions/NNNN-<slug>.md)
  ```
- The approval is an accepted decision record whose slug is `app-constitution`
  (`docs/decisions/NNNN-app-constitution.md`), made with `forge decision new app-constitution`
  and accepted with `forge decision accept app-constitution --by "<name>"`. No new command,
  option or setting.
- "Approved" means: on the default branch as last fetched (`story.landed_ref`), some
  `docs/decisions/NNNN-app-constitution.md` has `status: accepted` and
  `docs/product/CONSTITUTION.md` exists. `records.constitution(top) -> str` returns the
  constitution's text from that ref when it is approved, and `""` otherwise. The gate, `forge
  next`, the review and the cold read all call it.
- "A client app past the prototype": `cfg["repo"] == "client"` and not `repo.is_prototype(top,
  cfg)`. A prototype repo already refuses `story new` until sign-off (`REFUSALS["prototype"]`),
  and that refusal comes first.
- The new brief section is `## Things it keeps track of`: one line per thing with its fields, and
  one line per choice list with its options. The product answers also use the existing
  `## Summary` (what the app is for) and `## Users` (who uses it). Private or regulated data uses
  the existing `- Personal data:` line of `## Answers`.
- A finding or note against the constitution has a title that starts `Constitution: `, after a
  read note's optional `Blocking:` or `Advisory:` label.

### Done-when details

1. Story gate (GATE).
   - `story.new` checks, after the prototype refusal: when `forge.toml` exists, `cfg["repo"] ==
     "client"`, the repo is not a prototype, and `records.constitution(top)` is `""`, it refuses
     with `REFUSALS["constitution"]`: `"New stories wait for this app's approved constitution in
     docs/product/CONSTITUTION.md."`, next step `forge fix start "Write the app constitution"
     --done "The owner approved docs/product/CONSTITUTION.md"`. `intake.act` reaches it through
     `story.new`, so `forge start` refuses the same way. `--from-fix` promotion is a new story
     too.
   - Not gated: `forge fix start`, `forge task start`, `forge read`, `forge work`, `forge close`
     and approval of a story whose branch already exists. The check sits in `story.new` only.
   - `forge next`: in a client repo past the prototype with no approved constitution, it appends
     `Before its next story, this app needs its approved constitution.` and the same Next line,
     after the other lines, so `machine_next` keeps the first Next line of the work in progress.
   - `story.py` is at 1,185 lines and must stay under 1,200: the refusal and the check take at
     most 5 lines there, and REVIEW adds one more. The ref reading lives in
     `records.constitution`.
   - Normal-use cases: a new repo after sign-off; a new repo before sign-off (the prototype
     refusal is unchanged and fixes of every kind start); an adopted live repo; a story started
     before the upgrade.
   - Test: `test_1_a_new_story_waits_for_the_approved_constitution`, with the parameter `case` in
     ("new prototype", "new after sign-off", "adopted", "adopted story already started").
     - new prototype (`_fresh_client`): `forge fix start "Build storage" --done "Storage works"
       --kind backend` exits 0, and no output has "constitution".
     - new after sign-off: commit an accepted client sign-off record to main and push it, as
       `_decision` in `tests/test_proto_signoff.py` writes it, with `status: accepted`.
       `forge story new SHOP "Shoppers can save a basket"` exits 1. Its stderr has the refusal
       line and the `forge fix start "Write the app constitution"` step. `forge next` shows the
       same two lines. `forge fix start` for the constitution exits 0. In that fix, write the
       constitution and a filled choice record, run `forge decision accept` for the choice and
       for `app-constitution`, then merge the fix to main with `--ff-only` and push, as test_1 of
       `tests/test_design_first.py` merges its settings fix. Then `forge story new` exits 0, and
       `forge next` has no constitution line.
     - adopted (`tests/fixtures/adopted-v1.2.2/client`): `forge story new` exits 1 with the same
       refusal. After the constitution lands the same way, it exits 0.
     - adopted story already started: start the story with the earlier release's `story.py`, as
       test_24 of `tests/test_design_first.py` installs it. Back on this release, `forge read
       SHOP` runs with no constitution refusal.
2. Approval check (GATE).
   - `records.decision_accept`, for a slug that ends in `app-constitution`, refuses before it
     accepts when anything below is missing. One refusal, `"The app constitution can't be
     approved yet: {missing}."`, next step `fill them in, then forge decision accept
     app-constitution --by "{by}"`. `{missing}` lists each problem in plain words, joined by
     "; ":
     - `docs/product/CONSTITUTION.md` does not exist;
     - its `## Defaults` or `## Architecture choices` section has no text other than comments
       (the same test as the unfilled check on `DECISION_SECTIONS`);
     - an `## Architecture choices` line that names no `docs/decisions/NNNN-<slug>.md`, quoted;
     - a named record that does not exist in the checkout or is not `status: accepted`, with
       `forge decision accept <slug>`;
     - `docs/product/BRIEF.md` with no text in `## Summary`, `## Users` or `## Things it keeps
       track of`;
     - no settled `Personal data` answer: `nextstep.open_must_answer_topics` lists it (missing,
       malformed, `ask the client` or `later`).
   - It reads the checkout's files (the fix's worktree), not the default branch.
   - Normal-use cases: the first approval after sign-off; an adopted live app; a choice record
     still proposed; a brief from an earlier release without the new section.
   - Test: `test_2_the_constitution_is_approved_only_when_complete`, with the parameter `adopted`
     (a new repo after sign-off, and the adopted fixture). In a fix: with no constitution, accept
     exits 1 and names `docs/product/CONSTITUTION.md`. With an empty `## Architecture choices`,
     it names that section. With a choice line that links a proposed record, it names the record
     and `forge decision accept <slug>`. With a brief that lacks `## Things it keeps track of`
     (the adopted fixture's brief, or the section removed), it names that section. With
     `- Personal data: ask the client (developer, 2026-10-22)`, it names Personal data. When all
     is complete, it exits 0 with `Accepted docs/decisions/`, and the record has
     `status: accepted`.
3. Review and cold read (REVIEW).
   - `review.run` adds a `<!-- constitution -->` block of `review.md` after the review-rules
     block when `records.constitution(top)` is not empty: `## This app's constitution` / `The
     app's approved constitution, on the default branch, follows. Report work that goes against
     it as a finding titled `Constitution: <the line it breaks>`, quoting the line. Where it
     differs from Forge's convention pages, it wins.` / `$constitution`. A branch's own edit of
     the constitution never reaches the prompt.
   - The cold read's first block (`cold-read.md`, before `## What counts`) gets: `This app's
     approved constitution, from the default branch, follows. Report a plan that goes against it
     as a note titled `Constitution: <the line it breaks>`:` / `$constitution`. `story.py` fills
     `constitution` with `records.constitution(top) or "None."`.
   - `score.normalise` gets a floor next to the Harm floor: a finding or note titled
     `Constitution: ` scores Gain 4 or more and Work 2 or less, and its score line is marked
     `(floor: constitution)`. That puts it at "fix now" (P1) whatever the model scored, both for
     review findings (`autoreview.py` calls `normalise`) and for read notes (`score.notes`). Its
     Harm is unchanged, so a constitution finding is a P0 only when its Harm makes it one. A
     `Case: rare` note stays a follow-up, as today.
   - The worker brief (`brief.md`) gets: `When docs/product/CONSTITUTION.md is approved, follow
     it. A review holds work that goes against it.`
   - Normal-use cases: a fix review; a story part's review; a story's cold read; an app without
     an approved constitution.
   - Test: `test_3_reviews_and_reads_hold_work_against_the_constitution`, with the parameter
     `adopted` (`setup_client(env, adopted)`).
     - An approved constitution is on main. A fix that also edits the constitution closes. The
       review prompt (`env.prompt()`) has `## This app's constitution`, the rule sentence and the
       main branch's text, and not the branch's edit. Autoreview returns a P1 finding titled
       `Constitution: The app uses Postgres` with `Gain 3, Work 4, Harm 1`. Close exits 1 with
       "The review left serious findings open".
     - With only a proposed `app-constitution` record on main, the prompt has no `## This app's
       constitution`.
     - A story's first cold read (the Claude reader with `say`) gets a prompt with the rule
       sentence and the constitution's text. A reader note `Blocking: Constitution: The plan adds
       MySQL` scored `Gain 2, Work 1, Harm 1` holds the read: the notes show `(floor:
       constitution)` and no below-the-bar disposition, and `forge read` reports it as open.
4. The guide (GATE).
   - `skill.md`: a new `## App constitution` section after `## Prototype`. The Prototype
     section's order becomes "... obtain the customer's named sign-off; then write the app
     constitution; then create stories." The new section has these sentences, which the test
     checks:
     - `Before the prototype, ask only the product questions: what the app is for, who uses it,
       what it keeps track of with each thing's fields, and the options of each choice list.`
     - `Write the answers in docs/product/BRIEF.md under ## Summary, ## Users and ## Things it
       keeps track of.`
     - `After the customer's sign-off and before the first story, write the app's constitution in
       docs/product/CONSTITUTION.md.`
     - `Show every default in one message, and let the person change any of them.`
     - `Make each architecture choice yourself, from the answers and the code, and write it as
       one plain line with its reason and its decision record.`
     - `A live app answers both halves at adoption: ask only what the code cannot answer.`
     - `No new story starts until the owner approves the constitution.`
     The section also says: one question at a time, in plain words, for a person who may not be
     technical; ask whether any data is private or regulated only when the brief's `Personal
     data` answer is missing; skip a defaulted question that `## Answers` already answers;
     record the stack that the code uses, and use the stack default (an Nx workspace with React
     (Vite, React Router) and NestJS, on Postgres; a FastAPI backend only when the person asks)
     only for parts with no code; the constitution's outline above; the approval commands; and
     that a review or cold read holds work against the approved constitution. `## Adopt a live
     app` gets one step that points to the section.
   - The reference page (`.codex/skills/forge/fde.md`, which sync copies to
     `.claude/skills/forge/fde.md`) gets `## Constitution defaults`: the defaulted questions of
     the research checklist's section 1 (all except 1, 2, 6, 7 and 17), each as `- <question in
     plain words>: <default>`, naming no vendor that the stack page or the owner has not chosen.
   - `src/forge/templates/skeleton/docs/product/BRIEF.md` gets `## Things it keeps track of`
     after `## Users`, with a one-line comment.
   - Test: `test_4_clients_get_the_constitution_guide`, with the parameter `adoption` in ("new
     init", "previous release upgrade and sync"). For `.claude` and `.codex`,
     `skills/forge/SKILL.md` has the seven sentences above (whitespace joined), and
     `skills/forge/fde.md` has `## Constitution defaults`. On a new init,
     `docs/product/BRIEF.md` has `## Things it keeps track of`.

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
| GATE | Story gate, approval and guide | `records.constitution`, the story gate in `forge story new` and `forge start`, the `forge next` line, the approval check on `app-constitution`, the guide's App constitution section, the reference page's defaults and the brief's new section. | 1, 2, 4 | `src/forge/records.py`, `src/forge/story.py`, `src/forge/nextstep.py`, `src/forge/templates/skill.md`, `src/forge/templates/skeleton/docs/product/BRIEF.md`, `.codex/skills/forge/fde.md`, `.claude/skills/forge/fde.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md` (the last three rewritten by `forge sync`), `tests/test_story.py` and the existing tests in Notes | `tests/test_app_constitution.py` (`test_1`, `test_2`, `test_4`), plus GATE's changes in Notes | | no | |
| REVIEW | Reviews and reads hold the constitution | The review and cold-read prompts carry the approved constitution, Forge holds a `Constitution:` finding or note at P1 through a score floor, and the worker brief says to follow the constitution. | 3 | `src/forge/review.py`, `src/forge/templates/review.md`, `src/forge/story.py`, `src/forge/templates/cold-read.md`, `src/forge/score.py`, `src/forge/templates/brief.md` | `tests/test_app_constitution.py` (`test_3`) | GATE | no | |

New moving parts: none

## Notes

- **Order.** GATE, then REVIEW. REVIEW uses `records.constitution`, GATE's test helper and the new
  test file, and both change `story.py`. Both ship in one release.
- **Decision 0095 stays.** The prototype-first order is unchanged. This story adds one step after
  sign-off. No decision record changes.
- **Not in this story.** The starter app with Nx and the shadcn check; the design canvas flow with
  the completeness check; a change to `src/forge/templates/conventions/stack.md`.
- **A later change to the constitution** needs no new approval in this story. A changed
  architecture choice is a new decision record that supersedes the old one, as today.
- **Existing tests (GATE).**
  - `setup(repo, kind="client")` in `tests/test_story.py` also commits an approved constitution
    (a filled `docs/product/CONSTITUTION.md` and an accepted `NNNN-app-constitution.md` at the
    next free number) through one helper in the same file, `approved_constitution(repo,
    where=None)`. `tests/test_app_constitution.py` imports it.
  - Each other test that runs `forge story new`, or `forge start` for a plan, in a client repo
    past the prototype calls `approved_constitution` first and changes nothing else. Known ones:
    `tests/test_board_dependency_timelines.py`, `tests/test_approval.py`,
    `tests/test_board_graph.py`, `tests/test_board_runway.py`,
    `tests/test_cold_read_blocking_notes.py`, `tests/test_claude_implementation_defaults.py`,
    `tests/test_design_first.py`, `tests/test_fix_five_process_gaps_waste_rounds_cold_read.py`,
    `tests/test_fix_plan_reads_capped.py`, `tests/test_codex_reader.py`,
    `tests/test_machine_views.py`, `tests/test_proto_gate.py`, `tests/test_readloop_cut.py`,
    `tests/test_run_records.py`, `tests/test_score_notes.py`, `tests/test_score_upgrade.py`,
    `tests/test_start_sorts_ideas.py`, `tests/test_story_reads_limit_done_when_items.py`,
    `tests/test_story_without_a_spec.py`, `tests/test_live_stage.py`,
    `tests/test_owner_decides_at_the_round_limit.py`, `tests/test_phases.py`,
    `tests/test_read_accepts_no_findings.py` and `tests/test_started_branches_claim_the_work.py`.
    Run them all. A test that expects the exact lines of `forge next` in such a repo also gets
    the constitution first.
- **Not to do.**
  - No new command, option, `forge.toml` setting, stored state or board change.
  - No gate on fixes, on prototype work or in Forge's own repo.
  - No new skeleton file: the guide holds the constitution's outline for new and existing repos.
  - No copy of a brief answer in the constitution: it points to the brief.
- No client repo is named anywhere in this story's code, tests, texts or commits.
