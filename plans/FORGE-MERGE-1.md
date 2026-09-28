# The agent can merge a ready pull request when the owner allows it

## What changes for you

- In a repo where you allow it, the agent merges each pull request itself once Forge has found it
  ready: a clean review and every check green. You no longer have to come back to merge.
- The choice is yours per repo, in `forge.toml`, and it is off unless you turn it on. Only the
  setting on the default branch counts, so a change can't give itself permission, and turning it
  off takes effect at once.
- After a merge, Forge tidies up: the branch, the item's folder and its Codex chats go away, and
  `forge next` stops listing the item. A folder with unsaved changes is left in place, and Forge
  says so. Archived chats can still be restored in Codex.
- A cold read's Codex chat is archived as soon as the read is written, so reads don't pile up in
  your Codex list.
- In Forge's own repo it is turned on.

## Why

Forge lets only a human merge, and on this repo the owner merges every green pull request anyway,
so each ready item waits for the owner to come back, and the next item that needs its code waits
too. Other owners want the human gate, so it stays the default. This story builds the confirmed
spec `docs/specs/agent-merge.md`.

## Done when

1. `docs/specs/agent-merge.md` is confirmed by the owner and on the roadmap as FORGE-MERGE-1.
2. `forge.toml` accepts `merge = "agent"` or `merge = "human"` and refuses any other value as
   unusable; `forge merge` fetches the default branch first and reads the setting and the checks
   only from the default branch's `forge.toml`, so an item's own branch can neither grant the
   setting nor narrow the checks.
3. When `forge close` ends Ready, it records under `.git/forge/`, never committed, that the item is
   ready, with the commit it pushed and that its review was clean; with the setting it ends with
   `Next: forge merge <item>` and `forge next` names `forge merge <item>` for a ready item; without
   it, both keep saying a human merges.
4. `forge merge <item>` refuses without the setting, naming it; with it, it merges only an item
   recorded ready with a clean review whose open pull request targets the default branch, whose
   head is the recorded commit, and whose checks are all green on it, with the merge itself tied
   to that head commit; any of those failing refuses and merges nothing.
5. A merge squashes with the pull request's title, deletes the remote branch, fetches the default
   branch, and removes the item's worktree and local branch, leaving a worktree with uncommitted
   changes in place and saying so; it archives, through Codex's own archive call, every Codex
   conversation Forge recorded for the item; `forge next` no longer lists the item; the hook still
   refuses the agent's raw merge command in every repo.
7. A cold read archives its Codex conversation, through Codex's own archive call, right after it
   writes its notes; a failed archive is reported and never fails the read.
6. The generated AGENTS.md, the Forge skill and the guide describe the setting and `forge merge`,
   and say the agent merges only through `forge merge`; this repo's `forge.toml` has
   `merge = "agent"`.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| THE-OWNER-WANTS-THE-AGENT-TO-MERGE-READY | The spec | The confirmed spec and its roadmap item | 1 | `docs/specs/agent-merge.md`, `docs/specs/agent-merge.read.md`, `plans/roadmap.json` | | none | no |
| READY | Ready on record | The `merge` setting and its reader from the fetched default branch; close recording the ready record and naming the next step; `forge next` naming `forge merge`; a stub `forge merge` that refuses, with its command row in the CLI and the guide | 2, 3 | `src/forge/repo.py`, `src/forge/close.py`, `src/forge/nextstep.py`, `src/forge/merge.py`, `src/forge/cli.py`, `docs/guide.md` | `tests/test_merge_ready.py` | none | yes |
| MERGE | Forge merges | `forge merge`'s checks, the head-tied squash merge and the tidy-up, including archiving the item's recorded Codex conversations; the cold read archiving its own conversation; the driver's archive request | 4, 5, 7 | `src/forge/merge.py`, `src/forge/codex.py`, `src/forge/codex_turn.py`, `src/forge/story.py`, `src/forge/nextstep.py`, `tests/test_merge_ready.py` | `tests/test_merge_command.py` | READY | yes |
| DOCS | Tell the agent | The generated AGENTS.md's and the Forge skill's merge rules, the guide's section on the setting and `forge merge`, and this repo's `merge = "agent"` | 6 | `src/forge/templates/adapters/AGENTS.md`, `src/forge/templates/skill.md`, `AGENTS.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `docs/guide.md`, `forge.toml` | `tests/test_merge_docs.py` | READY | yes |

New moving parts: none

## Risks

- `forge merge` deletes the remote branch and removes the item's worktree and local branch. It
  does so only after the merge succeeded, never removes a worktree with uncommitted changes, and
  the merged commit keeps the work on the default branch.

## Notes

- READY pins the names: the setting `merge` with values `"agent"` and `"human"` (default
  `"human"`), the ready record `.git/forge/ready/<item>.json` with `commit` and `review`, and the
  command `forge merge <item>`. Keeping the record out of the branch leaves the checked head as it
  is.
- `forge merge` fetches the default branch and reads `origin/<default>:forge.toml` for both the
  setting and the `checks` list, never the item's checkout. The clean review comes from the ready
  record, so it doesn't depend on which checks are listed.
- `forge merge` waits on the checks with close's existing `checks.wait`, with no migration
  exception, and merges with `gh`'s squash merge tied to the recorded head commit
  (`--match-head-commit`), run from Forge's own Python, which the shell hook doesn't see.
- The hook's refusal of the agent's raw merge command stays as it is.
- Archiving goes through the Codex SDK driver (`codex_turn.py`) with a new `archive` request, the
  same path as a turn, so Forge never edits Codex's own files; tests use a throwaway Codex home.
  MERGE waits for FORGE-STEER-1/RESUME, which also changes `codex_turn.py`.
- READY owns the guide's command-list row; DOCS, which runs after it, owns the guide's prose.
  DOCS turns this repo's setting on, which takes effect only once a human merges its pull request.
- Each test file starts with `STORY = "FORGE-MERGE-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
