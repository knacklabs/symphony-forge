---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-20T07:52:42.069603+00:00
seconds: 489.212
read_hash: ff43d7b773ab927254d78e1a48ef914fe83d08be
round: 1
passed: no
doc_seen: ff43d7b773ab927254d78e1a48ef914fe83d08be
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a15844-e787-7e63-867e-480b27e36e5b
session:
blocked_rounds: 1
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

1. Blocking: The plan lane cannot start on a freshly initialized repo.
   Raise: Functional — [plan:138](plans/FORGE-INTAKE-1.md#L138) requires calling `story.new`, but [init.py:143](src/forge/init.py#L143) creates an unsigned prototype and [story.py:122](src/forge/story.py#L122) refuses stories there. This defeats item 3 and its required fresh-repo test; changing `story.py` is explicitly forbidden.
   Gain 5, Work 3, Harm 3
   Disposition: cut

2. Blocking: Item 2 promises automatic landing where the existing merge policy requires a human.
   Raise: Not done — [plan:129](plans/FORGE-INTAKE-1.md#L129) delegates completion to `forge land`. [land.py:149](src/forge/land.py#L149) stops for a human merge, and the required adopted fixture explicitly sets `merge = "human"` at [forge.toml:5](tests/fixtures/adopted-v1.2.2/client/forge.toml#L5). The proposed test stops before invoking land, so it cannot expose this contradiction.
   Gain 4, Work 2, Harm 3
   Disposition: cut

3. Blocking: The keyword shortcut parks product requests that contain “later” without requesting deferral.
   Raise: Functional — [plan:106](plans/FORGE-INTAKE-1.md#L106) parks any whole-word match. The repository’s own example, “Shoppers can save a basket and come back to it later,” at [test_story.py:20](tests/test_story.py#L20), would therefore bypass sorting and enter the idea list. Here “later” describes product behaviour, contradicting item 4’s requirement for an owner decision to defer.
   Gain 4, Work 2, Harm 3
   Disposition: cut

4. Blocking: The prescribed helpers provide no way to carry ideas into the item’s first commit.
   Raise: Plan gap — [plan:156](plans/FORGE-INTAKE-1.md#L156) requires that first-commit carry. However, `fix_start` commits and publishes through [_new_checkout:171](src/forge/task.py#L171), and `story.new` commits and publishes at [story.py:157](src/forge/story.py#L157), before either returns to intake. SORT pins no carry interface; MOVE excludes `task.py`, and changing `story.py` is forbidden.
   Gain 4, Work 2, Harm 2
   Disposition: cut

5. Blocking: Test 6 requires a generated command page that client repos never receive.
   Raise: Plan gap — [plan:205](plans/FORGE-INTAKE-1.md#L205) requires `docs/commands.md` after client init and upgrade. [sync.py:636](src/forge/sync.py#L636) generates that page only for `forge-source`, while [init.py:290](src/forge/init.py#L290) uses the client adapter writer. Neither task includes a generator change that can satisfy this test.
   Gain 4, Work 1, Harm 1
   Disposition: cut

6. Advisory: Handback can start a sorted fix from the wrong checkout.
   Raise: Functional — [plan:83](plans/FORGE-INTAKE-1.md#L83) passes `top` into `intake.act`. In [native.py:201](src/forge/native.py#L201), that is the handback caller’s checkout; existing reads instead use the saved checkout at line 229. Starting from an unmerged fix and handing back from main would lose the parent base selected by [task.py:538](src/forge/task.py#L538). No proposed test covers this supported worktree flow.
   Gain 3, Work 3, Harm 3
   Disposition: cut

7. Advisory: Normal planning instructions still bypass the new intake.
   Raise: Not done — The edits at [plan:194](plans/FORGE-INTAKE-1.md#L194) leave “Planning a story” directing agents straight to `forge story new` at [skill.md:942](src/forge/templates/skill.md#L942). [nextstep.py:454](src/forge/nextstep.py#L454) also presents separate story and fix commands. These contradict the promised single entry path, while test 6 checks only the replaced table rows.
   Gain 3, Work 3, Harm 3
   Disposition: cut

8. Advisory: “Just fix it” creates another active item rather than moving the plan.
   Raise: Functional — [plan:179](plans/FORGE-INTAKE-1.md#L179) starts a fix and leaves the story unchanged. Its `planning` state remains, and [nextstep.py:482](src/forge/nextstep.py#L482) continues collecting that story and requesting its read through [nextstep.py:700](src/forge/nextstep.py#L700). The proposed test verifies preservation but never verifies that the original planning workflow stops.
   Gain 3, Work 4, Harm 2
   Disposition: cut

9. Advisory: Configured explore models can bypass the promised cost restriction.
   Raise: Not done — [plan:20](plans/FORGE-INTAKE-1.md#L20) promises never to use the most expensive models, but the selection at line 78 uses `worker_models`. [repo.py:611](src/forge/repo.py#L611) returns configured models without restriction, and [repo.py:698](src/forge/repo.py#L698) accepts arbitrary model strings. Existing explore or fallback-lite overrides can therefore select models the plan excludes; the proposed test checks only fixture defaults.
   Gain 3, Work 2, Harm 2
   Disposition: cut
