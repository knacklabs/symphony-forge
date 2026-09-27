---
slug: codex-chat-view
title: Forge's Codex chats are easy to follow in the Codex app
status: confirmed
saved: 2026-09-27T16:54:48+00:00
confirmed_by: "vrknetha"
confirmed_hash: 3bb6a14dc403fe9e50166db37897bb47d0f0005b37569dc1116d7d613298f5ff
---

# Forge's Codex chats are easy to follow in the Codex app

## Why

The owner follows Forge's work in the Codex app, on the laptop and the phone. Every task and fix
runs in its own worktree folder, and the app groups chats by folder, so each shows as a separate
project. Chat names are long ("Fix · <whole fix slug> · <whole why>"), the preview line is the
first message, which is the whole brief, and nothing in the chat leads to its pull request.
Finding and reading one chat takes scrolling and guessing, and going from a chat to its pull
request means searching GitHub. The Codex app-server, through the SDK version Forge pins, can set a
chat's project, attach its pull request and name it; Forge uses none of these.

## Behaviour

**Chats group under their repo.** Right after Forge starts or resumes any Codex chat for its work
(a worker round or a cold read), it puts the chat into the Codex project for its repo. The repo's
main checkout is the resolved parent of `git rev-parse --git-common-dir`; Forge sends
`project/list` and picks the one project that has a root equal to that path, compared as resolved
paths. With no such project, or more than one, it assigns nothing. It assigns with
`thread/metadata/update {threadId, projectId}`, sent through the SDK client's raw request call,
since the pinned SDK has no helper for either request. The worktree stays the chat's working
folder, so where the worker runs and what it may change are unchanged. A failed request is written
to the work log and never fails the round or the read. Chats from before this change stay where
they are.

**Each chat links its pull request.** Each time `forge close` opens or finds the item's pull
request, it attaches it to the item's recorded chat with `thread/attachment/add`, as the Codex app
does: `attachmentType` "pull_request", `identityKey` `["github.com","<owner>","<repo>",<number>]`,
and a payload with the pull request's URL, the main checkout as `root`, and its head branch.
Adding the same identity again changes nothing, so every close may send it. With no recorded chat
it sends nothing; a failure is reported in the close output and never fails the close.

**Short names.** A chat is named once, when it starts, and keeps that name on later rounds: a task
chat "<KEY> · <task name>", a fix chat "Fix · <why>", a cold read "Read · <KEY or spec slug>". A
name longer than 60 characters is cut at the last whole word that fits in 59 and ends with "…".

**A readable preview.** Every worker brief (Codex or Claude) and every cold-read prompt starts with
one plain line before the rest: "Build <task name> for <KEY>." on a task's first round, "Fix
round <n> on <task name or why>." on a later round, "Fix: <why>." on a fix's first round, and
"Cold read of <KEY or spec slug>." for a read.

**Nothing else changes.** No worker's working folder, sandbox, model or brief content changes
beyond the first line; no chat is pinned, moved into a folder or labelled otherwise.

## Acceptance criteria

- A worker or cold-read chat in a repo with exactly one matching Codex project is in that project,
  and a worker's working folder is still the item's worktree; with no match or several, the chat's
  project is left as it is and the round runs as before.
- After `forge close` finds or opens a pull request, the item's chat carries it as an attachment
  with the pinned identity; repeating the close adds no duplicate; a failed attach doesn't fail
  the close.
- Chat names follow the formats above, are set once, and stay within 60 characters.
- Every worker brief's and cold-read prompt's first line is the pinned summary line.
- Tests use a throwaway Codex home and never touch the owner's real chats.

## Success measure

- Metric: Codex app projects that hold Forge chats for this repo started after this ships.
- Baseline: one per worktree folder (dozens on 2026-09-27).
- Target: one (the repo's own project).
- Check date: 2026-12-15

## Out of scope

- Moving chats from before this change.
- A "Forge" folder or label in the app.
- Pinning chats or nesting a story's chats under one parent (the app-server offers neither).
- Changing where workers run.

## Roadmap

- FORGE-CHATVIEW-1: Forge's Codex chats are easy to follow in the Codex app
