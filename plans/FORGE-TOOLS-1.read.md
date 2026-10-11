---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-10T11:27:18.445020+00:00
read_hash: 70c673ecc3c8ea95523e3bd159d7bf905613abf3
round: 6
passed: yes
doc_seen: 70c673ecc3c8ea95523e3bd159d7bf905613abf3
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: f86577e5686f395c155c993287797333c48e0339
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. P1: RUN introduces the setting and command behavior without the required coordinator or worker template update.
   `AGENTS.md:53–55` requires that update in the same change. GUIDE lands afterward, so it cannot satisfy RUN’s review. Assign the setting and command instructions to RUN, and the default-model instructions to DEFAULTS, with explicit ownership of their template edits.

Disposition: cut

2. Item 2 does not pin which model Claude uses for repair rounds.
   In `worker.py:72–74`, ordinary Claude work never sets `later`, so subsequent rounds continue using `build` or `lite`; the Claude `fix` entry remains unused. Decide the single-tool behavior and prove it in `tests/test_tools_setting.py` using different build, fix and lite models.

Disposition: cut

3. Item 2’s missing-model guarantee contradicts its review and design paths.
   The general rule promises the tool’s own default, but Claude reviews fall back to `grill`, and `repo.design_models` supplies Forge’s pinned defaults. Doctor would incorrectly describe those missing entries as work using the tool’s own default. Pin the exceptions or remove the fallbacks, and test the resulting runtime behavior and notes.

Disposition: cut

4. Unproven: item 3: missing tools refuse before any state commit.
   `worker.py:117` commits status before `_run` checks for Claude at line 427; design work also skips initial readiness checks. The four proposed refusal tests assert messages and no other-tool launch, but not unchanged HEAD and state. Move installation checks before the commit and cover ordinary Claude workers and directly selected Codex design workers in `tests/test_tools_setting.py`.

Disposition: cut

5. Item 2’s Claude question command does not deliver “keeps no session.”
   `claude -p` needs `--no-session-persistence` to disable saved, resumable sessions. Add that flag and its boundary check to `tests/test_tools_setting.py`. [Claude CLI reference](https://code.claude.com/docs/en/cli-reference)

Disposition: cut

6. Unproven: item 2: fixed-tool cold reads when the other app coordinates.
   The proposed tests only pair Claude settings with Claude coordination and Codex settings with Codex coordination. An implementation that always chooses the coordinator could pass both. Cover both opposite-app combinations in `tests/test_tools_setting.py`, asserting the named reader and its grill model.

Disposition: cut

7. Unproven: item 2: Claude questions with failed or empty answers, effort-only overrides, and no Claude lite entry.
   Existing question failure tests exercise Codex. Pin Claude’s refusal text and discarded output, and prove that absent entries omit model flags and `--effort` independently overrides configuration, in `tests/test_tools_setting.py`.

Disposition: cut

8. Unproven: item 6: doctor checks the executable reviews actually use.
   Reviews accept `CODEX_BIN`, while doctor’s proposed row checks literal `codex` on PATH. A valid override could be reported missing; a broken override could escape the program check. Use the review’s executable lookup and cover both cases in `tests/test_tools_doctor.py`.

Disposition: cut

9. DEFAULTS lacks scope for regenerating the committed agent files its role change affects.
   The prerequisite’s `tests/test_subagent_roles.py` requires Forge’s own `.claude/agents/` and `.codex/agents/` files to match sync output. Switching to `repo.models` also changes missing-family effort output. Include those generated paths and the affected existing role/default assertions in DEFAULTS’s Scope and Tests.

Disposition: cut

10. Unproven: item 2: the new Claude question path through Windows command shims and shell quoting.
    No proposed case covers `.cmd` launchers, paths containing spaces, multiline Unicode input or CRLF output, and current CI runs on Ubuntu. Add focused platform proof to RUN’s tests and name its execution route, or explicitly exclude unsupported platforms with a reason.

Disposition: keep the Claude question uses the same repo.run route with the prompt on stdin as the Claude cold read (src/forge/story.py:613-624), which already runs on every platform Forge supports; it adds no new launcher, quoting or encoding path to prove

## Round 2

11. Split: RUN → settings and worker routing; command routing and coordinator guide.
    RUN now covers four Done-when items (`1, 2, 3, 5`), exceeding the three-item limit. Pin the shared setting, helper and refusal in the first task; give each task its required template update and owned tests.

Disposition: cut

12. Finding 9 remains partly open: DEFAULTS still excludes an existing default-model assertion it must update.
    `tests/test_codex_reader.py:170` compares the entire initialized models table with today’s single-entry shape; that assertion also remains in the prerequisite branch. Item 4 necessarily changes it. Add this file to DEFAULTS’s Scope and Tests, and narrow item 1’s promise that existing cold-read tests pass unchanged.

Disposition: cut

## Round 3

No findings.

## Round 4

13. Native workers are not told which worktree to build in.
    Raise: Functional. Item 3 prints only “Read <brief path> and follow it.” Today `worker._run` starts with `cwd=top`; `_brief` supplies no checkout path, and its template says to use “the checkout you were started in.” A subagent spawned from the coordinator’s main checkout therefore receives instructions to work there instead of the task or fix worktree.

Disposition: cut

14. Native workers lose the existing settings-commit guard.
    Raise: Not done. Notes explicitly omit `FORGE_WORKER=1`. `githooks.pre_commit` uses that marker to refuse unauthorized `forge.toml` commits, while `_restore_settings` restores only uncommitted changes from HEAD. A native worker that commits a settings edit bypasses the guard, and handback preserves it. Item 3’s proposed test covers only an uncommitted edit.

Disposition: cut

15. A stopped round’s handback cannot be distinguished from its replacement round.
    Raise: Plan gap. Items 3–4 record the pending round before spawning, learn the agent id at handback, and accept only `<item> --agent <id>`. After stopping and restarting an item in the same session, the old agent’s first handback supplies no identifier tying it to the stopped round. The promised stopped refusal has no pinned validation rule or test for this case.

Disposition: cut

16. Unproven: item 4: starting a new conversation without ending the app process.
    Raise: Test. The continuation rule relies on the coordinating process’s identity; the test changes sessions by ending that process. Claude’s `/clear` starts a new conversation in the same process. Such a conversation would still match the recorded process and receive the old subagent’s short brief, although the story promises a fresh whole brief in a new session. [Claude command reference](https://code.claude.com/docs/en/commands)

Disposition: cut

17. Native Codex rounds retain a prerequisite belonging to the kit route.
    Raise: Plan gap. Items 3 and 5 retain today’s readiness checks. `worker.ready` unconditionally probes the Codex SDK for Codex work and reads, while item 8 describes SDK installation as a kit requirement. A developer coordinating in Codex without Forge’s separate SDK would be refused before a native handout; the proposed native tests do not exercise that setup.

Disposition: cut

18. Native role selection drops Codex’s repair-round model.
    Raise: Not done. Item 3 assigns every task round to `worker` on the build entry and every fix round to `fixer` on lite. Today `worker.work` selects the fix entry for later Codex rounds. With distinct build, lite and fix models, the printed selection and the generated role diverge; no native repair-round test proves the promised per-kind routing.

Disposition: cut

19. Item 3 puts the status commit before the busy lock.
    Raise: Functional. Its stated sequence commits status and then takes the item lock and lane place. Today `worker.work` takes both before incrementing and committing the round. Re-running `forge work` while a native round is outstanding could therefore change HEAD and round state before refusing as busy.

Disposition: cut

20. SETTING cannot deliver its no-fallback rule within its Scope.
    Raise: Plan gap. Item 1 promises that a named tool never falls back, but SETTING excludes `worker.py`. Its existing design-failure branch checks only `config["workers"] == "split"` before launching Codex. With `tools = "claude"` and `workers = "split"`, changing `repo.worker()` alone leaves that fallback active. The proposed test uses `workers = "claude"` and misses it.

Disposition: cut

21. Trap: Windows Node launches: item 4’s session lookup cannot obtain the script name from the named API.
    Raise: Plan gap. The rule matches a Node launch by its script’s basename, but Windows `codex.identity` returns only the executable image path, such as `node.exe`, with no script arguments. Doctor’s Claude installation command uses npm. The proposed shim named `claude` or `codex` bypasses this supported installation path.

Disposition: cut

22. Split: NATIVE → session lifecycle; native reads and command replacement.
    Raise: Plan gap. Its Scope includes a new lifecycle module, persistent locks and admissions, stop and continuation behavior, read handout and completion, command replacement, role generation, and four test files plus existing-test changes. That combined production and test change suggests substantially more than the review’s roughly 400-line task limit.

Disposition: cut

23. Split: SDK → SDK runtime and boundary; worker and reader migration.
    Raise: Plan gap. This task combines an installer and probe, a streaming resumable driver, worker and reader replacements, stop behavior, a new SDK fixture, and migration of every existing Claude worker/read test. Its Scope suggests substantially more than roughly 400 changed lines, with no partition named.

Disposition: cut

24. Unproven: item 3: `forge land` stops at a native handout and resumes after handback.
    Raise: Test. WORK promises this behavior, but its proposed test calls only work, next and handback. Existing land tests moved to Claude coordination continue exercising Codex’s kit route. They would pass if native land proceeded directly to close while its subagent was still outstanding.

Disposition: cut

## Round 5

25. Doctor omits the SDK needed for a supported run outside a coordinating session.
    Raise: Functional. The route table sends `tools = "both"` work through the kit when no app coordinates. With only Codex installed and Codex workers, that requires the Codex SDK, but item 8 checks that SDK only when Claude is installed. Doctor therefore neither reports nor installs the missing prerequisite. The symmetric Claude-only setup has the same gap.

Disposition: cut

26. Committed settings recovery can be blocked by the settings it must restore.
    Raise: Plan gap. Item 3 promises to restore unauthorized committed `forge.toml` changes at handback. When the coordinator hands back from the item's checkout after a worker changes its version pin, `cli._run` calls `repo.check_pin` before the handler. That forwards handback to the pinned release, which may lack the command. No rule or test ensures restoration remains reachable after a pin change.

Disposition: cut

27. Unproven: item 8: a missing review engine before close merges the default branch.
    Raise: Test. `close.close` calls `_merge_default` before `review.run`. With a named tool missing and new default-branch commits available, checking availability inside `review.run` changes HEAD before refusing, contrary to item 8. CHECKS specifies no earlier close preflight and excludes `close.py`; its test does not name an advanced default branch, so it can pass while this guarantee is broken.
    This read checked the plan and repository code; runtime behavior was not exercised.

Disposition: cut

## Round 6

No findings.
