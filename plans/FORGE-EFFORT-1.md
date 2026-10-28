# Build and fix rounds raise their effort after a failure

3 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A build, fix or lite round starts at low effort: Codex `gpt-6.1-sol` at low, Claude `claude-sonnet-5-5` at low. A new repo gets these in its `forge.toml` at `forge init`. This repo's `forge.toml` gets them too. (Source: your decision, 28 Oct 2026)
- A round after a verified failure runs at the top effort: Codex high, Claude xhigh. A verified failure is a red test run, a blocking review finding or a failed required check. The round runs in the same worker thread as before, with the failure as the round's brief. Only that turn's effort changes. It works in codex, claude and split modes, because the tool that runs the round sets the effort. (Source: your decision, 28 Oct 2026; the arXiv 2610.34491 result that starting low and rising after a failure matched fixed top effort at lower cost)
- Your model choices stay. Only the effort changes from round to round. An existing repo keeps its `forge.toml` as it is. Its configured effort is the effort of a normal round. A round after a failure runs at the top effort, or at the configured effort when that is already higher. Forge writes nothing into the file. (Source: your decision, 28 Oct 2026; the exact upgrade rule is the planner's choice)
- Codex subagents stay as they are: `gpt-6-luna` at max effort, set by `subagents` and `subagent_effort` in `forge.toml`. The ladder changes only the main worker's effort for each round, never a subagent's model or effort. (Source: your decision, 28 Oct 2026)
- Reviews, cold reads and sign-off keep their fixed effort (Sol high). In a new Claude-only repo, cold reads and reviews run on `claude-sonnet-5-5` at high instead of `claude-opus-5-5`. An existing repo keeps its entry. (Source: your decision, 28 Oct 2026)
- Each round's run record and the board show its effort and its round number. The per-round line on the board and in the story's record names the effort the round ran at, so one week of cost and round counts can be compared on this repo. (Source: your decision, 28 Oct 2026)
- Forge never sets effort none. (Source: your decision, 28 Oct 2026)

Design: none (the board's round line gets two words; no new screen)

## Why

Every build, fix and lite round runs at one fixed effort. A first attempt pays for the high effort that most tasks do not need. A retry after a failure gets no more thought than the attempt that failed. The paper finds that starting low and rising only after a verified failure matches fixed top effort at lower cost, that higher fixed effort loses some tasks and overspends, and that effort none costs more.

## Done when

1. **A first build, fix or lite round runs at low effort. The next round after a red test run, a blocking review finding or a failed required check runs at the top effort in the same worker thread, and only that turn's effort changes. This is true in codex, claude and split modes.**
2. **A new repo gets low effort for build, fix and lite on both tools. In a Claude-only new repo, cold reads and reviews run on `claude-sonnet-5-5` at high. An existing repo keeps every model and effort in its `forge.toml`; its normal rounds run at its configured effort, and a round after a failure runs at the top effort or its own configured effort when that is higher.**
3. **Reviews, cold reads, design rounds and sign-off keep their fixed effort.**
4. **Each worker run's record and the board's round line show the round number and the effort that round ran at.**
5. **Forge never sets effort none.**

## Risks

Risks: none one-way. Each part reverts with its pull request.

Trade-off: a first round at low effort may fail more often. The paper says the saving still holds. You can compare one week of round counts and cost on this repo, then change `forge.toml`.

Trade-off: an existing repo with a high configured effort sees no saving. Its first round already runs at or above the top effort. Forge does not lower it, because it never rewrites your settings.

Finding for you: a build round that a Claude Code or Codex session runs as its own subagent (the native route) is handed out with a model and effort in the instruction text. Forge cannot change the effort of a subagent that the session continues. This plan changes the instruction for the round after a failure and does not start a fresh subagent. If the session cannot apply it, that round runs at the first effort. The builders measure which happens and say so in the guide.

Finding for you: Forge cannot read or change the prompt cache. This plan does not claim a cache result. Each run record already holds `cached_input_tokens`. After a week, compare it on rounds that rose in effort with rounds that did not.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-EFFORT-1"`. Tests run the forge command and never import forge. They build on the fake Codex driver and the fake Claude of `tests/test_codex_worker.py` and `tests/test_worker.py` (`install_claude`), and read the run records as `tests/test_run_records.py` does.

### What exists (evidence)

- Models per kind. `MODELS` in `src/forge/init.py` writes `[models.build|fix|lite|explore|grill|design]` for both tools into every new `forge.toml`: build and fix are Codex `gpt-6.1-sol` at `medium` and Claude `claude-sonnet-5-5` at `xhigh`, lite is Codex `medium` and Claude `xhigh`, grill on Claude is `claude-opus-5-5` at `high`. `src/forge/repo.py` holds the fallbacks: `WORKER_DEFAULTS` (Claude `xhigh`, Codex `medium`), `DESIGN_DEFAULTS` and `CLAUDE_GRILL_DEFAULT` (Opus, `high`). `repo.worker_models` returns the file's entry or `WORKER_DEFAULTS`. `repo.worker` returns the family, the chosen entry and why.
- Which entry a round uses. `worker.py` `work` sets `kind` to `Fix` for any Codex round after the item's first turn (`later`), `Build` for a task's first round and `Lite` for a fix's first round, then calls `repo.worker(config, kind.lower(), design, tool)`. Design rounds use `repo.design_models`.
- What a failure is. `worker._fix_round(state)` returns `(findings, failing)`: `findings` are `review.blocking(state["review"])`; `failing` is close's recorded red run (`state["tests"]`, set in `close.py` when the run fails) plus each required check on the pull request with `bucket == "fail"`. `work` sets `state["status"] = "fixing"` when either is non-empty and `"working"` otherwise, and records the work phase `fixing_findings` or `building`. A round after the owner's answer to a question (`--note`) has neither, so it is no failure. `state["round"]` holds the round number, and `record_event` copies it onto every record.
- Codex per turn. `codex.run(..., effort=None)` writes `request["config"]["model_reasoning_effort"]` when `effort` is given. `codex_turn.py` passes `request["config"]` as the `config` of `codex.thread_resume(...)` for a continued conversation and of `thread_start(...)` for a new one. `worker.work` starts a new driver process for every round, so each round's resume carries its own effort. The driver reads back `reasoningEffort` from the resume response and emits it as `selection`, and `codex.run` writes it onto the run record (`ran.update(model=..., effort=...)`). The turn itself (`thread.turn(prompt, ...)`) takes no effort.
- Claude per turn. `worker._claude` runs one `claude_turn.py` process per round. `turn()` builds `ClaudeAgentOptions(model=request["model"], effort=request["effort"], resume=request.get("resume"), ...)` and calls `query(...)`. So each resumed turn takes its own effort. `repo.claude_output` records the effort that the SDK's init event and the `forge-live-settings` reply report. The values come from `ready()` for build rounds and from `design_models` for design rounds.
- Native. `native.hand_out(..., chosen, family)` writes the `run start` event with `effort=chosen.get("effort")` and prints `Start it on {model} at {effort} effort`, then `Continue subagent <id>` or a new subagent. The session starts it; Forge cannot set the effort of a continued subagent.
- Records and board. `repo.record_run` writes `run start` and `run end` with `model`, `effort`, `family` and the event's `round`. `repo.record_timing(..., chosen)` writes `model` and `effort` to `timings.jsonl`. `board.py` puts `effort` and `round` on the live worker. The per-round line in `time_records.py` (`Round N: ...`) has no effort.
- This repo's `forge.toml` sets build and fix to Codex `medium` and Claude `high`, lite to `medium` and `medium`, grill on Claude to `claude-sonnet-5-5` at `high`.
- Guide text: `src/forge/templates/skill.md` ("Codex build, fix and lite default to `gpt-6.1-sol` at medium effort"), `docs/guide.md` (the `[models]` paragraph) and `src/forge/templates/brief.md`.

### Words this story pins

- **Top effort:** Codex `high`, Claude `xhigh`. Fixed in `repo.py` as `TOP_EFFORT`. It is not a setting (decision 28 Oct 2026; a setting would add a key and a check for no asked-for gain).
- **Effort order:** `low`, `medium`, `high`, `xhigh`, `max`. A failure round runs at the higher of the round's own effort and the top effort. A value outside this list (such as `ultra`, which Forge already maps to `max`) counts as at least the top, so it is never lowered.
- **Failed round:** the round where `_fix_round` returns findings or failing checks. A round that only answers a question or only has the owner's note is a normal round.
- **Subagents:** the ladder never touches `subagents` or `subagent_effort`. `round_effort` changes the `effort` key only, and the Codex `agents.default_subagent_model` and `agents.default_subagent_reasoning_effort` settings (`codex.OVERRIDES`) stay as `forge.toml` has them.
- **Applies to:** the kinds `Build`, `Fix` and `Lite` on both tools. It does not apply to design rounds, cold reads, reviews or sign-off.

### Done-when details

1. Ladder, in LADDER.
   - `repo.round_effort(chosen, family, failed)` returns `chosen`'s entry with its `effort` raised per the order above when `failed`. It never returns `none` and never lowers.
   - `worker.work`: after `findings, failing = _fix_round(state)`, a non-design Build, Fix or Lite round with `findings or failing` uses the raised entry. Codex passes it to `codex.run(..., effort=...)`. Claude replaces the `--effort` value in `claude`. The printed `Building ... ({model}, {effort})` line and `repo.record_timing(..., chosen)` use the same entry. The round's thread is the one `work` already resumes. The brief carries the failure as it does today. No new thread or session is started.
   - Native: `hand_out` receives the raised entry, so the `run start` event and the printed `Start it on ... at ... effort` line name it. The `Continue subagent` line is unchanged.
   - Tests in `tests/test_effort_ladder.py`:
     - `test_1_a_failed_round_runs_at_top_effort_in_the_same_thread`, parameters `codex`, `claude` and `split` (user-facing and plain parts): first round `forge work` then a red close run (new repo `forge.toml`, fake tools). The first run record has effort `low`. After a blocking finding, the second `forge work` resumes the same Codex conversation id or Claude session id, and its `run start` has effort `high` (Codex) or `xhigh` (Claude) and round 2. Repeat for a red test run and a failed required check. A round after `--note` for a question has effort `low`. On every failure round the Codex request's `agents.default_subagent_model` and `agents.default_subagent_reasoning_effort` equal the first round's (`gpt-6-luna`, `max`).
     - `test_1_native_round_names_the_raised_effort`: the printed line and the `run start` event for a native round after a failure name the top effort.
     - `adopted`: an existing repo whose `forge.toml` is the earlier release's (medium and xhigh) keeps round 1 at `medium` (Codex) and `xhigh` (Claude) and runs a failure round at `high` and `xhigh`.
2. Defaults, in DEFAULTS.
   - `MODELS` in `init.py`: build, fix and lite on both tools at `low`; `grill.claude` is `claude-sonnet-5-5` at `high`. `WORKER_DEFAULTS` effort becomes `low` for both tools, so a repo with no entry gets the same defaults. `CLAUDE_GRILL_DEFAULT` stays Opus for a repo with no entry, so no existing repo changes its reviewer. This repo's `forge.toml` sets build, fix and lite to `low` on both tools (lite's `subagents` keys stay).
   - Tests: `test_2_new_repos_start_low` (init writes `low` for build, fix and lite on both tools and Sonnet high for the Claude cold read; the first run record is `low`) and `test_2_existing_forge_toml_is_not_changed` (upgrade and `forge sync` leave an earlier `forge.toml`'s models and efforts byte for byte; its entry-less kinds follow the new `WORKER_DEFAULTS`, which is what "defaults" means).
3. Fixed effort, in LADDER.
   - `test_3_reviews_reads_and_design_keep_their_effort`: a failure round does not change the effort of a cold read, a review, a sign-off or a design (frontend) round.
4. Records, in SHOWN.
   - The `Round N:` line in `time_records.py` adds `built at <effort>` from the round's `run start` or `worker round` record, and omits it when none is recorded (old records). The board's item view shows the line as it shows every round line. The live worker already shows `effort` and `round`.
   - Test `test_4_round_line_and_run_records_show_effort_and_round`: the run records of a two-round item hold effort and round on each run, and the board's JSON round lines name `low` then the top effort.
5. Never none.
   - `round_effort` has no `none` in its order, and a configured `none` is refused by `forge.toml`'s existing model check or ignored by the order rules. Test `test_5_effort_none_is_never_sent`: no run record and no request to either fake tool holds `none` in any scenario of tests 1 to 3.

### New and existing repos

- **New repo (`forge init`, adoption):** gets the low defaults, Sonnet-high cold reads in a Claude-only setup, and the ladder. Full cases: tests 1 to 5.
- **Existing repo (upgrade):** keeps its `forge.toml`. Its configured effort is the normal-round effort. Failure rounds run at the top effort or its configured effort when higher. An entry-less kind gets the new low default. Cold reads keep their entry, or Opus when it has none. Existing-repo case: `adopted` in test 1 and `test_2_existing_forge_toml_is_not_changed`. The ladder is code, so it needs no sync step. The upgrade message tells the agent that new repos start at low effort and that the client edits its own `forge.toml` to match.
- The version bump needs no upgrade test.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| LADDER | Failure rounds raise effort | `repo.round_effort` and `TOP_EFFORT`, the raised entry in `forge work` for Codex, Claude and native rounds, and fixed effort elsewhere. | 1, 3, 5 | `src/forge/repo.py`, `src/forge/worker.py`, `src/forge/native.py`, `tests/test_effort_ladder.py` (new) | `tests/test_effort_ladder.py::test_1_a_failed_round_runs_at_top_effort_in_the_same_thread`, `::test_1_native_round_names_the_raised_effort`, `::test_3_reviews_reads_and_design_keep_their_effort`, `::test_5_effort_none_is_never_sent` | | no | |
| DEFAULTS | Low defaults | Low effort in `MODELS` and `WORKER_DEFAULTS`, Sonnet-high Claude cold read in new repos, this repo's `forge.toml`. | 2 | `src/forge/init.py`, `forge.toml`, `tests/test_effort_defaults.py` (new) | `tests/test_effort_defaults.py::test_2_new_repos_start_low`, `::test_2_existing_forge_toml_is_not_changed` | | no | |
| SHOWN | Round line and guides | The effort in each round line, and the guide, skill and brief text that states the ladder, the new defaults and the existing-repo rule. | 4 | `src/forge/time_records.py`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `tests/test_effort_records.py` (new) | `tests/test_effort_records.py::test_4_round_line_and_run_records_show_effort_and_round` | LADDER, DEFAULTS | no | |

LADDER and DEFAULTS share no file and can start now. SHOWN waits for both because it states their rules, pins nothing they need, and owns the shared guide lines. The `.claude` and `.codex` skill copies are rewritten by `forge sync`.

New moving parts: none.

## Notes

- **Scores (F x H >= 2 x C).**
  - Ladder in `forge work`, about 40 lines for three routes: F 3 (every failed round), H 2 (cost and lost tasks), C 2. 6 >= 4. Kept.
  - Low defaults: F 3, H 2, C 1 (a few edited lines). 6 >= 2. Kept.
  - Effort in the round line: F 2, H 1, C 1. 2 >= 2. Kept. A new board table or chart: cut.
  - A setting for top effort: F 1, H 1, C 3. 1 < 6. Cut.
  - Changing `CLAUDE_GRILL_DEFAULT` for repos with no entry: owner said existing repos keep theirs. Cut.
- **Thread and cache findings (Codex and Claude, 28 Oct).** Codex: the effort is set on the resume call of each round's driver, not on the turn call; the driver reports the applied effort back, and the test reads it from the run record. Claude: each round's `query()` takes `effort` together with `resume`, so one session can run rounds at two efforts. Neither path starts a new thread. What either tool does to its prompt cache is not stated in what Forge reads, so it stays unmeasured and the owner compares `cached_input_tokens` after a week.
- **Planner choices the owner did not make.**
  1. A failure round runs at the higher of its configured effort and the top effort, so a repo's high setting is never lowered.
  2. Top effort is fixed in code, not a `forge.toml` key.
  3. Entry-less kinds in an existing repo follow the new low `WORKER_DEFAULTS`; entries that are written stay.
  4. `CLAUDE_GRILL_DEFAULT` stays Opus for repos with no entry. Only `forge init` writes Sonnet.
  5. Design (user-facing) rounds keep their fixed design effort in every mode; the owner named build, fix and lite.
  6. A round after only a question or an owner note is a normal round, not a failure.
  7. The board change is one added phrase in the round line, no new screen.
  8. The native route changes only the instruction for the round after a failure.
