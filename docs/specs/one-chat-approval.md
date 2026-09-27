---
slug: one-chat-approval
title: One main chat approves every Forge repo's stories
status: confirmed
saved: 2026-09-27T15:18:50+00:00
confirmed_by: "vrknetha"
confirmed_hash: 19e131df57992cf7cc791576df0601aafab6ebafa85dcc7bd57e0e4859b4b981
---

# One main chat approves every Forge repo's stories

## Why

The owner runs Forge in several repos (this one, myclaw, the trial client) and wants to drive all
of them, every worktree included, from one main chat. Inside one repo that already works: the
approval hook finds the waiting story in any of the repo's worktrees. But the hook only looks at
the repo the chat started in, so a story in another repo can be approved only from a chat started
there. That costs a new chat, and its context, for every approval in another repo.

## Behaviour

**Forge remembers its repos.** Whenever `forge init`, `forge migrate`, `forge sync` or
`forge next` runs, Forge adds the repo's main checkout (the folder holding its shared `.git`), as
an absolute resolved path, to a per-machine list outside every repo: the file `forge/repos` in
the user's config folder (`$XDG_CONFIG_HOME`, else `~/.config`; `%APPDATA%` on Windows), one path
per line, each path once. The list is never committed and needs no upkeep: a checkout that no
longer exists, or no longer has a `forge.toml`, is skipped when read. A failed write never stops
the command that tried it; two commands adding at once at worst add a line twice, which reading
ignores.

**The approval hook checks every remembered repo.** When the owner approves in Plan Mode (or
Codex's approval question), the hook looks for the story waiting for that approval in the chat's
own repo and in every remembered repo, across all their worktrees. Every existing check stays:
the exact text, the runtime and tool, the session and event identity, replay refusal, the cold
read, and the client sign-off gate, which is read from the story's own repo. Exactly one waiting
story in all of them must match, or nothing is recorded, as today. The approval is recorded and
committed in the story's own repo, on its story branch, as if the chat had started there: that
commit runs the story repo's own git hooks, as any commit there does. The replay marker lives in
the story's repo (its `.git/forge/approvals/`), is checked after the one match is found and
before anything is written, and is written after the commit, as today.

**A repo on a different Forge version is refused.** If the matching story's repo pins a Forge
version other than the one installed, nothing is recorded, and Forge names both versions and says
to bring that repo's pin to the installed version (the owner asks the agent to upgrade it) before
approving again; records are never written in another version's format.

**Nothing else changes.** Each repo's git hooks, checks and rules stay its own. Every other Forge
command already works in any checkout the chat names. The skill that starts a separate Remote
Control chat stays for when the owner wants one, but its description and example no longer say an
approval needs a session in the story's checkout, and no step in Forge needs it.

## Acceptance criteria

- `forge init`, `forge migrate`, `forge sync` and `forge next` add the repo's main checkout to the
  per-machine list at the named path, once; missing checkouts and folders without `forge.toml`
  are skipped on read; a failed write doesn't fail the command.
- A Plan Mode approval in a chat started in one repo records the approval of a story waiting in
  another remembered repo, in that repo's story branch, with every existing check applied and
  the replay marker kept in the story's repo.
- Two waiting stories with the same approved text across repos record nothing, as within one repo.
- A matching story in a repo pinned to another Forge version records nothing and names both
  versions and the upgrade.
- The guide says one chat can approve stories in every Forge repo this machine has used, and the
  Remote Control skill no longer says approvals need their own session.

## Success measure

- Metric: chats started only to approve a story in another repo.
- Baseline: one per story in another repo (2026-09-27: myclaw's approvals needed their own chat).
- Target: none.
- Check date: 2026-12-15

## Out of scope

- Loading another repo's Claude Code or Codex hooks and deny rules into this chat; its git hooks
  still run on its own commits.
- A command to list or edit the remembered repos.
- Approving across machines.

## Roadmap

- FORGE-ONECHAT-1: One main chat approves every Forge repo's stories
