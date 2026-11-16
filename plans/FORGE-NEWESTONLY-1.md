# Forge tests each rule on a new repo only

5 parts · Risks: none one-way; no product code changes · New moving parts: none

## What changes for you

- No product behaviour changes in this story, and nothing that a client repo sees changes. Only Forge's own tests and Forge's own test rule change. These things move to a second story, planned when every repo is on the newest release: Forge stops in a repo on an older pin (a pin is the release that a repo names in forge.toml), Forge upgrades only from the release just before, forge migrate says that it goes away, and Forge deletes its code that reads or moves records of older releases. Until then, a repo on an older pin still runs its own older release, as today. (Source: your decisions, 15 Nov 2026: "Cut the tests now, refusal later" and "Tests only in this story"; for this title, 16 Nov 2026: "Rename it")
- Forge's own tests check each ordinary rule on a new repo only. Today most of these rules are checked a second time on a repo adopted on an earlier release (v1.2.2); these second runs go. Tests whose subject is the older-release behaviour itself stay until the second story deletes that behaviour, for example the move of old worker chats or the run of a pinned release. The suite keeps one existing test that upgrades a repo from an earlier release (v1.0.0) to the installed release. (Source: your decision, 15 Nov 2026: "New repo only, plus one upgrade test")
- Numbers, measured today: about 946 of 4,674 test cases (in about 471 of 828 test files) are second runs on an adopted repo, and they go. One small old-release test folder (14 lines) goes too. The other four old-release folders (about 10,180 lines, of which 8,374 lines are a copy of Forge v1.2.2's code) stay, because kept tests still read them; they go in the second story. (Source: the planner's measurement, 15 Nov 2026)
- Test time. Today the full test run takes about 90 minutes on this laptop, and each of the six CI test groups takes 12 to 20 minutes (your measurement). In Forge's recorded test times, the cases that go take 56 of 242 minutes (23%). Estimate after the cut: about 70 minutes on this laptop, and about 10 to 16 minutes per CI group. These are estimates, not measurements. (Source: the planner's measurement of the recorded test times, 15 Nov 2026)
- No release hold for this story. The earlier plan held releases until the client repo in daily use is on v1.2.40. This story changes no file that Forge ships to a client repo (Forge ships only its own code, and that code does not change), so a release that holds it gives clients nothing new and the hold protects nothing here. The hold moves to the second story, which changes what a client repo sees. (Source: your decision, 16 Nov 2026: "Yes, drop the hold here")
- What each repo gets. A new repo and an existing repo both get nothing new: no file that Forge writes into a client repo changes. (Source: Forge's rule for new and existing repos)
- Cost. No model call is added, so the model cost does not change. CI minutes go down with the test time. (Source: the planner's estimate)

Design: none. Nothing that a person sees in Forge changes, except Forge's own test rule for the people who build Forge.

## Why

Today most rules of Forge are tested twice: on a new repo, and on a repo adopted on v1.2.2. These second runs are about 946 of 4,674 test cases and about 23% of the recorded test time, and each release adds more. Every change must add and keep such a second run, so each change costs more to build and to review.

Only one client repo is in daily use, and it moves to each new release. So the second runs protect almost nobody. Today there is no workaround: every pull request pays the extra test time.

## Done when

1. **Forge's own tests check each ordinary rule on a new repo only, and the suite keeps one existing test that upgrades a repo from an earlier release to the installed release.**
2. **No test case remains that checks an ordinary rule a second time on a repo adopted on an earlier release, every test whose subject is older-release behaviour stays, and the test rule in Forge's own instructions says this.**
3. **An old-release test folder that no kept test reads is deleted, and the folders that kept tests read stay.**

## Risks

Risks: none one-way. Each part reverts with its pull request; a revert brings back the deleted tests. No file under `src/forge` changes, so no client repo can see a difference.

Trade-offs, in plain words:
- A rule that behaves differently on a repo adopted on an earlier release is no longer checked there. The client repo in daily use is such a repo, so a later change could break it without a test noticing. The second story removes the old paths that make such repos different.
- The kept tests of older-release behaviour and the four old-release folders they read stay until the second story, so part of the old test load stays too.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Rules for every part. No file under `src/forge` changes, and no shipped template, guide or skill copy. Tests run the forge command and never import forge. Before a round ends, run the two cheap checks from AGENTS.md. No client is named in code, tests, texts or commits: write "the client repo in daily use".

**The line.** A part removes a test case when it checks an ordinary rule (a rule that also holds on a new repo, and has a new-repo case or test) a second time on a repo made by an earlier release: copied from an old-release folder, adopted with the vendored v1.2.2 Forge, or given an earlier pin and moved to the installed release. It keeps a test or case whose subject is behaviour that exists only for older releases, because that test is the only test of code that stays until the second story. That code, which this story does not change: the earlier-release chat moves (`codex.preserve_chats`, the fallbacks at `codex.py:213-218` and `worker.py:253-256`), the Codex hook lines of old releases (`codex.EARLIER_COMMANDS`), the old CLAUDE.md lines (`sync.EARLIER`), the old review and ready readers (`close.py:217-221`, `nextstep.py:886-891`), the run-list conversion and `codex._legacy_identity` and the progress fallback (`machine.py:705-714`, `codex.py:910-913`, `event_log.py:72-77`), the run of a pinned release (`repo.check_pin`, `resume_pin`, `run_release`, `githooks.py:139-145`, the hooks' uvx fallback), doctor's install of a newer pin, the merge-rule and Husky-shim repairs for older releases (`sync.install_merge_rules`, `sync.install_shims`), the history readers (`time_records` `legacy_text`, `backfill.py`), and forge migrate. When a selected case reaches one of these paths, the part keeps it and lists it in its pull request.

Why the parts run one after the other. Every TESTS part deletes tests, and a deleted test's key must leave `.test_durations` in the same part: `tests/test_ci_timing_inventory.py::test_1` fails on keys that pytest no longer collects, and `.test_durations` also balances the CI groups. So each TESTS part changes `.test_durations`, and two at the same time would conflict. The chain is RULES, TESTS-1, TESTS-2, TESTS-3, TESTS-4. No part makes `.test_durations` by a script.

Moving a helper before a delete. Before a part deletes a test file or a helper branch, it moves each helper that a kept test imports into the first kept file that imports it, and points the other kept importers there. A helper that kept tests use only for a removed case goes with those cases, in the part that removes its last user.

A folder goes in the same part as the last test that reads it.

**Rules from cold read round 4 (accepted by the owner, 16 Nov 2026, for the builders).**
- (36) Kept old-hook cases. `tests/test_codex_trusts_earlier_forge_hooks.py::test_1_the_worker_starts_with_an_earlier_release_s_hooks_on_the_default_branch` is a kept test (old Codex hook lines); its `[v1.2.2]` case matches rule 1, so it joins the named exceptions of rule 2, beside its `[v1.2.1]` case. The proof under Done-when 1 counts it as an exception.
- (37) What "reaches a kept path" means. A case is kept only when the older-release behaviour is the subject of its assertions: what it asserts is the old chat move, the old hook trust, the legacy record reader, the pinned-release run, doctor's install, the older-release repair or forge migrate. A case that merely runs code that also calls a kept path, for example any `forge sync`, which always calls `codex.preserve_chats` (`sync.py:744`), is not kept for that reason. So `tests/test_close_refuses_binary_test_fixtures.py::test_2_sync_and_work_deliver_plain_text_fixture_guidance[previous-release-repo]` is removed in TESTS-1 as planned, with its folder.
- (38) Rule 5: helpers imported from another file. A case is also selected when its helper, imported from another test file, copies an old-release folder, for example the earlier-adopted client case in `tests/test_fast_test_ignores_own_package_version.py` (around `:92`), which imports `_repo_adopted_on_the_previous_release` from `tests/test_upgrade_command.py:499-503`. Find these by listing every helper function that reads an old-release folder (rule 4's `git grep`) and following each import of it into other test files (`git grep -n "<helper name>" -- tests`). The count per part may rise by a few over the numbers above; each part states its real count.

### What exists (evidence)

Checked in this worktree on 15 Nov 2026 (base `de01ac460`, Forge v1.2.40). A part checks each name again before it starts.

**How tests make the earlier-adopted case.** There is no shared fixture in `tests/conftest.py`. Each test file adds the case with its own `@pytest.mark.parametrize`, with ids such as `adopted`, `adopted-v1.2.2`, `earlier`, `earlier-adopted`, `earlier-adoption`, `previous-adoption`, `previous release`, `previously-adopted`, `existing-repo`, `upgraded`, with a bare `True` (for example `True-fix-record-missing-codex` in `tests/test_worker_and_reader_chats_survive_rounds.py:146-152`), or with an id that says nothing about the release (for example `[upgrade]` in `tests/test_lanes_tests.py:109-124`, whose helper `tests/test_lanes_upgrade.py:17-22` copies `tests/fixtures/adopted-v1.2.2/client`). The case copies `tests/fixtures/adopted-v1.2.2/client` into the repo and sets its pin to the installed release (for example `tests/test_worker_runs_wait_for_machine_load.py::_release`, `:25-36`), runs the real v1.2.2 adoption from `tests/fixtures/forge-v1.2.2/` (30 files read it), or calls a helper from another test file (for example `client` in `tests/test_runs_wait_for_machine_load.py:20`).

**Selection, in four rules** (pytest `--collect-only` and `.test_durations`, this worktree; 4,674 test cases in 828 `tests/test_*.py` files, 1,616 test functions):
1. Ids whose parameter part matches, case-insensitive, `(earlier|previous|previously)[- _]?(adopt|release)|adopted-v1\.2\.\d|v1\.2\.2|(^|[\[-])adopted([\]-]|$)|adopted[- ](upgrade|repo|on)|earlier[\]-]|release adoption|adopted repo|existing[- ](repo|client)|(^|[\[-])existing([\]-]|$)|upgraded[- ]?(repo|client)|(^|[\[-])upgraded([\]-]|$)`: 930 ids.
2. Minus ids that are not about an earlier release, found by reading what each does: the live-app adoption ids `adopted live app`, `adopt with alternate path spelling`, `adopted code conflict`, `adopted fix`, `adopted story already started`; `tests/test_board_running_review.py::test_2_init_delivers_the_board_plugin[existing]` and `tests/test_init_requires_git_identity.py::test_1_init_refuses_before_writes_and_names_git_config[existing-repo]` (both `forge init` on an existing app); `[existing-review]`, `[existing-clean]`, `[claude-existing-queue]`, `[codex-existing-queue]`, `[existing-new]`, `[new-client-existing-roadmap]` (an existing review, queue or roadmap); `[missing-earlier-rounds]` and the two sentence ids of `tests/test_fix_pr_title_whole_sentence.py::test_1` (the words match by chance). Minus the kept-behaviour cases: ids with `legacy` (`[adopted-v1.2.2-legacy timing]`, `[True-legacy-spotted]`, the two `legacy-review-...-previously-adopted` ids), the eight `previous-release-round-...` ids of `tests/test_worker_and_reader_chats_survive_rounds.py::test_1` and `::test_2` (old chat fallback), and `tests/test_husky_hooks_survive_install.py::test_1_...[adopted-on-v1.2.7]` (retiring v1.2.7 Husky shims).
3. Plus ids that select the earlier-adopted case with a bare `True`, in files that parametrize `adopted`, `previous`, `earlier` or `upgraded` and name an old-release folder or helper: about 39 ids in 15 files (each confirmed by reading it).
4. Plus cases whose helper copies an old-release folder whatever their id says: run `git grep -l -e adopted-v1.2.2 -e forge-v1.2.2 -e doctor-v1.2.2 -e forge-v1.2.7-husky -e previous-release-fixture-guidance -- tests ':!tests/fixtures'` (295 files today) and read each reading case that rules 1 to 3 did not select. Known: `tests/test_lanes_tests.py::test_2_workers_and_close_share_one_test_lane[upgrade]`.
In all about 946 cases in 471 files, 55.7 recorded minutes of 242.4 (`.test_durations` holds 3,910 recorded cases). By file name: `test_a*` to `test_c*` 140 files, 275 cases; `test_d*` to `test_m*` 130 files, 224 cases; `test_n*` to `test_r*` 87 files, 168 cases; `test_s*` to `test_z*` 114 files, 279 cases. Rule 4 can add a few more. Only one function has no new-repo case: `tests/test_guides_agree.py::test_4_an_existing_repo_gets_the_non_root_rule_and_keeps_its_app_files`; it checks an ordinary rule on an existing repo, so TESTS-2 turns it into a new-repo case when no other test in the file covers that rule, else deletes it.

**Old-release folders and their readers after the cut.**
- `previous-release-fixture-guidance/` (2 files, 14 lines): its only reader is `tests/test_close_refuses_binary_test_fixtures.py::test_2_sync_and_work_deliver_plain_text_fixture_guidance[previous-release-repo]`, a second run, so TESTS-1 deletes the case and the folder.
- `adopted-v1.2.2/` (9 files, 1,075 lines): stays; kept readers include `tests/test_codex_trusts_earlier_forge_hooks.py` (old hook lines) and the `[adopted-v1.2.2-legacy timing]` case.
- `forge-v1.2.2/` (30 files, 8,374 lines) and `forge-v1.2.2.md`: stays; kept readers include `tests/test_failed_legacy_review_history.py`, `tests/test_mixed_review_attempt_history.py`, `tests/test_outstanding_adopted_item_time.py` (history readers) and the chat tests in `tests/test_worker_and_reader_chats_survive_rounds.py`.
- `doctor-v1.2.2/` (8 files, 695 lines) and `doctor-v1.2.2.md`: stays; `tests/test_doctor_fix_files.py:316-319` reads its stale workflow as the input of "a stale tests workflow is repaired in place", which is not a second run.
- `forge-v1.2.7-husky/` (6 files, 34 lines): stays; its kept reader is the `[adopted-on-v1.2.7]` and `[v1.2.7-after-install]` cases of `tests/test_husky_hooks_survive_install.py::test_1`.
- Not old-release folders, and they stay: `release-v1.2.6-picker/`, `copied-client/`, `husky-v9.1.7/`, `before-test-runner/`, `pr-check-before-branch-diff/`. Two of them name old folders in their text (`before-test-runner/README.md:3`, `release-v1.2.6-picker/changes.json:71`), so no proof greps for names.

**The kept upgrade test.** `tests/test_upgrade_to_installed_release.py::test_1_upgrade_to_installed_release_continues_during_runs[new]`. Its repo comes from the test's own setup (`up` in `tests/test_upgrade_command.py`, on `env` in `tests/test_close.py:264`): a small hand-written `forge.toml` and `forge sync`, not `forge init`. The test sets the default branch's pin to v1.0.0, runs the real `forge upgrade <installed release>` while another repo's read holds a machine place, and checks that the upgrade makes one fix, skips the install, ends Ready with the fix pinning the installed release, and leaves the other run alone. It does not check that an upgrade keeps every setting that `forge init` writes. Its `[earlier-adoption]` case goes in TESTS-4. The other upgrade-command tests (`tests/test_upgrade_command.py` and the `test_upgrade_*.py` files) check the upgrade command's own rules and keep their new-repo cases.

**Where the test rule is written.** Only in this repo's `AGENTS.md`: `:111` (Building Forge), `:118-124` (Review rules) and `:171-173` (Tests for Forge). `AGENTS.md`'s review rules sit outside the `forge:begin` and `forge:end` lines, so `forge sync` ships none of them. The wheel holds only `src/forge` (`pyproject.toml:23`), so no test or `AGENTS.md` change reaches a client repo.

### Decisions

- **The test rule (RULES).** In `AGENTS.md`:
  - `:111` stays: "Every change says what a new client repo and an existing client repo each get."
  - The review rule `:118-124` becomes: "A change to Forge says what a new client repo (init or adoption of a live app) and an existing client repo (on upgrade to the new release) each get. Each ordinary rule is tested on a new repo only; do not add a second case on a repo adopted on an earlier release. Tests whose subject is behaviour that exists only for older releases (old record readers and movers, the run of a pinned release, repairs of older releases' files, forge migrate) stay with that behaviour. The suite keeps one test of the upgrade from an earlier release to the installed release (`tests/test_upgrade_to_installed_release.py`); a change that must convert a record during the upgrade extends that test. Report as P1 a change that does not say what each repo gets. Report a new earlier-adopted case of an ordinary rule as a deletion candidate. A release's version bump changes no behaviour and needs no new upgrade test."
  - "Tests for Forge" `:171-173` becomes: "Each ordinary rule is tested on a new repo. Tests of older-release behaviour stay with that behaviour. The suite has one upgrade test, from an earlier release to the installed release."
- **Deleting a case (TESTS).** In each file of the part's range: remove every case that the four rules select, and the code that only that case reached; keep the new-repo case as it is. When the test then has one case left, keep its id, so its `.test_durations` key stays valid. A part reruns rules 1 to 3 on its range and reads rule 4's cases, and states in its pull request the cases and files it removed and any selected case it kept under the line above.

### Done-when details

1. New repo only, with the kept upgrade test (RULES, TESTS-1 to TESTS-4).
   - Proof: after TESTS-4, rules 1 and 3 select no collected id beyond the ids that rule 2 names; the rule-4 cases listed in the parts' pull requests are gone; `tests/test_upgrade_to_installed_release.py::test_1_upgrade_to_installed_release_continues_during_runs[new]` is collected and passes; `tests/test_ci_timing_inventory.py` passes. No new test: the deletions and the green suite are the proof.
2. Kept behaviour and the rule (RULES, TESTS-1 to TESTS-4).
   - Proof: every id that rule 2 names as kept is still collected and passes, and `tests/test_codex_trusts_earlier_forge_hooks.py`, `tests/test_failed_legacy_review_history.py`, `tests/test_mixed_review_attempt_history.py`, `tests/test_outstanding_adopted_item_time.py` and `tests/test_worker_and_reader_chats_survive_rounds.py` tests 12 to 19 (at least one case each) still run; `AGENTS.md` holds the rewritten texts above.
3. Old-release folders (TESTS-1).
   - Proof: `tests/fixtures/previous-release-fixture-guidance/` no longer exists; the four other old-release folders exist; the suite is green. No proof greps for folder names, because kept fixtures name them in their text.

### What each part removes

- RULES: text only, in `AGENTS.md`.
- TESTS-1 (`test_a*` to `test_c*`): about 275 cases in 140 files, and the 14-line folder `previous-release-fixture-guidance/`.
- TESTS-2 (`test_d*` to `test_m*`): about 224 cases in 130 files, the `[upgrade]` case of `tests/test_lanes_tests.py` and then the helper file `tests/test_lanes_upgrade.py`.
- TESTS-3 (`test_n*` to `test_r*`): about 168 cases in 87 files.
- TESTS-4 (`test_s*` to `test_z*`): about 279 cases in 114 files, and the helper branches no kept test uses.
- Principle 6: production code none changed; tests about 946 cases removed and none added; test data 14 lines removed.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| RULES | The test rule: new repo only | The rewritten rule in Forge's own instructions: ordinary rules on a new repo only, older-release behaviour tests kept, the kept upgrade test named | 1, 2 | `AGENTS.md` | none (instructions only) | | no | |
| TESTS-1 | Remove second runs, files a to c | About 275 earlier-adopted second runs removed, and the one old-release folder that no kept test reads | 1, 2, 3 | `tests/test_[a-c]*.py`, `tests/*.py`, `tests/fixtures/previous-release-fixture-guidance/*`, `.test_durations` | none new (deletions); `tests/test_ci_timing_inventory.py` (unchanged, stays green) | RULES | no | |
| TESTS-2 | Remove second runs, files d to m | About 224 second runs removed, with the lanes `[upgrade]` case and its helper file | 1, 2 | `tests/test_[d-m]*.py`, `tests/*.py`, `.test_durations` | none new (deletions) | TESTS-1 | no | |
| TESTS-3 | Remove second runs, files n to r | About 168 second runs removed | 1, 2 | `tests/test_[n-r]*.py`, `tests/*.py`, `.test_durations` | none new (deletions) | TESTS-2 | no | |
| TESTS-4 | Remove second runs, files s to z | About 279 second runs and the helper branches no kept test uses; the kept upgrade test's `[new]` case stays | 1, 2 | `tests/test_[s-z]*.py`, `tests/*.py`, `.test_durations` | none new (deletions); `tests/test_upgrade_to_installed_release.py` (its `[new]` case stays green) | TESTS-3 | no | |

Order. RULES first, so the reviews of the TESTS parts read the new rule from the default branch. TESTS-1 to TESTS-4 one after the other (see "Why the parts run one after the other"). Sizes outside tests and Markdown: 0 for every part.

New moving parts: none

## Notes

- **Owner decisions (15 Nov 2026, settled).** 1 "Support only the newest release". 2 "One step back only". 3 "Refuse and say upgrade". 4 "New repo only, plus one upgrade test". 5 forge migrate: "Keep it one more release" with a notice. 6 "After the client is on v1.2.40". After round 2: "Cut the tests now, refusal later". After round 3: "Tests only in this story". This story now carries decision 4 only; decisions 1, 2, 3, 5 and 6 belong to the second story.
- **The second story (title only).** "Forge stops in a repo on an older pin and upgrades one release at a time": the refusal, the one-step upgrade, the end of running a pin through uv, the forge migrate notice, the release hold, and the deletion of the older-release code listed under "The line" with its kept tests and the four remaining old-release folders. Cold read notes 1 to 9, 16 to 24 and 26 to 29, 33 and 34 hold its known cases.
- **Title (settled, 16 Nov 2026: "Rename it").** The story is now "Forge tests each rule on a new repo only", in this plan, in `plans/roadmap.json` and in the story record `.factory/stories/FORGE-NEWESTONLY-1/story.json`; the key stays FORGE-NEWESTONLY-1. The release hold is dropped for this story (16 Nov 2026: "Yes, drop the hold here").
- **Changed in the owner's part after round 4.** The title, and the Sources of the title and of the dropped release hold (16 Nov 2026); nothing else.
- **Changed in the owner's part after round 3.** The first line (no product change, what moved, both sources); the tests line (ordinary rules only, older-release behaviour tests kept, the upgrade test described as it is); the numbers (about 946 cases in about 471 files; 14 lines of test data now, about 10,180 lines later); the release hold dropped, with the reason; the "what each repo gets" line; the Done-when list (three items); Risks.
- **Scores (F x H >= 2 x C).** The test cut: F 3 (every pull request pays the old test time), H 2, C 2: 6 >= 4, kept.
- **Not verified.**
  - The full-suite time after the cut: an estimate from recorded test times, which cover 3,910 of 4,674 cases.
  - The 39 bare-`True` cases and the rule-4 cases: found by pattern and by readers of the folders; the parts confirm each by reading it.
- No client is named anywhere in this story's code, tests, texts or commits.
