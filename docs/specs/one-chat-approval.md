---
slug: one-chat-approval
title: One main chat approves every Forge repo's stories
status: draft
saved: 2026-09-27T15:18:50+00:00
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
`forge next` runs, Forge adds the repo's main checkout to a per-machine list outside every repo,
in the user's config folder. The list is never committed and needs no upkeep: a checkout that no
longer exists, or no longer has a `forge.toml`, is skipped when read.

**The approval hook checks every remembered repo.** When the owner approves in Plan Mode (or
Codex's approval question), the hook looks for the story waiting for that approval in the chat's
own repo and in every remembered repo, across all their worktrees. Every existing check stays:
the exact text, the runtime and tool, the session and event identity, replay refusal, the cold
read, and the client sign-off gate, which is read from the story's own repo. Exactly one waiting
story in all of them must match, or nothing is recorded, as today. The approval is recorded and
committed in the story's own repo, on its story branch, as if the chat had started there.

**A repo on a different Forge version is refused.** If the matching story's repo pins a Forge
version other than the one installed, nothing is recorded and Forge says to upgrade that repo;
records are never written in another version's format.

**Nothing else changes.** Each repo's git hooks, checks and rules stay its own. Every other Forge
command already works in any checkout the chat names. The skill that starts a separate Remote
Control chat stays for when the owner wants one, but no step in Forge needs it.

## Acceptance criteria

- `forge init`, `forge migrate`, `forge sync` and `forge next` add the repo's main checkout to the
  per-machine list, once; missing checkouts and folders without `forge.toml` are skipped on read.
- A Plan Mode approval in a chat started in one repo records the approval of a story waiting in
  another remembered repo, in that repo's story branch, with every existing check applied.
- Two waiting stories with the same approved text across repos record nothing, as within one repo.
- A matching story in a repo pinned to another Forge version records nothing and names the
  upgrade.
- The guide says one chat can approve stories in every Forge repo on the machine.

## Success measure

- Metric: chats started only to approve a story in another repo.
- Baseline: one per story in another repo (2026-09-27: myclaw's approvals needed their own chat).
- Target: none.
- Check date: 2026-12-15

## Out of scope

- Running another repo's git hooks or deny rules from this chat.
- A command to list or edit the remembered repos.
- Approving across machines.

## Roadmap

- FORGE-ONECHAT-1: One main chat approves every Forge repo's stories
