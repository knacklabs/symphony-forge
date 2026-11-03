---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-28T14:45:29.891534+00:00
seconds: 103.216
read_hash: cfd89f6b6e315e26b21c58ea4748c18296b34906
round: 2
passed: yes
doc_seen: cfd89f6b6e315e26b21c58ea4748c18296b34906
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: c2a682bc74d23430ba43a792b314e5b3e82160bd
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a182e5-12cc-7d22-b3a7-02d4fd33da67
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

1. Blocking: Not done: item 3 does not ensure Should findings remain advice.
   Raise: Plan gap
   Case: normal use - a reviewer scores `Agents advice: Route by difficulty` Gain 4, Work 2, Harm 2
   Disposition: cut - the review rule now scores an `Agents advice:` finding Gain 1 or 2, and the test pins a Gain 2 case that does not block..
   [plans/FORGE-AGENTS-1.md:532](/plans/FORGE-AGENTS-1.md:532) specifies P2 and no floor, but [src/forge/score.py:127](/src/forge/score.py:127) decides scored findings by scores regardless of priority. That advice still blocks close. Neither the review wording nor the test pins how this case stays advisory.
   Gain 4, Work 2, Harm 2

2. Blocking: Not done: item 3 excludes prompt changes that break explicit Must rules.
   Raise: Not done
   Case: normal use - a builder changes only the system prompt without the required case, evaluation or prompt version.
   [plans/FORGE-AGENTS-1.md:567](/plans/FORGE-AGENTS-1.md:567) expressly exempts prompt-only changes. This contradicts the Must rules at lines 492 and 498 and the promise to report new agent work that breaks them. The exclusion is a planner choice, not an owner decision.
   Gain 4, Work 1, Harm 2
   Disposition: cut - the prompt-only exemption is removed; a prompt edit is agent code and is checked.

3. Blocking: Not done: item 3 omits the normal prototype review path.
   Raise: Plan gap
   Case: normal use - a new client builds its first chat agent before sign-off.
   REVIEW updates only the full review’s database-adjacent block. [src/forge/review.py:371](/src/forge/review.py:371) instead selects `review-light.md` for prototype fixes; that template explicitly limits review to three checks. Additionally, [src/forge/review.py:207](/src/forge/review.py:207) selects P0-only blocking, so the proposed Gain 4, Work 2 floor would not hold an ordinary Must violation there. The planned task-based test exercises neither difference.
   Gain 4, Work 2, Harm 2
   Disposition: keep - the prototype review is P0 only by design (`blocking_level`, `review-light.md`), and the database rule behaves the same; the plan now says so in What changes for you and in the review part, and the test pins it.

4. Blocking: The recall example cancels the late result it promises to deliver.
   Raise: Not done
   Case: normal use - a memory lookup takes 100 ms against the specified 80 ms wait.
   [plans/FORGE-AGENTS-1.md:296](/plans/FORGE-AGENTS-1.md:296) prescribes `asyncio.wait_for(task, 0.08)` while requiring the late result for the next turn. That call cancels the lookup on timeout, so no late result remains. This contradicts the rule and default immediately above it. [Python’s documentation](https://docs.python.org/3.13/library/asyncio-task.html#asyncio.wait_for) confirms the cancellation behavior.
   Gain 3, Work 1, Harm 3
   Disposition: cut - the example now uses `asyncio.wait({task}, timeout=0.08)`, which does not cancel the lookup.

5. Advisory: The web-only skill retains a phone-call testing requirement.
   Raise: Not done
   [plans/FORGE-AGENTS-1.md:492](/plans/FORGE-AGENTS-1.md:492) includes “real phones and real calls” in a Must rule. Phone calls are explicitly excluded by the skill and the settled owner decision at line 559. The harness default was adapted to web chat, but this requirement was not.
   Gain 2, Work 1, Harm 1
   Disposition: cut - the Must rule now names the real web chat and the speech providers, not phones.

6. Advisory: Split: SKILL → skill content and delivery; builder and coordinator naming.
   Raise: Plan gap
   [plans/FORGE-AGENTS-1.md:544](/plans/FORGE-AGENTS-1.md:544) combines the 446-line skill, both generated copies, shipping, brief and coordinator changes, and four test files. The three skill copies alone add 1,338 lines, exceeding the requested task-size guideline before wiring and tests.
   Gain 2, Work 2, Harm 1
   Disposition: keep - the three skill copies are one text that sync copies, so the builder writes one page; a split adds a task and a wait for little.

## Round 2

No findings.
