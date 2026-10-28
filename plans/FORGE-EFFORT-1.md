# Build and fix rounds raise their effort after a failure

4 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A build, fix or lite round starts at low effort: Codex `gpt-6.1-sol` at low, Claude `claude-sonnet-5-5` at low. A new repo gets these in its `forge.toml` at `forge init`. This repo's `forge.toml` gets them too. (Source: your decision, 28 Oct 2026)
- A round after a verified failure runs at the top effort: Codex high, Claude xhigh. A verified failure is a red test run, a blocking review finding or a failed required check, meaning a check named in `checks` in `forge.toml`. An optional check that fails does not raise the effort. The round runs in the same worker thread as before, with the failure as the round's brief. Only that turn's effort changes. It works in codex, claude and split modes, because the tool that runs the round sets the effort. (Source: your decision, 28 Oct 2026; the arXiv 2610.34491 result that starting low and rising after a failure matched fixed top effort at lower cost)
- Claude build, fix and lite rounds run through the Claude Agent SDK, not as the coordinating session's own subagent, whenever the SDK is installed. The SDK sets effort for each turn and gives the builder its Haiku helpers. The native route stays for a Claude round only where no SDK is installed, and there the effort and helpers are requested in the instruction and not enforced. This changes the earlier native-runs direction for Claude rounds only. A Codex round in a Codex session stays native, with its effort requested in the same way. (Source: your decision, 28 Oct 2026)
- Your model choices stay. Only the effort changes from round to round. An existing repo keeps its `forge.toml` as it is. Its configured effort is the effort of a normal round. A round after a failure runs at the top effort, or at the configured effort when that is already higher. Forge writes nothing into the file. (Source: your decision, 28 Oct 2026; the exact upgrade rule is the planner's choice)
- The Claude builder gets helpers of its own, as the Codex builder has. Claude build, fix and lite entries take `subagents` and `subagent_effort`, and the defaults are `claude-haiku-5-5` at high. A new repo gets them at `forge init`, and this repo's `forge.toml` gets them. An existing repo keeps the entries it has. An entry sets both keys or neither, as today, and a kind with neither uses the default. Forge also gives the SDK's built-in `general-purpose` helper the same model and effort. Forge hands them to the Claude builder only. It sets no `settings.json` value and no `CLAUDE_CODE_SUBAGENT_MODEL`, so no other Claude session changes. (Source: your decision, 28 Oct 2026; Haiku 5.5 scores well above Luna on Terminal-Bench at the same list price)
- Subagent settings never change with the round. Codex subagents stay as they are: `gpt-6-luna` at max effort, set by `subagents` and `subagent_effort` in `forge.toml`. The ladder changes only the main worker's effort for each round, never the model or effort of a Codex or Claude subagent. (Source: your decision, 28 Oct 2026)
- Reviews, cold reads and sign-off keep their fixed effort (Sol high). In a new Claude-only repo, cold reads and reviews run on `claude-sonnet-5-5` at high instead of `claude-opus-5-5`. A new repo's `forge.toml` sets this in `[models.grill.claude]` for cold reads and `[models.review.claude]` for reviews. An existing repo keeps its entries. (Source: your decision, 28 Oct 2026)
- Each round's run record and the board show its effort and its round number. The per-round line on the board and in the story's record names the effort the round ran at, so one week of cost and round counts can be compared on this repo. (Source: your decision, 28 Oct 2026)
- Forge's defaults and the ladder never set effort none. A value that a repo writes in its own `forge.toml` is the repo's choice. (Source: your decision, 28 Oct 2026)

Design: none (the board's round line gets two words; no new screen)

## Why

Every build, fix and lite round runs at one fixed effort. A first attempt pays for the high effort that most tasks do not need. A retry after a failure gets no more thought than the attempt that failed. The paper finds that starting low and rising only after a verified failure matches fixed top effort at lower cost, that higher fixed effort loses some tasks and overspends, and that effort none costs more.

## Done when

1. **A first build, fix or lite round runs at low effort. The next round after a red test run, a blocking review finding or a failed required check runs at the top effort in the same worker thread, and only that turn's effort changes. This is true in codex, claude and split modes. A Claude round runs through the SDK whenever it is installed. Where a round runs natively, its effort is requested and labelled so.**
2. **A new repo gets low effort for build, fix and lite on both tools. In a Claude-only new repo, cold reads (`models.grill.claude`) and reviews (`models.review.claude`) run on `claude-sonnet-5-5` at high. An existing repo keeps every model and effort in its `forge.toml`; its normal rounds run at its configured effort, and a round after a failure runs at the top effort or its own configured effort when that is higher.**
3. **Reviews, cold reads, design rounds and sign-off keep their fixed effort.**
4. **Each worker run's record and the board's round line show the round number and the effort that round ran at.**
5. **Forge's defaults and the ladder never set effort none.**
6. **The Claude builder's helpers run on the `subagents` model at the `subagent_effort` of its kind's entry, `claude-haiku-5-5` at high when the kind has no entry pair. This covers the built-in `general-purpose` helper too. Forge passes them only to the Claude builder's own turn, through the SDK's options. They do not change on a failure round. Existing entries are kept.**

## Risks

Risks: none one-way. Each part reverts with its pull request.

Trade-off: a first round at low effort may fail more often. The paper says the saving still holds. You can compare one week of round counts and cost on this repo, then change `forge.toml`.

Trade-off: an existing repo with a high configured effort sees no saving. Its first round already runs at or above the top effort. Forge does not lower it, because it never rewrites your settings.

Finding for you: a round that a session runs as its own subagent (the native route) is handed out with a model and effort in the instruction text, and Forge cannot check that the session applied it. After this plan that is true only for a Codex round in a Codex session and for a Claude round where no SDK is installed. The record and the printed line say "requested" for those rounds. A Codex session cannot change the effort of a subagent it continues, so a Codex native failure round may run at the first effort. The SDK route does not have this limit.

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
- Review and cold-read models. `review.py` (around line 920) takes the review model from `repo.models(cfg, "review", engine)`, so `[models.review]` or `[models.review.claude]` picks it and passes it to Autoreview as `--model` and `--thinking`. With no entry it passes nothing, and Autoreview uses its own default. The cold read uses `[models.grill.claude]` (`repo.models(cfg, "grill", "claude")`, default `CLAUDE_GRILL_DEFAULT`). `init.py` `MODELS` writes no `review` entry today. `_models_problem` accepts a per-family `models.review.claude` with a `model` key.
- Route. `repo.route` returns `native` when the worker's tool is the coordinating app's tool, and `worker.work` then hands the round out and returns before the SDK path. `ready()` skips `claude_sdk.sdk_problem()` for native rounds.
- Native. `native.hand_out(..., chosen, family)` writes the `run start` event with `effort=chosen.get("effort")` and prints `Start it on {model} at {effort} effort`, then `Continue subagent <id>` or a new subagent. The session starts it; Forge cannot set the effort of a continued subagent.
- Records and board. `repo.record_run` writes `run start` and `run end` with `model`, `effort`, `family` and the event's `round`. `repo.record_timing(..., chosen)` writes `model` and `effort` to `timings.jsonl`. `board.py` puts `effort` and `round` on the live worker. The per-round line in `time_records.py` (`Round N: ...`) has no effort.
- This repo's `forge.toml` sets build and fix to Codex `medium` and Claude `high`, lite to `medium` and `medium`, grill on Claude to `claude-sonnet-5-5` at `high`.
- Guide text: `src/forge/templates/skill.md` ("Codex build, fix and lite default to `gpt-6.1-sol` at medium effort"), `docs/guide.md` (the `[models]` paragraph) and `src/forge/templates/brief.md`.

- Claude subagents. `repo.SUBAGENTS` and `_models_problem` already accept `subagents` and `subagent_effort` on any build, fix, lite or explore entry, including Claude's, and demand both or neither. Nothing reads them for Claude: `roles.subagent_defaults` and `sync.py` (`AGENT_PINS`) use only the Codex entry. `claude_turn.py` builds `ClaudeAgentOptions` with no `agents` option; it sets `setting_sources=["user","project","local"]`, so the roles in `.claude/agents/*.md` (written by `roles.ships` from the main model, not the budget) load for the builder. The SDK is pinned at 0.2.161 (`claude_sdk.SDK_PIN`). Its types, read in a throwaway environment: `AgentDefinition` has description, prompt, tools, disallowedTools, model, skills, memory, mcpServers, initialPrompt, maxTurns, background, effort and permissionMode; `ClaudeAgentOptions` has agents, model, effort, thinking and max_thinking_tokens. Open report: openai/codex issue 32587 says a pinned Codex custom agent can still inherit the parent's model and effort, so the Codex side is only as sure as what the request sends.

### Words this story pins

- **Top effort:** Codex `high`, Claude `xhigh`. Fixed in `repo.py` as `TOP_EFFORT`. It is not a setting (decision 28 Oct 2026; a setting would add a key and a check for no asked-for gain).
- **Effort order:** `none` (only a repo's own value), `low`, `medium`, `high`, `xhigh`, `max`. A failure round runs at the higher of the round's own effort and the top effort. A repo's own `none` is raised to the top effort on a failure round. A value outside this list (such as `ultra`, which Forge already maps to `max`) counts as at least the top, so it is never lowered.
- **Failed round:** the round where `_fix_round` returns blocking findings, close's red test run, or a failing check whose name is in `forge.toml`'s `checks`. `_failing` lists every failed check, so the ladder keeps only those names to decide the effort. The brief still lists all failed checks, as today. A round that only answers a question or only has the owner's note is a normal round.
- **Subagents:** the ladder never touches `subagents` or `subagent_effort`. `round_effort` changes the `effort` key only, and the Codex `agents.default_subagent_model` and `agents.default_subagent_reasoning_effort` settings (`codex.OVERRIDES`) stay as `forge.toml` has them.
- **Claude subagents:** `repo.subagent_budget(cfg, kind, family)` returns `{model, effort}` from the kind's entry for the family, else from lite's (as `subagent_defaults` does for Codex), else the new `SUBAGENT_DEFAULT` (`claude-haiku-5-5` at high). The pair rule stays as it is: `_models_problem` refuses an entry that sets only one of `subagents` and `subagent_effort`. This is the simpler choice, because it needs no code and keeps the existing test. A kind with neither key uses the default. Forge sends it in the request to `claude_turn.py`, which sets it through `ClaudeAgentOptions` for that turn only. The pin is `ClaudeAgentOptions(agents={role: AgentDefinition(description=..., prompt=..., model=<budget model>, effort=<budget effort>)})` for the helper roles of `roles.ROLES` that a builder delegates to (`explorer`, `tester`, `refactorer`), with each role's own description and instructions, and also `general-purpose`, which the SDK keeps as a built-in helper and which a builder uses when it names no role. Its definition uses the built-in's description ("General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks") and a one-line prompt to match. Both fields exist in 0.2.161, so there is no model-only fallback. If a test shows the SDK does not override the project role of the same name, that is a finding for the owner. `settings.json`, `CLAUDE_CODE_SUBAGENT_MODEL` and any other process-wide setting are out of scope. Those would change every Claude session and override the role pins.
- **Applies to:** the kinds `Build`, `Fix` and `Lite` on both tools. It does not apply to design rounds, cold reads, reviews or sign-off.

### Done-when details

1. Ladder, in LADDER.
   - `repo.round_effort(chosen, family, failed)` returns `chosen`'s entry with its `effort` raised per the order above when `failed`. It never returns `none` and never lowers.
   - `worker.work`: after `findings, failing = _fix_round(state)`, a non-design Build, Fix or Lite round with `findings or failing` uses the raised entry. Codex passes it to `codex.run(..., effort=...)`. Claude replaces the `--effort` value in `claude`. The printed `Building ... ({model}, {effort})` line and `repo.record_timing(..., chosen)` use the same entry. The round's thread is the one `work` already resumes. The brief carries the failure as it does today. No new thread or session is started.
   - Routing: in `worker.work`, a Claude round is native only when `claude_sdk.sdk_problem()` reports no SDK. Otherwise `is_native` is false and the round runs through the SDK path. This applies to every Claude worker round, design rounds included, because they share the SDK path and the helpers. Codex rounds route as today.
   - Native: `hand_out` receives the raised entry, so the `run start` event and the printed line name it. The printed line and the `run start` event say the effort is requested (`requested` in the event). The `Continue subagent` line is unchanged.
   - Failure test: the ladder raises effort when `findings`, close's red run or a failing check named in `config["checks"]` exists. `worker.py` keeps `_fix_round` and `_failing` as they are and filters in the caller.
   - Tests in `tests/test_effort_ladder.py`:
     - `test_1_a_failed_round_runs_at_top_effort_in_the_same_thread`, parameters `codex`, `claude` and `split` (user-facing and plain parts): first round `forge work` then a red close run (new repo `forge.toml`, fake tools). The first run record has effort `low`. After a blocking finding, the second `forge work` resumes the same Codex conversation id or Claude session id, and its `run start` has effort `high` (Codex) or `xhigh` (Claude) and round 2. Repeat for a red test run and a failed required check. A failed check that `forge.toml` does not list, with every listed check passing, leaves the next round at `low`. A round after `--note` for a question has effort `low`. On every failure round the Codex request's `agents.default_subagent_model` and `agents.default_subagent_reasoning_effort` equal the first round's (`gpt-6-luna`, `max`).
     - `test_1_claude_rounds_use_the_sdk_in_a_claude_session`: with the coordinator set to Claude and the SDK installed, a Claude round goes to the fake SDK and prints no native hand-out. With no SDK installed, the same round is handed out natively.
     - `test_1_native_round_names_the_requested_effort`: the printed line and the `run start` event for a native round after a failure name the top effort and say it is requested (Codex session, and Claude with no SDK).
     - `adopted`: in a Claude session with the SDK installed, an existing repo whose round used to be native now runs through the SDK. An existing repo whose `forge.toml` is the earlier release's (medium and xhigh) keeps round 1 at `medium` (Codex) and `xhigh` (Claude) and runs a failure round at `high` and `xhigh`.
2. Defaults, in DEFAULTS.
   - `MODELS` in `init.py`: build, fix and lite on both tools at `low`; `grill.claude` and a new `[models.review.claude]` (model only plus effort) are `claude-sonnet-5-5` at `high`. `WORKER_DEFAULTS` effort becomes `low` for both tools, so a repo with no entry gets the same defaults. `CLAUDE_GRILL_DEFAULT` stays Opus for a repo with no entry, so no existing repo changes its reviewer. This repo's `forge.toml` sets build, fix and lite to `low` on both tools (lite's `subagents` keys stay).
   - Tests: `test_2_new_repos_start_low` (init writes `low` for build, fix and lite on both tools and Sonnet high in both `models.grill.claude` and `models.review.claude`; the first run record is `low`; a Claude review's Autoreview request carries `--model claude=claude-sonnet-5-5` and `--thinking claude=high`) and `test_2_existing_forge_toml_is_not_changed` (upgrade and `forge sync` leave an earlier `forge.toml`'s models and efforts byte for byte; its entry-less kinds follow the new `WORKER_DEFAULTS`, which is what "defaults" means).
3. Fixed effort, in LADDER.
   - `test_3_reviews_reads_and_design_keep_their_effort`: a failure round does not change the effort of a cold read, a review, a sign-off or a design (frontend) round.
4. Records, in SHOWN.
   - The `Round N:` line in `time_records.py` adds `built at <effort>` from the round's `run start` or `worker round` record, and omits it when none is recorded (old records). The board's item view shows the line as it shows every round line. The live worker already shows `effort` and `round`.
   - Test `test_4_round_line_and_run_records_show_effort_and_round`: the run records of a two-round item hold effort and round on each run, and the board's JSON round lines name `low` then the top effort.
5. Never none.
   - `repo.py` validates an effort as text only, so a repo's own `none` is its choice and Forge does not refuse it. Forge's defaults hold no `none`, and a failure round raises a configured `none` to the top. Test `test_5_effort_none_is_never_sent`: a new repo's file, and every run record and request in tests 1 to 3, hold no `none`; a repo that configures `none` itself runs round 1 as configured and its failure round at the top effort.

6. Claude subagents, in SUBS.
   - `MODELS` in `init.py` adds `subagents = "claude-haiku-5-5"` and `subagent_effort = "high"` to build, fix and lite on Claude. This repo's `forge.toml` does the same. ``repo.subagent_budget` and `SUBAGENT_DEFAULT` are new in `repo.py`. The budget also covers the `general-purpose` definition. `worker._run` adds the budget to the request, and `claude_turn.py` applies it. Design (frontend) rounds on Claude get the same budget, because they run through the same turn.
   - Tests in `tests/test_claude_subagents.py`:
     - `test_6_claude_builder_gets_haiku_helpers`: a new repo's Claude round sends the fake SDK `agents` for the helper roles and `general-purpose` with `claude-haiku-5-5` at high. A Codex round sends none. For Codex, `test_6_codex_request_names_the_subagents` asserts what the request sends (`agents.default_subagent_model` and `agents.default_subagent_reasoning_effort`). It does not assert what Codex then uses, because of the open report above. `test_6_no_process_wide_setting`: after a round, no `settings.json` under the repo or home and no `CLAUDE_CODE_SUBAGENT_MODEL` in the turn's environment holds a subagent value.
     - `adopted`: an earlier `forge.toml` with its own Claude subagent pair keeps it. One with neither key gets the default. One with a single key is refused, as today (`test_6_one_key_is_refused_as_today`). The test sees the request only, so it proves what Forge sends and not what the model does with it. A later failure round (the ladder test's scenario) sends the same `agents` as round 1.

### New and existing repos

- **New repo (`forge init`, adoption):** gets the low defaults, Sonnet-high cold reads in a Claude-only setup, and the ladder. Full cases: tests 1 to 5.
- **Subagents:** a new repo's Claude entries carry the Haiku helpers. An existing repo keeps its entries; a kind with neither key uses the default.
- **Routing:** a new repo and an existing repo both run Claude rounds through the SDK when it is installed. This is code, with no sync step.
- **Existing repo (upgrade):** keeps its `forge.toml`. Its configured effort is the normal-round effort. Failure rounds run at the top effort or its configured effort when higher. An entry-less kind gets the new low default. Cold reads and reviews keep their entries, and Opus when a cold read has none. Existing-repo case: `adopted` in test 1 and `test_2_existing_forge_toml_is_not_changed`. The ladder is code, so it needs no sync step. The upgrade message tells the agent that new repos start at low effort and that the client edits its own `forge.toml` to match.
- The version bump needs no upgrade test.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| LADDER | Failure rounds raise effort | `repo.round_effort` and `TOP_EFFORT`, the raised entry in `forge work`, the SDK route for Claude rounds, the requested label for native rounds, the required-check filter, and fixed effort elsewhere. | 1, 3, 5 | `src/forge/repo.py`, `src/forge/worker.py`, `src/forge/native.py`, `tests/test_effort_ladder.py` (new) | `tests/test_effort_ladder.py::test_1_a_failed_round_runs_at_top_effort_in_the_same_thread`, `::test_1_claude_rounds_use_the_sdk_in_a_claude_session`, `::test_1_native_round_names_the_requested_effort`, `::test_3_reviews_reads_and_design_keep_their_effort`, `::test_5_effort_none_is_never_sent` | DEFAULTS | no | |
| DEFAULTS | Low defaults | Low effort in `MODELS` and `WORKER_DEFAULTS`, Sonnet-high Claude cold read and review entries in new repos, this repo's `forge.toml`. | 2 | `src/forge/init.py`, `src/forge/repo.py` (`WORKER_DEFAULTS` only), `forge.toml`, `tests/test_effort_defaults.py` (new) | `tests/test_effort_defaults.py::test_2_new_repos_start_low`, `::test_2_existing_forge_toml_is_not_changed` | | no | |
| SHOWN | Round line and guides | The effort in each round line, and the guide, skill and brief text that states the ladder, the new defaults and the existing-repo rule. | 4 | `src/forge/time_records.py`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `tests/test_effort_records.py` (new) | `tests/test_effort_records.py::test_4_round_line_and_run_records_show_effort_and_round` | LADDER | no | |
| SUBS | Claude helpers | `subagent_budget` and its default, the Haiku entries in `MODELS` and this repo's `forge.toml`, and the SDK options that give the Claude builder its helpers. | 6 | `src/forge/repo.py`, `src/forge/init.py`, `forge.toml`, `src/forge/worker.py`, `src/forge/claude_turn.py`, `tests/test_claude_subagents.py` (new) | `tests/test_claude_subagents.py::test_6_claude_builder_gets_haiku_helpers`, `::test_6_codex_request_names_the_subagents`, `::test_6_no_process_wide_setting`, `::test_6_one_key_is_refused_as_today` | LADDER | no | |

DEFAULTS goes first. LADDER waits for it because both edit `repo.py` and LADDER's tests need the new low defaults. SUBS waits for LADDER, which already waits for DEFAULTS, because it edits `worker.py`, `repo.py`, `init.py` and `forge.toml`. SHOWN waits for LADDER and DEFAULTS because it states their rules, pins nothing they need, and owns the shared guide lines. The `.claude` and `.codex` skill copies are rewritten by `forge sync`.

New moving parts: none.

## Notes

- **Scores (F x H >= 2 x C).**
  - Ladder in `forge work`, about 40 lines for three routes: F 3 (every failed round), H 2 (cost and lost tasks), C 2. 6 >= 4. Kept.
  - Low defaults: F 3, H 2, C 1 (a few edited lines). 6 >= 2. Kept.
  - Effort in the round line: F 2, H 1, C 1. 2 >= 2. Kept. A new board table or chart: cut.
  - A setting for top effort: F 1, H 1, C 3. 1 < 6. Cut.
  - Changing `CLAUDE_GRILL_DEFAULT` for repos with no entry: owner said existing repos keep theirs. Cut.
- **Thread and cache findings (Codex and Claude, 28 Oct).** Codex: the effort is set on the resume call of each round's driver, not on the turn call; the driver reports the applied effort back, and the test reads it from the run record. Claude: each round's `query()` takes `effort` together with `resume`, so one session can run rounds at two efforts. Neither path starts a new thread. What either tool does to its prompt cache is not stated in what Forge reads, so it stays unmeasured and the owner compares `cached_input_tokens` after a week.
  - Claude rounds through the SDK, not native: the owner's decision of 28 Oct 2026. About 6 lines in `worker.work`. F 3, H 2, C 1. Kept.
  - Redefining `general-purpose`: F 3, H 2, C 1. Kept.
- **Cold read round 1 (28 Oct).** Findings 1 to 5 and 7 are cut: native routing (owner decision above), the review entry, the task order, the pair rule (kept as is), `general-purpose`, and the required-check filter (the code changes, not the plan's meaning). Finding 6 is kept below the bar: a repo's own `none` stays its choice.
- **Planner choices the owner did not make.**
  00. The ladder filters failed checks by the names in `forge.toml`'s `checks` and changes no brief text. Optional checks do not raise effort.
  00. The one-key refusal stays; a missing pair uses the default.
  00. Every Claude worker round, design rounds included, goes through the SDK when it is installed. A Codex session's own native rounds stay native with requested effort.
  0. Claude helpers use the SDK's `agents` option for the helper roles, not a setting or an environment variable; `ClaudeAgentOptions(agents=...)` with `AgentDefinition.model` and `.effort`, as pinned above.
  1. A failure round runs at the higher of its configured effort and the top effort, so a repo's high setting is never lowered.
  2. Top effort is fixed in code, not a `forge.toml` key.
  3. Entry-less kinds in an existing repo follow the new low `WORKER_DEFAULTS`; entries that are written stay.
  4. `CLAUDE_GRILL_DEFAULT` stays Opus for repos with no entry. Only `forge init` writes Sonnet.
  5. Design (user-facing) rounds keep their fixed design effort in every mode; the owner named build, fix and lite.
  6. A round after only a question or an owner note is a normal round, not a failure.
  7. The board change is one added phrase in the round line, no new screen.
  8. The native route changes only the instruction for the round after a failure.
