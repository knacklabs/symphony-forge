---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T11:21:36+00:00
read_hash: 4e3b7f2b1528944dca8168f4ab6126151e7d6bd7
amended_hash: 377265337d6b2c1477b2bb4424cab1fab31fe994
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The automatic merge rule lacks a confirmed spec and reverses an existing permission rule.
   The confirmed `agent-merge` spec says only the default branch’s `merge = "agent"` grants merge authority. The confirmed prototype spec covers pre-sign-off fixes, but does not grant an exception. Pin the intended authority before approving an override of `merge = "human"`.
   Disposition: cut SPEC now records the owner's decision that the agent merges prototype changes until sign-off.

2. `forge next` would still tell the salesperson to merge a ready pull request.
   MERGE changes close and merge, while the current `nextstep.py` reads the raw merge setting in both its ready and cleanup paths. TALK owns that file, so it must use MERGE’s `repo.merge_setting(top)` and list MERGE under After.
   Disposition: cut TALK makes nextstep's ready and cleanup paths use merge_setting and waits on MERGE.

3. The setup order cannot run as written from an empty client repo.
   The script exists in Forge’s `scripts/`, not in the new repo, so SPEC and INSTALL need to pin how the salesperson obtains and runs it. `forge doctor --fix` and the final `forge doctor` require an initialized repo with `forge.toml`, but the checklist places the install script before `forge init`. Pin the order and where `--check` runs.
   Disposition: cut the script is fetched from Forge's repo with one line, ends by printing the next step, and the Codex SDK installs at forge init.

4. The sign-off boundary is ambiguous for an in-progress sign-off fix.
   `approval.signed_off(top)` accepts a decision in the current checkout as well as one on the default branch. `forge merge` can be invoked from another checkout. Specify which checkout and branch determine the effective setting so the sign-off fix and subsequent fixes use the intended merge rule.
   Disposition: cut merge_setting reads sign-off from the default branch as last fetched only.

5. The demo address has no complete handoff contract.
   TALK introduces `- Demo address: <url>` in `BRIEF.md`, while the prototype sign-off plan puts the address in the decision’s `demo` front matter. No SALES task owns copying it, and the story does not pin which branch’s brief `forge next` reads. Pin the line’s location, the read source, and whether copying is an agent instruction or code; give the task that uses the format an After dependency on its owner.
   Disposition: cut the address lives in BRIEF.md's own Demo section on the default branch, and the skill has the agent copy it into the sign-off.

6. The promised “empty repo to live demo” checklist has unresolved steps.
   Its listed steps omit building and merging the prototype. “Connect our deploy platform” also gives no named entry point or account access path a salesperson can follow. The script installs the Codex SDK, but the checklist does not say how the salesperson gets and signs in to Claude Code or Codex.
   Disposition: cut the checklist now includes signing in, building and merging the demo, and the platform step with a placeholder the owner chose.

7. INSTALL’s stated test proves only `--check` command detection.
   Stub commands on `PATH` cannot establish that the install path installs the named release, browsers and Docker successfully, skips usable existing installs, or reaches a working final `forge doctor`. Add focused proof for those observable script outcomes.
   Disposition: cut the test now also runs a full stubbed install; a real clean-Mac run is recorded in the functional check.
