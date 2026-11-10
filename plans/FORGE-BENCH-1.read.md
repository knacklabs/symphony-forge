---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-10T19:37:00.253768+00:00
seconds: 418.247
read_hash: 1871e42e0d0326e0eec12cb6de14f9b7fbde96d9
round: 5
passed: no
doc_seen: 1871e42e0d0326e0eec12cb6de14f9b7fbde96d9
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 8084915edafdaaeaff205ff1d2182c08fe32fb51
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1c67a-137f-7750-ac95-00994b5ef6e8
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

1. Blocking: Plan gap: the unattended build must follow a process that needs a human.
   Raise: Plan gap  
   Case: normal use - Claude starts the requested app from the fresh starter.  
   The plan tells Claude to follow the generated [AGENTS.md](/src/forge/templates/adapters/AGENTS.md:12), which requires the Forge flow. [Init](/src/forge/init.py:234) creates a prototype; its [UI fixes require an approved plan](/src/forge/task.py:697), and [stories require sign-off](/src/forge/story.py:112). The benchmark provides no human approval or close step.  
   Gain 5, Work 3, Harm 2
   Disposition: cut - Settled 3 now tells the session there is no person: it builds in the working folder from the shipped guide, skills, rules and starter, runs no story, fix or close command, and does not commit (hooks fire only on commit); Risks says Forge's own flow is not measured.

2. Blocking: Plan gap: the required live run cannot run from main before the new workflow merges.
   Raise: Plan gap  
   Case: normal use - the builder tries to provide the required live proof for the pull request.  
   The [plan](/plans/FORGE-BENCH-1.md:77) requires a manual run from `main`, but the workflow is a [new file in the unmerged task](/plans/FORGE-BENCH-1.md:99). [GitHub requires the workflow to exist on the default branch](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch) before a manual run can start.  
   Gain 4, Work 2, Harm 2
   Disposition: cut - Done-when detail 1 no longer asks the builder for a live run before merge; the builder's proof is `test_1` plus the fixture runs of `test_2` and `test_3`, and the coordinator starts the first manual run from `main` after the merge (a failed run is a fix, not a merge blocker).

3. Blocking: Unproven: item 1: the scratch app can use a different Forge release.
   Raise: Test  
   Case: normal use - a tag starts the benchmark while main has a newer Forge release.  
   [Init](/src/forge/init.py:189) pins the version of the Forge installation that runs it. The [planned workflow test](/plans/FORGE-BENCH-1.md:75) does not establish that this installation comes from the triggering tag; the prescribed live run uses main. A workflow using main for every tag would pass those checks while scoring the wrong release.  
   Gain 4, Work 2, Harm 2
   Disposition: cut - Settled 4 checks out the triggering ref and installs Forge with `uvx --from git+...@<ref>`, the form `docs/guide.md` uses; `test_1` asserts that both use the same ref expression and that the script gets it as `--release`.

4. Blocking: Unproven: item 3: a manual run can be mistaken for the previous release.
   Raise: Not done  
   Case: normal use - someone runs the workflow by hand between two releases.  
   The [planned lookup](/plans/FORGE-BENCH-1.md:65) lists successful runs without specifying how to exclude manual runs or select the preceding release. The workflow test checks that a previous file is passed, so it can pass while the summary compares against an untagged build. Existing [release-proof lookup](/.github/reuse-test-proof.py:76) distinguishes event and ref.  
   Gain 4, Work 2, Harm 2
   Disposition: cut - Settled 6 looks up previous results with `--event push --status success`, so a manual run is labelled as manual and never becomes a previous result; `test_1` asserts the flags.

5. Blocking: Not done: a changed design checker does not start a new baseline.
   Raise: Not done  
   Case: normal use - a release changes a design rule while the benchmark files stay the same.  
   The [baseline](/plans/FORGE-BENCH-1.md:69) hashes the notes, checks file and browser specs, but not the [design checker and its rules](/src/forge/templates/design/ui-checks.js:31). A new checker rule can change the score for the same app while the summary still reports a direction.  
   Gain 4, Work 2, Harm 2
   Disposition: cut - Settled 8 builds the baseline id from the files in a `baseline` list that includes `ui-checks.js` and the bundled impeccable folder; `test_3` changes a listed file and expects "new baseline"; Done-when 3 now names the design checker.

6. Blocking: Unproven: item 2: the browser checks may run after the app has stopped.
   Raise: Plan gap  
   Case: normal use - scoring runs the starter’s own test command before the fixed browser checks.  
   [Init](/src/forge/init.py:229) sets that command to `node scripts/test.mjs`, which [removes its containers and data before returning](/src/forge/templates/starter/scripts/test.mjs:98). The [helper the plan proposes to reuse](/tests/test_starter_tree.py:386) also returns after cleanup. Neither task pins a running app for the subsequent checks, and the proposed score test uses simple commands.  
   Gain 4, Work 2, Harm 2
   Disposition: cut - Settled 2 adds an `[app]` entry (`start`, `ready`, `stop`) that runs the fixed checks after build, tests and design checks, between start and stop, since the starter's test command removes its stack when it ends (`scripts/test.mjs`); `test_2` uses a small web server to prove the order and the stop.

7. Blocking: Not done: the job check can pass when the job is never scheduled.
   Raise: Not done  
   Case: normal use - the generated app implements the late-order handler but never schedules it nightly.  
   The [planned check](/plans/FORGE-BENCH-1.md:63) calls the handler’s endpoint or command directly. That can produce the expected result even though no scheduled job runs; the [starter](/src/forge/templates/starter/README.md:3) supplies no job screen.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - the job check no longer claims a schedule: the notes make the client's own scheduler call a fixed address each night, the check makes that call and reads the orders list, and the owner text and Done-when say "one job"; Risks says the schedule is not proved.

8. Advisory: Unproven: item 2: the browser checks can report working controls without exercising them.
   Raise: Test  
   Case: normal use - the generated sign-in page displays its fields, but submitting credentials does nothing.  
   The [planned test](/plans/FORGE-BENCH-1.md:83) checks the notes and checks list, not whether the fixed specs detect broken behavior. A visibility-only spec like the [starter’s controls check](/src/forge/templates/starter/apps/web/e2e/rules/sign-in.spec.ts:23) could therefore pass while sign-in is broken.  
   Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

9. Blocking: Plan gap: the two tasks share an undefined usage-file format.
   Raise: Plan gap  
   Case: normal use - the workflow writes Claude’s usage for the score script to read.  
   The [shared interface](/plans/FORGE-BENCH-1.md:68) names a JSON file containing tokens, turns and minutes but pins no field names or types. SCORE can pass its test with one shape while RUN writes another from the [Claude result event](/src/forge/claude_turn.py:27), leaving the summary unable to read the usage.  
   Gain 4, Work 2, Harm 2
   Disposition: cut - Settled 7 pins the usage file keys (`input_tokens`, `output_tokens`, `turns`, `minutes`; null prints "not reported") and where each comes from; `test_3` uses exactly those keys and a missing-key case; the unverified `usage` field names are listed under Not verified.

## Round 2

10. Blocking: Unproven: item 1: the specified SDK setup can stop the build on a fresh runner.  
    Raise: Plan gap  
    Case: normal use - the benchmark starts with Claude access but no Codex installation or login.  
    The [plan](/plans/FORGE-BENCH-1.md:67) relies on the environment installed by `forge doctor --fix`. On a fresh runner, [init](/src/forge/init.py:182) keeps both tools enabled, and [doctor](/src/forge/doctor.py:349) reports the missing Codex login and exits with an error. If init detects only Claude instead, doctor installs the Claude SDK only when Codex is also installed. The workflow test does not exercise either setup.  
    Gain 5, Work 2, Harm 2
   Disposition: cut - Settled 3 names the Claude-only setup (Node 24, uv, Python 3.11, Forge from the triggering ref, the Claude SDK via `claude_sdk.install()` as `codex-smoke.yml` does for Codex), runs no `forge doctor`, and writes `tools = "claude"` and `workers = "claude"` after init; `test_1` asserts no doctor, no Codex step or key, and those lines.

11. Blocking: Not done: a release without a key can prevent later releases from being scored.  
    Raise: Not done  
    Case: normal use - a release is tagged before the key is added, then another is tagged after it is added.  
    The [previous-result lookup](/plans/FORGE-BENCH-1.md:70) selects successful tag runs. A notice-and-skip run like [codex-smoke](/.github/workflows/codex-smoke.yml:38) succeeds without producing a score artifact. The prescribed `gh run download` [fails when that run has no artifact](https://github.com/cli/cli/blob/trunk/pkg/cmd/run/download/download.go), and the plan gives no rule or test for continuing without a previous score.  
    Gain 5, Work 2, Harm 2
   Disposition: cut - Settled 6 picks the previous result as the newest successful tag run that has a `bench-result` artifact, so a skipped no-key run is passed over and a missing one never fails the job; `test_1` asserts the lookup and `test_3` has the missing or empty `--previous` case.

12. Advisory: Unproven: item 3: the reported tokens can omit part of the Claude build.  
    Raise: Test  
    Case: normal use - Claude reuses cached input or delegates work during the build.  
    The [plan](/plans/FORGE-BENCH-1.md:71) does not pin how the result event becomes total tokens. Claude reports cached input separately, and its result `usage` excludes subagent activity; [Anthropic’s SDK documentation](https://code.claude.com/docs/en/agent-sdk/cost-tracking) identifies `model_usage` as the whole-session breakdown. Forge already [adds cached input](/src/forge/repo.py:561) for its own records. The planned test supplies a finished usage file, so copying only the raw fields could pass it.  
    Gain 3, Work 2, Harm 2
   Disposition: cut - Settled 6 sets `GH_TOKEN` from `github.token` on the lookup step and the job has `actions: read`; `test_1` asserts both.

13. Advisory: The baseline also changes when design guidance changes without changing the checker.  
    Raise: Not done  
    Case: normal use - a release improves the design instructions Claude uses to build the app.  
    The [baseline](/plans/FORGE-BENCH-1.md:72) hashes the entire impeccable folder, including [guidance Claude reads before UI edits](/src/forge/templates/skills/impeccable/SKILL.md:21) and the [vendor notice](/src/forge/templates/skills/impeccable/FORGE-NOTICE.md:1). Changing those files suppresses the direction even when the checker is unchanged, hiding the effect of a shipped skill change.  
    Gain 3, Work 2, Harm 2
   Disposition: cut - Settled 6 sets `GH_TOKEN` from `github.token` on the lookup step and the job has `actions: read`; `test_1` asserts both.

14. Advisory: Unproven: item 2: an app that cannot start may produce no score.  
    Raise: Test  
    Case: normal use - Claude builds an app whose container or migration fails at startup.  
    The [new start-and-ready step](/plans/FORGE-BENCH-1.md:66) precedes all five app checks, but [the planned test](/plans/FORGE-BENCH-1.md:82) only starts a working server. It can pass while a startup failure aborts the scorer instead of recording those checks as “did not run.”  
    Gain 3, Work 3, Harm 4 (floor: migration)
   Disposition: cut - Settled 2 adds `ready_timeout` and makes a failed or silent start count the 5 app checks as failed with "the app did not start", still stopping the app and writing the score; `test_2` has a second run with a `start` that exits at once.

## Round 3

15. Advisory: Unproven: item 3: an unauthenticated lookup can be mistaken for no earlier score.  
    Raise: Test  
    Case: normal use - a release runs after an earlier score has been saved.  
    The [plan](/plans/FORGE-BENCH-1.md:70) specifies `actions: read` and allows a missing lookup to continue. GitHub CLI also needs a token in its environment; the existing [release workflow](/.github/workflows/forge-next.yml:58) supplies `GH_TOKEN`. The planned test does not check that authentication, so a workflow could pass it while reporting no earlier score on every run. [GitHub’s workflow documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli) describes the token requirement.  
    Gain 3, Work 2, Harm 2
   Disposition: cut - Settled 6 sets `GH_TOKEN` from `github.token` on the lookup step and the job has `actions: read`; `test_1` asserts both.

## Round 4

16. Advisory: Not done: an older release can be compared with a newer one.  
    Raise: Not done  
    Case: normal use - two releases are scored by hand in the opposite order.  
    The [lookup](/plans/FORGE-BENCH-1.md:71) selects the newest run with an artifact without checking which release it scored. Scoring `v1.2.37` and then `v1.2.36` would compare the older release against the newer one; the next run would use `v1.2.36` as its comparison. Forge’s existing [release ordering](/src/forge/releases.py:41) uses ancestry rather than run time.  
    Gain 3, Work 3, Harm 2
   Disposition: cut - Settled 6 compares only with a lower release number and ignores higher ones; `test_3` has a higher-release file present.

17. Advisory: Unproven: item 1: a tag from before this story has no benchmark files.  
    Raise: Test  
    Case: normal use - after the workflow merges, the first manual run names the latest release already tagged.  
    The [plan](/plans/FORGE-BENCH-1.md:69) says the job checks out the named tag and can score any tag. The [scorer and notes](/plans/FORGE-BENCH-1.md:102) are new; `git ls-tree v1.2.35 -- benchmark scripts/bench_score.py` finds neither in the current latest release. The plan does not specify another source for those files, and the workflow test would pass with only the tag checkout.  
    Gain 3, Work 3, Harm 2
   Disposition: cut - Settled 4 says an older tag is scored with the current notes, checks and script from the fix's worktree and the app built from that tag.

## Round 5

18. Blocking: Plan gap: the builder is given the Forge checkout’s worker instructions.
    
    Raise: Plan gap  
    Case: normal use - the coordinator starts the background worker from its Forge session and passes the scratch folder’s path.  
    The [plan](/plans/FORGE-BENCH-1.md:69) assumes that passing the path selects the scratch repo’s worker. [Claude Code’s documentation](https://code.claude.com/docs/en/sub-agents) says project workers are discovered from the session’s working directory, and a subagent starts there. The current [worker’s system instructions](/.claude/agents/worker.md:9) say to work in that checkout and commit, conflicting with the requested scratch-folder, no-commit build. This is a new conflict introduced by the native worker setup; the guide test checks only its wording.  
    Gain 5, Work 3, Harm 2
   Disposition: cut - Settled 4 and 5 now start a `general-purpose` subagent (not the `worker` role) whose prompt is only the scratch folder, the notes and the rule to read the scratch folder's AGENTS.md and skills by path, start no story or fix and not commit; the evidence explains why the `worker` role comes from this repo (`worker.md` line 9); `test_1` asserts the subagent type and the prompt parts.

19. Advisory: Unproven: the saved score is left outside the fix checkout.
    
    Raise: Test  
    Case: normal use - the agent scores a release, then starts the fix that will save its result.  
    The [steps](/plans/FORGE-BENCH-1.md:69) write the result before starting the fix. [Fix start](/src/forge/task.py:264) creates a separate checkout from a commit and does not carry the uncommitted result into it. The guide test does not require a transfer, so following the listed steps can leave the fix without the score it must commit.  
    Gain 3, Work 2, Harm 2
   Disposition: cut - Settled 4 starts the fix first and writes the score into the fix's worktree; `test_1` asserts that order.

20. Advisory: Not done: the baseline can hash a different checker from the one being scored.
    
    Raise: Not done  
    Case: normal use - two release tags are scored from the same newer Forge checkout after the design checker changed between them.  
    The [baseline](/plans/FORGE-BENCH-1.md:73) hashes the checker in the coordinator’s checkout, while each scratch app receives the [checker shipped by its installed release](/src/forge/ui_checks.py:33). Both scores can therefore get the same baseline despite using different checkers, and the comparison can show a direction instead of “new baseline.” This arises from the new local design, where the scorer stays in the current checkout while the app is initialized from a named tag.  
    Gain 4, Work 2, Harm 2
   Disposition: cut - Settled 8 hashes the checker from the built app (`app_baseline`: its `ui-checks.js` and the impeccable `scripts/` folder), so the baseline follows the checker that was scored; `test_3` edits a file in each list.

21. Advisory: Not done: saving the score through a normal fix creates GitHub work.
    
    Raise: Not done  
    Case: normal use - the agent saves a release’s score as instructed.  
    The [owner-facing text](/plans/FORGE-BENCH-1.md:7) says nothing runs on or is added to GitHub, but the required normal fix [pushes its branch](/src/forge/task.py:288) and [opens a pull request](/src/forge/close.py:981). That pull request starts the existing [GitHub workflow](/.github/workflows/forge.yml:4).  
    Gain 3, Work 2, Harm 2
   Disposition: cut - the owner text now says only the saved-score file goes through Forge's usual pull request; Settled 4 names the mechanical kind (one pull request, one light review, related tests).
