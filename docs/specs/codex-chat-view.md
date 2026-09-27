---
slug: codex-chat-view
title: Forge's Codex chats are easy to follow in the Codex app
status: draft
saved: 2026-09-27T16:54:48+00:00
---

# Forge's Codex chats are easy to follow in the Codex app

## Why

The owner follows Forge's work in the Codex app, on the laptop and the phone. Every task and fix
runs in its own worktree folder, and the app groups chats by folder, so each shows as a separate
project. Chat names are long ("Fix · <whole fix slug> · <whole why>"), and the preview line is the
first message, which is the whole brief. Finding and reading one chat takes scrolling and guessing.
The Codex app-server, through the SDK version Forge pins, can set a chat's project, attach its pull
request and name it; Forge uses none of these.

## Behaviour

**Chats group under their repo.** When Forge starts or resumes a worker chat, it looks up the Codex
project whose root is the repo's main checkout and puts the chat in that project. The worktree
stays the chat's working folder, so where the worker runs and what it may change are unchanged.
If no project has that root, Forge leaves the chat as it is and creates none. A failure to set the
project is reported in the work log and never fails the round.

**Each chat links its pull request.** When `forge close` opens or finds the item's pull request, it
attaches the pull request to the item's recorded chat the same way the Codex app does, once. A
failure is reported in the close output and never fails the close.

**Short names and a readable preview.** A worker chat is named "<KEY> · <task name>" for a task and
"Fix · <first words of the why>" for a fix, at most 60 characters, and its kind shows only as that
short prefix where it isn't a task. A cold read is named "Read · <KEY or spec>". Every brief starts
with one plain line saying what the round is for, before the full brief, so the app's preview reads
as a sentence.

**Nothing else changes.** No worker's working folder, sandbox, model or brief content changes beyond
the first line; no chat is pinned, moved into a folder or labelled otherwise.

## Acceptance criteria

- A worker chat for a task or fix in a repo with a matching Codex project is in that project, and
  its working folder is still the item's worktree; with no matching project, nothing is changed and
  the round runs as before.
- After `forge close` opens a pull request, the item's chat carries it as an attachment; a failed
  attach doesn't fail the close.
- Chat names follow the formats above and stay within 60 characters.
- Every brief's first line is a one-line plain summary of the round.
- Tests use a throwaway Codex home and never touch the owner's real chats.

## Success measure

- Metric: Codex app projects that hold Forge chats for this repo.
- Baseline: one per worktree folder (dozens on 2026-09-27).
- Target: one (the repo's own project).
- Check date: 2026-12-15

## Out of scope

- A "Forge" folder or label in the app.
- Pinning chats or nesting a story's chats under one parent (the app-server offers neither).
- Changing where workers run.

## Roadmap

- FORGE-CHATVIEW-1: Forge's Codex chats are easy to follow in the Codex app
