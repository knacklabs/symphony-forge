# Forge supports only its newest release

7 parts · Risks: none one-way in data; releases wait until the client repo is on v1.2.40 · New moving parts: none

## What changes for you

- How pins work does not change in this story. A pin is the Forge release that a repo names in forge.toml. A repo on an older pin still runs its own older release, as today, and forge upgrade and forge migrate work as today. Three things move to a second, small story: Forge stops in a repo on an older pin, Forge upgrades only from the release just before, and forge migrate says that it goes away. That story is planned after the client repo in daily use is on v1.2.40. (Source: your decision, 15 Nov 2026: "Cut the tests now, refusal later")
- Forge's own tests check each rule on a new repo only. The suite keeps one existing test that upgrades a repo from an earlier release to the installed release. Measured today: about 960 of 4,674 test cases (in about 470 of 828 test files) run a rule a second time on a repo adopted on release v1.2.2. These cases go, and so do five folders of old-release test data (about 10,200 lines, of which 8,374 lines are a copy of Forge v1.2.2's code). The test rule in Forge's own instructions for reviewers and builders is rewritten to say this. (Source: your decision, 15 Nov 2026: "New repo only, plus one upgrade test")
- Code that reads or moves records in formats that no repo on v1.2.40 still has goes: about 200 lines. These are the move of worker chats that releases before v1.2.10 kept on the laptop, the Codex hook lines of releases before v1.2.9, the list of CLAUDE.md lines of releases before v1.2.13, and the readers of review and ready records of releases before v1.2.5 and v1.2.11. Code that older releases still need while they run beside the new one on a laptop stays: the shared list of runs, and the records of running processes. The readers of past work that Forge wrote into git and pull requests also stay, because the board shows that history. (Source: your decision, 15 Nov 2026: "Support only the newest release")
- What each repo gets. A new repo: nothing changes. An existing repo on v1.2.40: nothing changes when it upgrades. A repo that upgrades straight from a release older than v1.2.13 to the release with this change can lose a little: its old worker chats on the laptop start again, and a few old records are read again (see Risks). (Source: Forge's rule for new and existing repos)
- Test time. Today the full test run takes about 90 minutes on this laptop, and each of the six CI test groups takes 12 to 20 minutes (your measurement). In Forge's recorded test times, the cases that go take 56 of 242 minutes (23%). Estimate after the cut: about 70 minutes on this laptop, and about 10 to 16 minutes per CI group. These are estimates, not measurements. (Source: the planner's measurement of the recorded test times, 15 Nov 2026)
- The release with this change goes out only after the client repo in daily use is on v1.2.40. Until then, Forge publishes no new release once a part of this change has merged. (Source: your decision, 15 Nov 2026: "After the client is on v1.2.40")
- Cost. The change adds no model call, so the model cost does not change. CI minutes go down with the test time. (Source: the planner's estimate)

Design: none. Nothing that a person sees in Forge changes, except Forge's own test rule for the people who build Forge.

## Why

Today most rules of Forge are tested twice: on a new repo, and on a repo adopted on v1.2.2. These second runs are about 960 of 4,674 test cases and about 23% of the recorded test time, and each release adds more. Forge also keeps code that reads record formats of releases from October 2026 and before. Every change must keep these old paths working, so each change costs more to build and to review.

Only one client repo is in daily use, and it moves to each new release. So the second test runs and the old readers serve almost nobody. Today there is no workaround: every pull request pays the extra test time, and every builder carries the old code.

## Done when

1. **Forge's own tests check each rule on a new repo only, and the suite keeps one existing test that upgrades a repo from an earlier release to the installed release.**
2. **No test case adopted on an earlier release and no old-release test folder remains, and the test rule in Forge's own instructions says this.**
3. **Forge's code no longer moves worker chats of releases before v1.2.10, trusts Codex hook lines of releases before v1.2.9, lists CLAUDE.md lines of releases before v1.2.13, or reads review and ready records of releases before v1.2.5 and v1.2.11.**
4. **The release that holds this change goes out only after the client repo in daily use is on v1.2.40.**

## Risks

Risks: none one-way in data. Each part reverts with its pull request; a revert brings back the deleted tests and code. No record format changes, and no record on disk or in git is deleted.

What the release hold protects. Upgrades from any older release still work after this change. A repo that upgrades straight from an older release to the release with this change meets the new code without the old readers. Checked in the code, case by case:
- From a release before v1.2.10: the worker chats that this laptop kept locally are not moved into their branches, so the next round of those items starts a new chat. The old chat records stay on the laptop.
- From a release before v1.2.13: lines that an old Forge wrote into CLAUDE.md are copied into AGENTS.md as if the team wrote them. The upgrade's pull request shows them, and a person can delete them there.
- From a release before v1.2.9: while the upgrade waits for its merge, Codex worker turns in that repo stop with Forge's existing "Codex doesn't trust this project" line, because the default branch still holds the old hook lines. After the merge they run.
- From a release before v1.2.5: an item reviewed under that release is reviewed again once. From a release before v1.2.11: a pull request that release closed is not seen as ready, so close runs again.
None of these loses data or makes a command fail with an error. With the hold, the only client repo in daily use is on v1.2.40 first, so it meets none of them.

Kept because of this check: the conversion of the shared run list (entries of releases before v1.2.7), the reading of process start times without a time zone (releases before v1.2.8) and the progress fallback for runs without a live file (releases before v1.2.14). Older releases can still run beside the new one on the same laptop, through uv, and they share that run list. Without these readers the new release could take a running old process for an ended one, and a progress call could fail on a missing value. They go in the second story, when Forge stops older pins.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Rules for every part. No new `forge` command, no new setting, no new dependency, no model call. Do not grow `close.py` (1,200 lines), `codex.py` (1,200), `review.py` (1,199), `board.py` (1,197), `nextstep.py` (1,193) or `repo.py` (1,193); CODE shrinks `codex.py`, `close.py` and `nextstep.py`. Tests run the forge command and never import forge. A part that changes what a coordinator or worker does updates `src/forge/templates/skill.md` and runs `forge sync` for `.claude/skills/forge/` and `.codex/skills/forge/` in the same part. Before a round ends, run the two cheap checks from AGENTS.md. No client is named in code, tests, texts or commits: write "the client repo in daily use".

Out of scope, unchanged (the second story): `repo.check_pin`, `resume_pin`, `run_release`, the git hook hand-over (`githooks.py:139-145`), the hooks' uvx fallback (`sync.LAUNCHER_TEXT`, `.forge/hooks.sh`), doctor's install of a newer pinned release (`doctor.py:331-346`), `upgrade.py`, the pane's older-Forge line (`src/forge/mod/hooks/register.ts`), `migrate.py` and `migrate-skill.md`, the run-list and process-record readers named under Risks, and the history readers (`time_records` `legacy_text`, `backfill.py`).

Why the parts run one after the other. Every part except RULES and FIXTURES deletes tests, and a deleted test's key must leave `.test_durations` in the same part: `tests/test_ci_timing_inventory.py::test_1` fails on keys that pytest no longer collects, and `.test_durations` also balances the CI groups. So those parts all change `.test_durations`, and two of them at the same time would conflict. The chain is RULES, TESTS-1, TESTS-2, TESTS-3, TESTS-4, CODE, FIXTURES. No part makes `.test_durations` by a script.

Moving a helper before a delete. Before a part deletes a test file or a helper branch, it moves each helper that a kept test imports into the first kept file that imports it, and points the other kept importers there. A helper that kept tests use only for an earlier-adopted case goes with those cases. A kept test that reads an old-release folder only to make a repo is changed to make its repo with `forge init`; a test that needs the old-release content itself is an earlier-adopted test and goes.

### What exists (evidence)

Checked in this worktree on 15 Nov 2026 (base `de01ac460`, Forge v1.2.40). A part checks each name again before it starts.

**How tests make the earlier-adopted case.** There is no shared fixture in `tests/conftest.py`. Each test file adds the case with its own `@pytest.mark.parametrize`, with ids such as `adopted`, `adopted-v1.2.2`, `earlier`, `earlier-adopted`, `earlier-adoption`, `previous-adoption`, `previous-release adoption`, `previously-adopted`, `existing-repo`, `upgraded`, or with a bare `True` (for example `True-fix-record-missing-codex` in `tests/test_worker_and_reader_chats_survive_rounds.py:146-152`). The case copies `tests/fixtures/adopted-v1.2.2/client` into the repo and sets its pin to the installed release (for example `tests/test_worker_runs_wait_for_machine_load.py::_release`, `:25-36`), or calls a helper from another test file (for example `client` in `tests/test_runs_wait_for_machine_load.py:20`, imported by `tests/test_agent_admission_priorities.py`). About 30 files run the real v1.2.2 adoption from `tests/fixtures/forge-v1.2.2/` (README `tests/fixtures/forge-v1.2.2.md`).

**Measurements** (pytest `--collect-only` and `.test_durations`, this worktree):
- 4,674 test cases in 828 `tests/test_*.py` files (819 with collected tests); 1,616 test functions.
- Earlier-adopted cases, by three rules:
  1. Ids whose parameter part matches, case-insensitive, `(earlier|previous|previously)[- _]?(adopt|release)|adopted-v1\.2\.\d|v1\.2\.2|(^|[\[-])adopted([\]-]|$)|adopted[- ](upgrade|repo|on)|earlier[\]-]|release adoption|adopted repo|existing[- ](repo|client)|(^|[\[-])existing([\]-]|$)|upgraded[- ]?(repo|client)|(^|[\[-])upgraded([\]-]|$)`: 930 ids.
  2. Minus ids that are not about an earlier release, found by reading what each `existing` and `upgraded` id does (the ids with no plain adopt, earlier, previous or v1.2.2 word): the live-app adoption ids `adopted live app`, `adopt with alternate path spelling`, `adopted code conflict`, `adopted fix`, `adopted story already started`; `tests/test_board_running_review.py::test_2_init_delivers_the_board_plugin[existing]` and `tests/test_init_requires_git_identity.py::test_1_init_refuses_before_writes_and_names_git_config[existing-repo]` (both `forge init` on an existing app); `[existing-review]`, `[existing-clean]`, `[claude-existing-queue]`, `[codex-existing-queue]`, `[existing-new]` and `[new-client-existing-roadmap]` (an existing review, queue or roadmap, not a release). The `upgraded` ids reach a repo moved from an earlier release and count. 8 of these were in rule 1.
  3. Plus ids that select the earlier-adopted case with a bare `True`, in files that parametrize `adopted`, `previous`, `earlier` or `upgraded` and name an old-release folder or helper: about 39 ids in 15 files (a part confirms each by reading it).
  In all about 961 cases in 472 files, 56.5 recorded minutes over 713 recorded cases. Only one test function has no new-repo case: `tests/test_guides_agree.py::test_4_an_existing_repo_gets_the_non_root_rule_and_keeps_its_app_files`.
- By file name: `test_a*` to `test_c*` 140 files, 279 cases; `test_d*` to `test_m*` 131 files, 227 cases; `test_n*` to `test_r*` 87 files, 168 cases; `test_s*` to `test_z*` 114 files, 287 cases.
- `.test_durations`: 3,910 recorded cases, 242.4 minutes of serial test time.
- Old-release folders: `adopted-v1.2.2/` (9 files, 1,075 lines), `forge-v1.2.2/` (30 files, 8,374 lines), `doctor-v1.2.2/` (8 files, 695 lines), `forge-v1.2.7-husky/` (6 files, 34 lines), `previous-release-fixture-guidance/` (2 files, 14 lines), plus `forge-v1.2.2.md` and `doctor-v1.2.2.md`. They stay, as they are not old-release folders: `release-v1.2.6-picker/` (Forge's own test picker replay), `copied-client/` (forge migrate), `husky-v9.1.7/`, `before-test-runner/`, `pr-check-before-branch-diff/`.
- Full-suite time: the owner's figures (about 90 minutes on the laptop, 12 to 20 minutes per CI group, six groups in `.github/workflows/forge.yml:48`). Not measured again here.

**The kept upgrade test.** `tests/test_upgrade_to_installed_release.py::test_1_upgrade_to_installed_release_continues_during_runs[new]`: a repo made by `forge init` whose default branch pins v1.0.0 runs `forge upgrade <installed release>` with the real command, while another repo's read holds a machine place, and ends Ready with the fix pinning the installed release. Its `[earlier-adoption]` case goes in TESTS-4; the `[new]` case stays unchanged as the suite's upgrade proof. The other upgrade-command tests (`tests/test_upgrade_command.py` and the `test_upgrade_*.py` files) test the upgrade command's own rules and keep their new-repo cases.

**Old-format code that CODE deletes** (each newer format's first release found with `git log -S` and `git tag --contains`):
- Earlier-release chats: `codex.preserve_chats` (`codex.py:255-397`, 143 lines), called by sync (`sync.py:744`), with refusals `chat_owner`, `chat_origin`, `chat_dirty` (`codex.py:80-85`) and `old_run` (`:102-104`); the fallback for chats kept without the last tool (`codex.py:213-218`; `worker.py:253-256`, where `state["worker"]` exists since v1.2.2). Chats in branches shipped in v1.2.10 and `saves_chat` in v1.2.11.
- Codex hook lines: `codex.EARLIER_COMMANDS` (`codex.py:68-72`, hooks of v1.0.0 to v1.2.8) and its use in `FORGE_HOOKS` (`:76`).
- One-off readers: `sync.EARLIER` (`sync.py:189-205`, AGENTS.md and CLAUDE.md lines of earlier releases, since v1.2.13) and its use in `_agents` (`:217`); the review record without `branch_diff` (`close.py:217-221`, `:305`; `branch_diff` since v1.2.5); the ready evidence of an older release's pull request (`nextstep.py:886-891`; ready records since v1.2.11).
- The guide paragraph about sync keeping earlier-release chats (`skill.md:1938-1948`, from "Upgrade's sync commits earlier-release chat bindings" to "Keep `.git/forge` until the upgrade finishes.").
- In all about 200 lines of Python by these ranges.

**Checked and kept** (Risks): the run-list conversion (`machine.py:705-714`, the `legacy` flag `:168`, `:442`, the lanes skip `:557-558`; entries without `id` from releases before v1.2.7), `codex._legacy_identity` (`codex.py:910-913`, used at `:923`, `machine.py:730`, `:807`; start times without a time zone, before v1.2.8), and the progress fallback (`event_log.py:72-77`; without it `saved["round"]` at `:86` raises `KeyError` for a run with no live file). Older pinned releases still run through uv beside the new release and write to the same run list, so these readers protect running processes and a command.

**Not old-release code, though the words match:** `migration_warnings.py` (database migration numbers of the client's app), `releases.py` (the board's releases), `app_baseline.py:17` and `tests/test_migrations_keep_previous_release.py` (the client app's previous release), `tests/test_pytest_picker_supports_older_clients.py` (old pytest versions).

**Where the test rule is written.** Only in this repo's `AGENTS.md`: `:111` (Building Forge), `:118-124` (Review rules) and `:171-173` (Tests for Forge). `src/forge/standards.md`, `src/forge/templates/skill.md`, `run-reference.md`, `brief.md` and the review templates do not hold it.

### Decisions

- **The test rule (RULES).** In `AGENTS.md`:
  - `:111` stays: "Every change says what a new client repo and an existing client repo each get."
  - The review rule `:118-124` becomes: "A change to Forge says what a new client repo (init or adoption of a live app) and an existing client repo (on upgrade to the new release) each get. Each rule is tested on a new repo only. The suite keeps one test of the upgrade from an earlier release to the installed release (`tests/test_upgrade_to_installed_release.py`); a change that must convert a record during the upgrade extends that test. Report as P1 a change that does not say what each repo gets. Report an earlier-adopted test case or a new old-release test folder as a deletion candidate. A release's version bump changes no behaviour and needs no new upgrade test."
  - "Tests for Forge" `:171-173` becomes: "Each rule is tested on a new repo. The suite has one upgrade test, from an earlier release to the installed release; it has no earlier-adopted cases and no old-release test folders."
- **Deleting a case (TESTS).** In each file of the part's range: remove every earlier-adopted case (the three rules above), and the code that only that case reached; keep the new-repo case as it is. When the test then has one case left, keep its id, so its `.test_durations` key stays valid. Leave a helper's earlier-adopted branch while any kept test still passes it; the part that removes its last user removes it. A test that CODE names is not touched by TESTS. The one function with no new-repo case (`tests/test_guides_agree.py::test_4_...`) is in TESTS-2: delete it when a new-repo test in the same file covers its rule, else turn it into a new-repo case. Each part reruns the measurement on its range and states in its pull request the cases and files it removed.
- **CODE.** Delete the code listed under "Old-format code that CODE deletes", and in `worker.py:253-256` keep only `state.get("worker")` as the last tool. Then delete each test that fails only because it feeds a deleted reader, and list them in the pull request. Known: `tests/test_codex_trusts_earlier_forge_hooks.py`; `tests/test_worker_and_reader_chats_survive_rounds.py` tests 12 to 19; `tests/test_sync_not_blocked_by_other_runs.py::test_2`; the chat-move cases in `tests/test_sync_keeps_chats_without_checkouts.py`, `tests/test_sync_preserved_spec_chats.py` and `tests/test_spec_chat_upgrade_amendment.py`; the `legacy-review` cases of `tests/test_close_reuses_git_facts.py::test_1`. New and existing repos: a new repo never had these records; an existing repo on v1.2.40 has none of them; a repo upgrading from older releases meets the cases under Risks.
- **FIXTURES.** One part that deletes the five folders and two README files once `git grep` finds no reader. It is one part because it is a pure deletion of test data, with no code and no test logic: the size rule counts no lines under `tests/`, and the whole review is the one `git grep`. Five parts would repeat that one check.

### Done-when details

1. New repo only, with the kept upgrade test (RULES, TESTS-1 to TESTS-4).
   - Proof: after TESTS-4, rule 1 of the measurement matches no collected id except the ids excluded by rule 2, and no `True` case that selects an old-release folder remains; `tests/test_upgrade_to_installed_release.py::test_1_upgrade_to_installed_release_continues_during_runs[new]` is collected and passes; `tests/test_ci_timing_inventory.py` passes. No new test: the deletions and the green suite are the proof.
2. No old cases or folders, and the rule (RULES, TESTS-1 to TESTS-4, FIXTURES).
   - Proof: after FIXTURES, `git grep -n "adopted-v1.2.2\|forge-v1.2.2\|doctor-v1.2.2\|forge-v1.2.7-husky\|previous-release-fixture-guidance" tests src` finds nothing; `AGENTS.md` holds the rewritten texts above.
3. Old-format readers gone (CODE).
   - Proof: `git grep -n "preserve_chats\|EARLIER_COMMANDS\|^EARLIER\|legacy_diff\|older release's pull request" src/forge` finds nothing; the suite stays green; the readers under "Checked and kept" are unchanged.
4. Release hold (no part).
   - By hand, at the release fix: the coordinator asks the owner whether the client repo in daily use pins v1.2.40, and starts the release only after a yes. Nothing in the code can see the client repo. From the first merged part until then, no release is tagged.

### What each part removes

- RULES: text only, in `AGENTS.md`.
- TESTS-1 (`test_a*` to `test_c*`): about 279 cases in 140 files. TESTS-2 (`test_d*` to `test_m*`): about 227 in 131. TESTS-3 (`test_n*` to `test_r*`): about 168 in 87. TESTS-4 (`test_s*` to `test_z*`): about 287 in 114. A part's own count can be a little lower: cases that CODE names stay for it.
- CODE: about 200 Python lines and the guide paragraph, with their tests.
- FIXTURES: about 10,200 lines of test data, 8,374 of them the copy of Forge v1.2.2.
- Principle 6, estimates (the builders report real numbers): production code about 200 lines removed and none added; tests about 961 cases and about 10,200 lines of test data removed, none added.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| RULES | The test rule: new repo only | The rewritten rule in Forge's own instructions, naming the kept upgrade test | 1, 2 | `AGENTS.md` | none (instructions only) | | no | |
| TESTS-1 | Remove earlier-adopted cases, files a to c | About 279 earlier-adopted cases removed; new-repo cases unchanged | 1, 2 | `tests/test_[a-c]*.py`, `tests/*.py`, `.test_durations` | none new (deletions); `tests/test_ci_timing_inventory.py` (unchanged, stays green) | RULES | no | |
| TESTS-2 | Remove earlier-adopted cases, files d to m | About 227 earlier-adopted cases removed | 1, 2 | `tests/test_[d-m]*.py`, `tests/*.py`, `.test_durations` | none new (deletions) | TESTS-1 | no | |
| TESTS-3 | Remove earlier-adopted cases, files n to r | About 168 earlier-adopted cases removed | 1, 2 | `tests/test_[n-r]*.py`, `tests/*.py`, `.test_durations` | none new (deletions) | TESTS-2 | no | |
| TESTS-4 | Remove earlier-adopted cases, files s to z | About 287 earlier-adopted cases and the helper branches no kept test uses; the kept upgrade test's `[new]` case stays | 1, 2 | `tests/test_[s-z]*.py`, `tests/*.py`, `.test_durations` | none new (deletions); `tests/test_upgrade_to_installed_release.py` (its `[new]` case stays green) | TESTS-3 | no | |
| CODE | Delete readers of old record formats | The earlier-release chat moves, the old Codex hook lines, the old CLAUDE.md line list, the old review and ready readers and their guide paragraph, with their tests | 3 | `src/forge/codex.py`, `src/forge/sync.py`, `src/forge/worker.py`, `src/forge/close.py`, `src/forge/nextstep.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/*`, `.codex/skills/forge/*`, `tests/*.py`, `.test_durations` | none new (deletions); the tests named under CODE | TESTS-4 | no | |
| FIXTURES | Delete the old-release test folders | The five old-release folders and their two README files, once no test reads them | 2 | `tests/fixtures/adopted-v1.2.2/*`, `tests/fixtures/forge-v1.2.2/*`, `tests/fixtures/forge-v1.2.2.md`, `tests/fixtures/doctor-v1.2.2/*`, `tests/fixtures/doctor-v1.2.2.md`, `tests/fixtures/forge-v1.2.7-husky/*`, `tests/fixtures/previous-release-fixture-guidance/*` | none new (deletion); the `git grep` under Done-when 2 | CODE | no | |

Order. RULES first, so the reviews of the TESTS parts read the new rule from the default branch. TESTS-1 to TESTS-4 next; they change no behaviour. CODE after them, so the earlier-adopted cases that reach the old readers are already gone and CODE deletes the rest of their tests. FIXTURES last, once nothing reads the folders. Every part except RULES and FIXTURES changes `.test_durations`, so they run one after the other (see "Why the parts run one after the other"). Sizes outside tests and Markdown: RULES 0; TESTS 0; CODE about 200, deletions only; FIXTURES 0. Done-when 4 has no part: it is the release step's check by hand.

New moving parts: none

## Notes

- **Owner decisions (15 Nov 2026, settled).** 1 "Support only the newest release". 2 "One step back only". 3 "Refuse and say upgrade". 4 "New repo only, plus one upgrade test". 5 forge migrate: "Keep it one more release" with a notice, then a later deletion. 6 "After the client is on v1.2.40". After cold read round 2: "Cut the tests now, refusal later": this story keeps only the test cut and the old-format readers; decisions 2, 3 and 5 move to the second story.
- **The second story (title only, planned after the client repo in daily use is on v1.2.40).** "Forge stops in a repo on an older pin and upgrades one release at a time": the refusal and its next steps, the one-step upgrade, the end of running a pin through uv (also in the hooks' launcher and on branches that keep an old launcher), doctor's newer-pin install, the pane's older-Forge line, the run-list and process-record readers kept here, and the forge migrate notice. Round 1 notes 1 to 9 and round 2 notes 16 to 24 hold its known cases.
- **Follow-ups (titles only).** "Remove forge migrate", after the second story.
- **Assumptions.** The client repo in daily use moves to v1.2.40 within days. The story keeps its title, which matches its roadmap entry, although this story is now the first half of that goal.
- **Scores (F x H >= 2 x C).** The test cut: F 3 (every pull request pays the old test time), H 2, C 2: 6 >= 4, kept. The old-format readers' deletion: F 3 (every builder carries them), H 1, C 1: 3 >= 2, kept.
- **Not verified.**
  - The full-suite time after the cut: an estimate from recorded test times, which cover 3,910 of 4,674 cases.
  - The 39 bare-`True` cases: found by a pattern, confirmed by reading only for the samples in `tests/test_worker_and_reader_chats_survive_rounds.py`.
  - The behaviour of a release before v1.2.7 when the new release rewrites the shared run list: not read, and not reached, because CODE keeps that conversion.
- No client is named anywhere in this story's code, tests, texts or commits.
