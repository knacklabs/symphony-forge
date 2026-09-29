# You switch on agent merges yourself

1 part · Risks: none · New moving parts: none

## What changes for you

- To let the agent merge a repo's ready pull requests, you run one command in your own terminal;
  it opens the change for you to merge.
- The agent never tries to make that switch itself, and when agent merges are off it tells you the
  exact command to run.

## Why

Forge tells the owner to ask the agent to set `merge = "agent"`, but Claude Code's own permission
check rightly stops the agent from loosening a gate on itself, even when the owner says so. So
nobody can make the switch through the flow.

## Done when

1. **You switch a repo to agent merges with one command.**
2. **The agent never makes the switch and points you to the command.**

## Risks

Risks: none

## For the builders

### Done-when details

1. `forge merge enable`, run on the default branch, starts a fix that sets `merge = "agent"` in
   `forge.toml`, commits it, pushes it and opens its pull request, then prints that the owner
   merges it to switch on agent merges. It refuses, changing nothing, when run from an agent (the
   `CLAUDECODE` or `CODEX_THREAD_ID` variable is set), when not on the default branch, and when
   agent merges are already on, each with a plain message. Tests run the command in a throwaway
   repo with a fake `gh`: a normal run opening the fix, and each refusal with nothing created.
2. `forge merge`'s disabled message says to run `forge merge enable` in your own terminal. The
   skill says the `merge` setting is the owner's: the agent never changes it to `"agent"` and
   gives the owner that command instead; its "Ask, then in a fix" row excludes that setting. The
   command table lists the new command. Tests check the refusal text through `forge merge` and the
   synced skill through `forge sync`.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Merge switch | The owner-only `forge merge enable` command, its messages and the skill's rule | 1, 2 | `src/forge/merge.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `docs/commands.md` | `tests/test_merge_enable.py` | none | yes |

New moving parts: none

## Notes

- The command reuses how `forge fix start` and `forge close` start a fix and open its pull request.
- No client repo is named anywhere in this story.
- Opus writes the skill text; a Claude worker builds the command.
- Each new test file starts with `STORY = "FORGE-MERGESWITCH-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
