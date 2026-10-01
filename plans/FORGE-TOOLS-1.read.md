---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-01T01:35:23+00:00
read_hash: 4259d98b3c0d41bc0ffc18fc717daf71610486cc
round: 3
passed: yes
doc_seen: 4259d98b3c0d41bc0ffc18fc717daf71610486cc
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 39a918c6ffb5cd508ad56a26534f685e501cff50
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
