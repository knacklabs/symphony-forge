---
slug: agent-merge
title: The agent can merge a ready pull request when the owner allows it
status: draft
saved: 2026-09-27T14:52:56+00:00
---

# The agent can merge a ready pull request when the owner allows it

## Why

Forge lets only a human merge. Its hook refuses `gh pr merge` from the agent, and `forge close`
ends with "A human merges its pull request." On this repo the owner merges every green pull
request anyway and has given standing permission, so each ready item waits for the owner to come
back, and the next item that needs its code waits too. Other owners want the human gate, so this
has to be the owner's choice, per repo.

## Behaviour

**The owner's setting.** `forge.toml` takes `merge = "agent"`; without it, or with
`merge = "human"`, nothing changes from today. Any other value is refused as an unusable
forge.toml. The owner asks the agent to change the setting, like every other setting.

**`forge merge <item>`.** It refuses unless the repo's setting is `merge = "agent"`, naming the
setting. It refuses unless the item's last `forge close` ended Ready (a clean review) and the
pull request's head is still the commit that close pushed, and it waits on the required checks on
that head the same way close does, refusing if one fails. Then it squash-merges the pull request
with its title as the subject, deletes the remote branch, removes the item's worktree and local
branch, and prints what merged. A task whose merge is its story's last one still leaves
`forge story done` to the coordinator.

**The agent never merges any other way.** The hook keeps refusing a raw `gh pr merge` in every
repo; `forge merge` is the only path, so the close rule always holds.

**Forge says the right next step.** With `merge = "agent"`, `forge close` ends with
"Ready: … Next: forge merge <item>" and `forge next` names `forge merge <item>` for a ready item;
with the default, both keep saying a human merges. The generated AGENTS.md and the Forge skill
say that the human merges unless the repo's `forge.toml` has `merge = "agent"`, in which case
the agent runs `forge merge` once close says Ready. The guide lists `forge merge` and the setting.

**This repo turns it on.** Forge's own `forge.toml` gets `merge = "agent"`.

## Acceptance criteria

- Without `merge = "agent"`, `forge merge` refuses and names the setting; close and next keep
  saying a human merges.
- With it, `forge merge` merges only an item whose close ended Ready, whose pull request head is
  the commit close pushed and whose required checks are green on it; any of those failing
  refuses and merges nothing.
- A merge squashes with the pull request's title, deletes the remote branch, and removes the
  item's worktree and local branch; `forge next` no longer lists the item.
- A raw `gh pr merge` from the agent is still refused in every repo.
- The generated AGENTS.md, the Forge skill and the guide describe the setting and `forge merge`;
  this repo's `forge.toml` has `merge = "agent"`.

## Success measure

- Metric: median time from `forge close` printing Ready to the pull request merging, on this repo.
- Baseline: several hours on 2026-09-26 and 27 (estimated; ready items waited for the owner).
- Target: under 10 minutes.
- Check date: 2026-12-15

## Out of scope

- Merge methods other than squash.
- Merging without a clean `forge close`.
- Auto-merge that fires without the agent running `forge merge`.
- Marking a story done automatically after its last merge.

## Roadmap

- FORGE-MERGE-1: The agent can merge a ready pull request when the owner allows it
