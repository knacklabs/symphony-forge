---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-02T23:10:01+00:00
read_hash: ecf423364a5c968c4a07a41b4e39d56674de3b0c
round: 1
passed: no
doc_seen: ecf423364a5c968c4a07a41b4e39d56674de3b0c
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Item 4 assumes an approval path that does not exist today.
   In `approval.py`, Claude approvals come only from ExitPlanMode; AskUserQuestion only counts a human touch. APPROVE must pin the new question/answer contract, digest binding and native hook provenance while preserving the existing refusal checks. Calling the recorder with a constructed payload cannot prove human approval.
   Disposition: keep Approve now opens Claude Code's own plan-approval prompt (ExitPlanMode) so the existing hook and its checks record it; APPROVE proves this first (owner chose)

2. Item 4 contradicts the promised Approve-button behavior.
   “What changes for you” says pressing Approve approves the story; builder details say it starts another approval question. State the actual interaction consistently before the human approves this story.
   Disposition: cut wording now matches: the button opens Claude's own plan prompt and you approve there

3. VIEWS must explicitly pin the contracts its consumers share.
   The flag names, JSON fields/types, item and repository identities, run/review/check identities, unavailable-data representation, per-item next steps and approval document location/digest are unspecified. VIEWS must own these contracts and a test crossing producer and consumer; its Covers cell also needs the event data it supplies for item 3.
   Disposition: cut details 1-3 pin flags, fields, identities, unknown values and next.command; VIEWS covers 1-3

4. Items 1 and 3 lack an owner for missing run and question observations.
   Claude workers do not record their pending questions as Codex workers do, and close has no complete run-start/run-end record. Neither `worker.py` nor `close.py` is in Scope. Pin how VIEWS obtains reliable worker elapsed time, Claude questions and every close outcome, and assign any necessary recording changes.
   Disposition: cut VIEWS adds run start/end records in worker.py, close.py and codex.py; questions come from the item state both workers already write

5. Items 2 and 3 do not define which next step becomes the command.
   `nextstep._report` returns multiple steps, including platform alternatives, placeholders, human merge instructions and waits. Pin deterministic selection, per-item association and which states disable the hotkey; otherwise builders must invent what “next command” means.
   Disposition: cut next.command is the first runnable forge command with no placeholder or alternative, else null

6. P1: MOD changes coordinator behavior without its required instruction update.
   MOD introduces event-driven turns but scopes neither `src/forge/templates/skill.md` nor the worker brief. The repository’s Review rules require that update in the same change, including how the coordinator handles events and watches runs when the mod is unavailable.
   Disposition: cut EVENTS owns the guide's events section and the brief's line; each task owns its own guide section

7. Shared Scope entries leave ownership and wiring unspecified.
   APPROVE’s files are already inside MOD’s `src/forge/mod/**`; VIEWS, APPROVE and SHIP all own `templates/skill.md`. MOD must reserve approval files and pin its registration interface. Assign shared guide lines to one owner or a small final wiring task, rather than making unrelated work wait on guide edits.
   Disposition: keep each task adds its own named guide section; mod files are split per task with register.ts owned by PANE

8. Split: MOD → pane/band and event delivery.
   Pane rendering, keyboard controls, refresh/process handling, event comparison, busy-turn batching and packaging suggest more than about 400 changed lines. Keep drawing and next-step controls in one task; give event delivery its own files and tests.
   Disposition: cut split into PANE and EVENTS

9. Unproven: item 1: automatic pane visibility in a narrow terminal.
   Claude Code can leave an automatically opened pane hidden below its width threshold; it does not always place it above the prompt. Pin a supported user-open action or narrow-screen fallback and test that path. [Pane opening rules](https://code.claude.com/docs/en/plugins/mods/interface#when-a-pane-waits-for-a-wider-terminal).
   Disposition: cut /forge opens at any width; unasked open only shows at 144+ columns and the band points to /forge otherwise; tested at 80 columns

10. Unproven: item 1: refresh behavior and incomplete state.
    Fixture row checks do not prove timer refresh, refresh after commands, advancing elapsed time or recovery from a slow/failed/malformed response. Add cases for an empty board, missing state and unavailable checks; `board._prs` currently fetches check details for only the newest 25 pull requests.
   Disposition: cut refresh timer, after-forge-command refresh, single-flight, failure/slow/malformed handling, empty board and 25-PR limit pinned with tests

11. Unproven: item 2: the hotkey’s refusal states.
    The named test proves a successful submission only. It does not prove that typing into a nonempty prompt remains ordinary input, that nothing-ready disables the hotkey, or what happens while busy, after a stale command, or when submission fails. Name these cases in MOD’s Tests cell.
   Disposition: cut hotkey states pinned: empty prompt only, null, stale and busy cases tested

12. Unproven: item 3: event identity, lifecycle and queued delivery.
    Two snapshots do not prove repeated runs ending in the same stage, runs entirely between refreshes, initial load/reload behavior, overlapping refreshes or failed submissions. Pin event identities and consumption rules, reconcile “one turn per change” with busy-turn batching, and test batching, two sessions on one repo and isolation between repos.
   Disposition: cut event identities, seen store, initial load, batching and failed submit pinned with tests

13. Unproven: items 3 and 5: which sessions receive automatic turns.
    Mods also run in `claude -p` and VS Code chat sessions, even where nothing draws. Forge starts headless Claude workers itself, so installing the plugin can make workers receive coordinator events unless eligibility is defined. Pin interactive/coordinator gating and prove fallback behavior. [Where mods run](https://code.claude.com/docs/en/plugins/mods/overview#where-mods-run).
   Disposition: cut only interactive sessions; FORGE_WORKER=1 set for every Forge-started process makes the mod inert; tested

14. Unproven: item 4: approval refuses safely and Request changes delivers its note.
    Display and successful-recording tests do not cover a document changing after display, the wrong worktree, missing/malformed documents, unrelated questions, cancellation, replay or synthetic completion. Add coverage through the new native path, including Request changes delivering the exact note without recording approval.
   Disposition: cut trust checks stay in forge hook approval; tests cover changed doc, CRLF, and Request changes recording nothing

15. Item 5 does not resolve marketplace identity across repository versions.
    Claude Code identifies marketplaces by name and cannot register two with the same name simultaneously. Pin marketplace/plugin names, source paths and version handling for two repos on different Forge tags and for an existing cached install; changing settings alone is insufficient proof. [Marketplace version rules](https://code.claude.com/docs/en/plugins/host-marketplace#run-release-channels).
   Disposition: cut owner chose one mod from the latest release for every repo; the mod runs each repo's pinned Forge and shows a too-old line

16. Unproven: item 5: installation, reload, settings preservation and fallback.
    Settings-output tests and plugin validation do not prove the plugin loads from the shipped source. Define when an existing session activates it, and test repeated sync, existing unrelated entries, malformed settings, unavailable downloads and absent/old/disabled Claude Code. Prove the doctor warning leaves its exit status successful and Codex/no-mod behavior intact.
   Disposition: cut sync output, repeated sync, unrelated entries, malformed settings, reload and doctor exit status pinned with tests

17. Trap: Windows line endings and shells: items 1, 2, 4 and 5.
    No named cases cover CRLF approval text, Unicode/spaced/backslash paths, PowerShell/cmd command quoting or WSL launch behavior. Pin process invocation and working-directory handling, and assign the relevant platform cases to the owning Tests cells.
   Disposition: cut argv without a shell through the repo launcher, repo-root cwd, CRLF normalised; tested

18. Trap: installed-version mismatch and unavailable test tooling: items 1–5.
    Read-only `forge next` and `forge board` bypass the CLI’s pin check, so a pinned plugin can reach an installed Forge lacking its JSON flags. Pin executable/version resolution and test mismatch recovery. CI currently provisions only Python/uv; assign ownership for a pinned Claude test binary and executable plugin test/validation runs without network-dependent test execution. [Mod test runner](https://code.claude.com/docs/en/plugins/mods/test).
   Disposition: cut version check through the launcher with the too-old line; CI installs a pinned Claude Code for plugin tests
