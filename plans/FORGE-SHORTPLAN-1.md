# The plan you approve is short

2 parts · Risks: none · New moving parts: none

## What changes for you

- The plan you approve fits on one screen: what changes for you, why, one plain sentence per
  result, and risks.
- Test cases, edge cases, tasks and notes sit below, for the agents, and you don't see them when
  approving.
- Tightening those details never needs your approval again; changing a result or what changes for
  you still does.

## Why

The approval shows the whole story doc, with test lists, task tables and builder notes that only
agents use, so the part the owner must judge is buried.

## Done when

1. **New plans put one plain sentence per result on top and the details below.**
2. **You approve only the top part.**
3. **Workers and reviewers still get every detail of the results they cover.**
4. **Plans written the old way keep working.**

## Risks

Risks: none

## For the builders

### Done-when details

1. Forge's story template has each Done-when item as one bold plain sentence and a
   `### Done-when details` section under `## For the builders`, holding each item's evidence, edge
   cases and proving tests under the same number. The skill's planning steps say so, and that a
   Done-when sentence has no code names, file paths or test names.
2. Forge's instructions (the skill, the AGENTS.md block and `forge next`'s approval step) show the
   story doc from its title down to `## For the builders`, not the whole doc, in Plan Mode. The
   approval still binds only "What changes for you" and "Done when", so an edit under
   `## For the builders` needs no new approval. A test approves a plan made of only the top part
   and then changes a detail without losing the approval.
3. The worker brief and the review list each covered item as its sentence followed by its details
   from `### Done-when details`; items the task doesn't cover stay context, sentence only. Tests
   run `forge work` and `forge close` on a story with details and check both carry them.
4. A story doc without `### Done-when details` is read as today: each item's whole text is its
   sentence and there are no separate details. A test runs `forge work` and `forge close` on such
   a doc.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Short plans | The story template, the skill's planning steps and the Plan Mode instructions | 1, 2 | `src/forge/templates/story.md`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `src/forge/templates/adapters/AGENTS.md`, `AGENTS.md`, `src/forge/nextstep.py`, `tests/test_split_ships.py` | `tests/test_shortplan_docs.py`, `tests/test_split_ships.py` | none | yes |
| BRIEF | Details reach the builders | Each covered item's details in the worker brief and the review, and old docs read as today | 3, 4 | `src/forge/story.py`, `src/forge/review.py`, `src/forge/worker.py` | `tests/test_shortplan_briefs.py` | none | yes |

New moving parts: none

## Notes

- BRIEF pins `story.details(text) -> dict[int, str]`: the numbered entries of
  `### Done-when details`, each entry's whole text including wrapped lines, or `{}` when the
  section is missing. SPEC's template uses that exact heading and numbering.
- This story's own doc is written in the new shape.
- The loop story's tasks change `story.py`, `nextstep.py`, `skill.md` and the AGENTS.md block too;
  Forge's overlap check makes these tasks wait for them.
- Opus writes SPEC's text; a Claude worker builds BRIEF.
- Each new test file starts with `STORY = "FORGE-SHORTPLAN-1"`, and its `test_<n>_` names cite
  the Done-when items its task covers.
