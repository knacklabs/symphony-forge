# Forge's Codex chats are easy to follow in the Codex app

## What changes for you

- In the Codex app, on the laptop or the phone, Forge's chats for a repo sit together under that
  repo's project instead of one project per working folder.
- Each chat has a short name you can read at a glance, such as "FORGE-TRIM-1 · Migrate guide", and
  its preview line says in one sentence what that round is doing.
- Each chat carries a link to its pull request once one exists.
- Chats from before this change stay where they are.

## Why

The owner follows Forge's work in the Codex app, and today each task's chat is its own project with
a long name and the whole brief as its preview, with no way to reach its pull request. This story
builds the confirmed spec `docs/specs/codex-chat-view.md`.

## Done when

1. `docs/specs/codex-chat-view.md` is confirmed by the owner and on the roadmap as FORGE-CHATVIEW-1.
2. A worker or cold-read chat in a repo with exactly one Codex project rooted at its main checkout
   is put in that project right after it starts or resumes, through the SDK's raw request with
   `project/list` and `thread/metadata/update`; with no match or several, its project is left as it
   is; a worker's working folder is still its worktree; a failed request is written to the work log
   and never fails the round or read.
3. A chat is named once when it starts, "<KEY> · <task name>", "Fix · <why>" or
   "Read · <KEY or spec slug>", cut at the last whole word within 59 characters plus "…" when
   longer, and keeps that name on later rounds.
4. Every worker brief and cold-read prompt starts with its pinned summary line: "Build <task name>
   for <KEY>.", "Fix round <n> on <task name or why>.", "Fix: <why>." or "Cold read of <KEY or
   spec slug>.".
5. Each `forge close` that finds or opens a pull request attaches it to the item's recorded chat
   with `thread/attachment/add` and the pinned identity and payload; a repeat adds no duplicate;
   with no recorded chat nothing is sent; a failure is reported and never fails the close.
6. Tests use a throwaway Codex home and never touch the owner's real chats.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| FORGE-S-CODEX-CHATS-SHOW-AS-ONE-PROJECT | The spec | The confirmed spec and its roadmap item | 1 | `docs/specs/codex-chat-view.md`, `docs/specs/codex-chat-view.read.md`, `plans/roadmap.json` | | none | no |
| START | Chat start | In the driver: the project lookup and assignment after start or resume, naming only on a fresh start, and the `attach` request the close uses; the main checkout passed from Forge | 2, 3, 6 | `src/forge/codex_turn.py`, `src/forge/codex.py` | `tests/test_chatview_start.py` | none | yes |
| WORDS | Names and previews | The name formats and the summary lines in the worker's and cold read's prompts | 3, 4 | `src/forge/worker.py`, `src/forge/story.py`, `src/forge/templates/brief.md`, `src/forge/templates/cold-read.md` | `tests/test_chatview_words.py` | none | yes |
| ATTACH | Pull request link | `forge close` attaching the pull request to the item's chat through the driver's `attach` request | 5, 6 | `src/forge/close.py` | `tests/test_chatview_attach.py` | START | yes |

New moving parts: none

## Risks

Risks: none

## Notes

- START pins the driver's request fields: the request gains `root` (the main checkout, the resolved
  parent of `git rev-parse --git-common-dir`) and a request kind `attach` with `thread`, `identity`
  (`["github.com","<owner>","<repo>",<number>]`) and `payload` (`url`, `root`, `headBranch`).
  The driver emits `project=<id>` or `project_skipped=<reason>` lines, which Forge writes to the
  work log. `codex.py` exposes `attach(top, item, pr)` for ATTACH.
- WORDS owns the name strings; START sets a name only when the chat is new, using the name the
  caller passes, so the two share only the existing `name` field of the request.
- `project/list` and the `projectId` field are experimental in the app-server; the SDK sends the
  experimental flag already, and every call's failure is non-fatal.
- The work waits for FORGE-STEER-1's and FORGE-MERGE-1's tasks that change `codex_turn.py`,
  `codex.py`, `close.py` and `worker.py`; Forge's Scope overlap rule orders them.
- Each test file starts with `STORY = "FORGE-CHATVIEW-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
