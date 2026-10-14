---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-14T05:26:10.478333+00:00
seconds: 27.76
read_hash: 635e33e81bfd2f2643c55c7dc999129d523a3019
round: 3
passed: yes
doc_seen: 635e33e81bfd2f2643c55c7dc999129d523a3019
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: f71b890272ee2de83a21c0eacd0f7de9f1828f92
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
