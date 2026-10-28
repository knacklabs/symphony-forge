---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-28T18:05:48.652673+00:00
seconds: 317.724
read_hash: c5f0eb6db2c45c76f5a189be085007365a276789
round: 1
passed: no
doc_seen: c5f0eb6db2c45c76f5a189be085007365a276789
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: a4148686985e56e551781f8e6aa1332e72e46d85
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1839f-f05c-79d1-87b0-8aa799b93083
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

1. Blocking: Not done: native rounds cannot deliver the promised effort changes and Claude helper settings.
   Raise: Not done.
   Case: normal use - a developer runs Forge from the same tool selected as its worker.
   `src/forge/repo.py:824` selects the native route in this case. `src/forge/worker.py:279` hands it out and returns before the SDK path that SUBS changes. `src/forge/native.py:144` records requested effort before execution; it does not verify applied effort. The plan’s native limitation at `plans/FORGE-EFFORT-1.md:39` therefore contradicts items 1 and 4, while SUBS supplies no native mechanism for item 6.
   - Open question: Must automatic effort changes and Claude helper budgets work in native rounds, or should those guarantees explicitly cover SDK rounds only?
     Touches: Worker effort, helper settings and recorded effort.
     Why we ask: The current native mechanism cannot enforce these guarantees.
     Default: Limit automatic guarantees to SDK rounds and label native effort as requested.
     Why this default: It preserves the plan’s decision to continue the native subagent.
     If the default stands: The approval text and tests distinguish requested native settings from applied SDK settings.
     Due: 4 November 2026.
   Gain 5, Work 2, Harm 3
   Disposition: cut - Claude rounds run through the SDK when installed; native effort is labelled requested (owner decision, 28 Oct 2026)

2. Blocking: Not done: changing the cold-read entry does not select Sonnet-high for reviews.
   Raise: Not done.
   Case: normal use - closing a change in a newly initialized Claude-only repo.
   DEFAULTS changes only `grill.claude` at `plans/FORGE-EFFORT-1.md:84`. Reviews independently read `models.review` in `src/forge/review.py:920`; `src/forge/repo.py:747` provides no grill fallback for reviews. Neither the implementation instructions nor the new-repo test selects or verifies the review model required by item 2.
   Gain 4, Work 2, Harm 3
   Disposition: cut - new repos write models.review.claude and models.grill.claude at Sonnet high, with a test on the Autoreview request

3. Blocking: Plan gap: LADDER and DEFAULTS are not independent as their task instructions claim.
   Raise: Plan gap.
   Case: normal use - either task builds and closes before the other.
   DEFAULTS must change `WORKER_DEFAULTS`, located at `src/forge/repo.py:590`, but its Scope excludes that file and LADDER’s delivery does not assign it this edit. Conversely, LADDER’s test requires freshly initialized low defaults, while `src/forge/init.py:77` still writes medium and DEFAULTS owns that change. Pin the fallback edit’s owner and resolve the test dependency before declaring these tasks independently buildable.
   Gain 4, Work 2, Harm 2
   Disposition: cut - DEFAULTS goes first, owns the WORKER_DEFAULTS edit, and LADDER waits for it

4. Blocking: Not done: the promised fallback for one missing Claude helper key is explicitly refused.
   Raise: Not done.
   Case: normal use - a developer sets the helper model and leaves its effort at the documented default.
   Item 6 promises a default when either key is missing, but `plans/FORGE-EFFORT-1.md:70` also preserves refusal of a single-key entry. `src/forge/repo.py:863` implements that refusal before a budget can be selected. The planned tests cover both keys present or both absent, so they miss this contradiction.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the pair rule stays as today (simpler, no code); the plan now says a kind with neither key uses the default

5. Blocking: Unproven: item 6 leaves ordinary general-purpose delegation outside the helper budget.
   Raise: Test.
   Case: normal use - an SDK builder delegates without naming one of the three overridden roles.
   `plans/FORGE-EFFORT-1.md:70` overrides only `explorer`, `tester` and `refactorer`. The SDK also keeps its built-in `general-purpose` agent available when custom agents are supplied. That invocation receives none of these overrides, while the planned test can pass by inspecting only the three supplied definitions. The plan needs a budget rule and proof for this ordinary delegation path. [Claude SDK documentation](https://code.claude.com/docs/en/agent-sdk/subagents#filesystem-based-definition-alternative).
   Gain 3, Work 2, Harm 3
   Disposition: cut - general-purpose gets the same Haiku budget and the test checks it

6. Advisory: Unproven: item 5 assumes an effort validation rule that does not exist.
   Raise: Test.
   `plans/FORGE-EFFORT-1.md:92` says configured `none` is refused or ignored. `src/forge/repo.py:855` validates effort’s type, not its value, and `src/forge/codex.py:188` forwards it. Treating unknown values as already above the ladder also preserves `none`. Tests using only the non-none settings from scenarios 1–3 cannot prove the stated guarantee.
   Gain 2, Work 2, Harm 2
   Disposition: keep - below the bar (live with)

7. Advisory: Functional: an optional failed check also triggers the proposed effort increase.
   Raise: Functional.
   The plan defines verified check failures as required checks, but `src/forge/worker.py:502` fetches all checks and line 507 accepts every failed bucket. Using `_fix_round` unchanged therefore raises effort when an optional check fails and required checks pass. The proposed required-check test would still pass.
   Gain 3, Work 2, Harm 2
   Disposition: cut - only failed checks named in forge.toml checks raise effort
