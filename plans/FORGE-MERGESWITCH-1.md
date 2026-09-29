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
   `forge.toml` (a top-level key placed before the first table, keeping the file's line endings),
   commits it, and runs `forge close` on it, so the change is reviewed and its pull request opened;
   it then prints that the owner merges that pull request to switch on agent merges. Its fix always has the same name, so run again
   after an interruption (before or after the commit, the push, or the pull request) it finds that
   fix and continues from where it stopped, and never touches any other fix: the command knows its fix by the `why` and `done_when` it records
   when it starts it, and a fix with that name but any other `why` is left alone while the command
   refuses naming it. `forge merge` never
   merges a change to the `merge` setting, even where agent merges are otherwise allowed (a
   prototype before sign-off), so the owner always merges this pull request;
   `forge close` and `forge next` on that fix say the owner merges it, never `forge merge`, so the command's whole
   output gives one valid next step. It refuses,
   changing nothing, when run from an agent (the `CLAUDECODE` or `CODEX_THREAD_ID` variable is
   set), when not on the default branch, and when the default branch's `forge.toml` already says
   `merge = "agent"`; a prototype that merges by agent only before sign-off doesn't count as on.
   Tests run the command in a throwaway repo with fake `gh` and review: a normal run reaching
   Ready, a CRLF `forge.toml` ending in a table, a rerun after an interruption before the commit, after it, after the push and after
   the pull request, `forge merge` refusing the switch's pull request in a prototype, the whole output of a
   prototype run and `forge next` afterwards naming only the owner's merge, an unrelated fix already using the name, a rerun before the `forge.toml` edit, a
   differently named fix that changes `merge` refused by `forge merge` in a prototype, each refusal with
   nothing created, and a prototype before sign-off.
2. `forge merge`'s disabled message says to run `forge merge enable` in your own terminal. The
   skill says the `merge` setting is the owner's: the agent never changes it to `"agent"` and
   gives the owner that command instead; its "Ask, then in a fix" row excludes that setting. The
   command table lists the new command. Tests check the refusal text through `forge merge` and the
   synced skill through `forge sync`, and that `forge merge <item>` still works beside
   `forge merge enable`.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Merge switch | The owner-only `forge merge enable` command, its messages and the skill's rule | 1, 2 | `src/forge/merge.py`, `src/forge/cli.py`, `src/forge/close.py`, `src/forge/nextstep.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `docs/commands.md` | `tests/test_merge_enable.py` | none | yes |

New moving parts: none

## Notes

- The command reuses how `forge fix start` and `forge close` start a fix and open its pull request.
- No client repo is named anywhere in this story.
- Opus writes the skill text; a Claude worker builds the command.
- Each new test file starts with `STORY = "FORGE-MERGESWITCH-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
