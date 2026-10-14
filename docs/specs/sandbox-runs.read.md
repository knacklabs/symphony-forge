---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-14T06:28:51.420042+00:00
seconds: 44.564
read_hash: bb7d5d6a423c414fa16484b2ef66c017d87c6c20
round: 7
passed: yes
doc_seen: bb7d5d6a423c414fa16484b2ef66c017d87c6c20
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 88227df2491e4b5230abf2a58d49acfed8c99195
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a138d9-664f-7b40-bb0e-9a66ddfe7a00
session:
blocked_rounds: 0
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
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Provider-key setup does not define a safe secret-storage boundary.
   Raise: Security. [The spec](/docs/specs/sandbox-runs.md:59) puts provider account/key setup in a `forge.toml` fix without distinguishing a secret reference from the credential itself. `forge.toml` is tracked, and the sandbox receives the branch. A literal implementation therefore commits and distributes the provider key. The spec needs to forbid storing credentials in committed settings.
   Gain 5, Work 2, Harm 4
   Disposition: cut

2. Blocking: Remote admission is undefined when both the laptop and sandbox cap are full.
   Raise: Plan gap. [Behaviour item 4](/docs/specs/sandbox-runs.md:56) requires overflow instead of waiting and introduces a remote cap; acceptance criterion 2 repeats the unconditional remote start. Parallel starts exceeding both caps are the feature's normal workload, but the spec chooses neither waiting nor refusal in that state. Existing admission explicitly queues excess runs in [machine.py](/src/forge/machine.py:174).
   Gain 4, Work 2, Harm 3
   Disposition: cut

3. Blocking: The remote handback does not define how pending worker questions reach local close.
   Raise: Plan gap. [The transport contract](/docs/specs/sandbox-runs.md:63) specifies streamed output and a commit bundle, but no terminal-result handback. Workers normally record trailing questions in [worker.py](/src/forge/worker.py:332); that record lives outside committed files in [codex.py](/src/forge/codex.py:797). Local [close.py](/src/forge/close.py:141) checks it before proceeding. A remote worker asking a security or scope question can therefore return commits without establishing the required local pause.
   Gain 4, Work 2, Harm 3
   Disposition: cut

## Round 2

4. Blocking: Acceptance criterion 7 would disable an opted-in repo on its next sync or upgrade.
   Raise: Plan gap. [Criterion 7](/docs/specs/sandbox-runs.md:104) says existing repos get sandbox runs turned off on upgrade and sync, without limiting this to repos that have never opted in. This conflicts with the persistent setting described at lines 64–66. Current configuration preserves explicit settings over defaults in [repo.py](/src/forge/repo.py:556), and upgrades preserve settings in [upgrade.py](/src/forge/upgrade.py:136). The criterion must distinguish default-off adoption from preserving an existing opt-in.
   Gain 4, Work 1, Harm 3
   Disposition: cut

## Round 3

No findings.

## Round 4

5. Blocking: Uploading the whole ignored working folder contradicts the credential exclusions.
   Raise: Security. [Lines 73–79](/docs/specs/sandbox-runs.md:73) require copying `.env` and its real keys while keeping provider and GitHub credentials off the sandbox. A developer can normally keep either credential alongside test settings in `.env`; [`.gitignore`](/.gitignore:2) permits that file locally. Approving its filename does not resolve which contents must be excluded or when transfer must refuse.
   Gain 5, Work 2, Harm 4
   Disposition: cut

6. Blocking: Automatic local fallback can start a second worker while the disconnected remote worker still runs.
   Raise: Plan gap. [Lines 112–117](/docs/specs/sandbox-runs.md:112) require local retry when the provider is unreachable and separately allow remote execution to survive a disconnected laptop. Losing connectivity therefore does not establish that the remote round stopped. The spec supplies neither confirmed termination before retry nor a rule rejecting its later result. Current [worker.py](/src/forge/worker.py:145) explicitly permits only one round per item.
   Gain 4, Work 2, Harm 3
   Disposition: cut

7. Blocking: Turning sandbox runs off can delete the only copy of outstanding worker commits.
   Raise: Data loss. [Lines 115–119](/docs/specs/sandbox-runs.md:115) retain uncollected results at the provider but require deleting all repo sandboxes and disks when disabled. Disabling while a round is running or awaiting collection is normal use. No rule requires collecting completed commits before deletion or settling what happens to active rounds. Unlike this deletion, local [stop](/src/forge/machine.py:388) terminates processes without erasing their working folders.
   Gain 5, Work 2, Harm 4
   Disposition: cut

8. Advisory: Simpler: Claude Agent SDK → the existing headless Claude Code command.
   Raise: Plan gap. [Lines 82–83](/docs/specs/sandbox-runs.md:82) describe the Claude Agent SDK as the driver Forge already uses locally. Current [worker.py](/src/forge/worker.py:628) invokes `claude -p` with streamed JSON. The SDK introduces a separate integration where the existing command already provides the stated worker and output behaviour.
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

## Round 5

9. Blocking: Acceptance criterion 3 forbids the Git metadata needed for remote commits.
   Raise: Plan gap. [Criterion 3](/docs/specs/sandbox-runs.md:139) says the sandbox never holds a `.git` folder, while behaviour item 1 requires the remote worker to commit and return a bundle. The reused [Codex driver](/src/forge/codex.py:546) also requires a working Git repository. Excluding the laptop’s `.git` from uploads is compatible with this; forbidding a fresh remote `.git` is not. The criterion must distinguish those two.
   Gain 4, Work 1, Harm 3
   Disposition: cut

## Round 6

10. Blocking: The branch-only bundle leaves the remote worker unable to run `forge test`.
    Raise: Plan gap. [The new bootstrap rule](/docs/specs/sandbox-runs.md:75) supplies only the item’s branch history, with no remote. [fasttest.py](/src/forge/fasttest.py:262) requires `origin/<default branch>` and otherwise refuses with “Fetch … first: run git fetch origin, then forge test.” This affects the required worker tests, including Forge’s own first rollout. The bootstrap contract must also supply the pinned default-branch reference and its history locally, without adding credentials or a remote connection.
    Gain 4, Work 2, Harm 3
    Disposition: cut

## Round 7

No findings.
