# One main chat approves every Forge repo's stories

## What changes for you

- You approve a story in any of your Forge repos from the one main chat, the same way as today:
  in Plan Mode. No new chat is needed for an approval.
- Forge remembers the repos you use it in by itself; there is nothing to set up or keep up.
- If the other repo is on a different Forge version, nothing is recorded, and Forge tells you
  which versions differ and to upgrade that repo first.

## Why

The owner drives several Forge repos and wants all of them, every worktree included, managed from
one main chat. The approval hook only sees stories in the repo the chat started in, so each story
in another repo has cost a new chat and its context. This story builds the confirmed spec
`docs/specs/one-chat-approval.md`.

## Done when

1. `docs/specs/one-chat-approval.md` is confirmed by the owner and on the roadmap as
   FORGE-ONECHAT-1.
2. After `forge init`, `forge migrate`, `forge sync` or `forge next` succeeds (never on a dry run,
   never after a refusal), Forge adds the repo's main checkout, the resolved parent of its shared
   git folder, to `forge/repos` in the user's config folder (`$XDG_CONFIG_HOME`, else
   `~/.config`; `%APPDATA%` on Windows), once; reading skips missing checkouts, folders without
   `forge.toml` and repeated lines; a failed write doesn't fail the command.
3. A Plan Mode approval in a chat started in one repo records the approval of the one story
   waiting in another remembered repo, committed on that repo's story branch (running its git
   hooks), with every existing check applied and the sign-off gate read from the story's repo;
   each repo is searched once, by its main checkout, whichever worktree the chat started in; an
   event already used in the chat's repo or the story's repo records nothing, and a recorded
   approval marks the event used in both; two matching stories across repos record nothing.
4. A matching story in a repo pinned to another Forge version records nothing: the pin is read
   before the rest of that repo's `forge.toml` and before anything is written there, and the
   refusal names both versions and says to bring that repo's pin to the installed version.
5. The guide says one chat approves stories in every Forge repo this machine has used, and the
   Remote Control skill's description and example no longer say an approval needs its own
   session.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| THE-OWNER-WANTS-EVERY-FORGE-REPO-S-STORI | The spec | The confirmed spec and its roadmap item | 1 | `docs/specs/one-chat-approval.md`, `docs/specs/one-chat-approval.read.md`, `plans/roadmap.json` | | none | no |
| REGISTRY | Remembered repos | The per-machine list: `main_checkout(path)`, `remember(top)` and `remembered()` in a new module, called from the command dispatch after init, migrate, sync or next succeeds | 2 | `src/forge/machine.py`, `src/forge/cli.py`, `tests/conftest.py` | `tests/test_onechat_registry.py` | none | no |
| APPROVE | Approve anywhere | The approval hook matching across the chat's repo and every remembered repo, the story repo's replay marker and sign-off, and the version refusal | 3, 4 | `src/forge/approval.py` | `tests/test_onechat_approval.py` | REGISTRY | yes |
| DOCS | Say so | The guide's approval section and the Remote Control skill's wording, template and generated copy | 5 | `docs/guide.md`, `src/forge/templates/skills/remote-approval/SKILL.md`, `.claude/skills/remote-approval/SKILL.md` | `tests/test_onechat_docs.py` | APPROVE | yes |

New moving parts: the per-machine file `forge/repos` in the user's config folder, with its reader and writer in `src/forge/machine.py` (Done-when 2)

## Risks

Risks: none

## Notes

- REGISTRY pins the names: the module `src/forge/machine.py` with `main_checkout(path: Path) ->
  Path` (the resolved parent of `git rev-parse --git-common-dir`), `remember(top: Path) -> None`
  (never raises) and `remembered() -> list[Path]` (existing main checkouts with `forge.toml`, each
  once), and the file `forge/repos` in the config folder. Dispatch calls `remember` only after the
  command returns success, skips `--dry-run`, and only when the main checkout has `forge.toml`.
- APPROVE searches `{main_checkout(chat repo)} ∪ remembered()`, deduplicated by main checkout, and
  uses `story.stories_here(path)` for each, so every worktree of every repo is covered once.
- APPROVE checks the event's replay marker in both the chat's repo and the story's repo before
  writing, and writes it to both after the commit.
- The version check reads only the `version` key of the story repo's `forge.toml` first and
  compares it with the installed Forge, before `check_pin` or any write in that repo; the refusal
  reads: "<repo> pins Forge <pinned>, but <installed> is installed, so nothing was recorded."
  with "Next: ask your agent to upgrade <repo> to <installed>, then approve again".
- DOCS goes last, so what it describes exists; `docs/guide.md` is also in FORGE-MERGE-1 and
  FORGE-STEER-1 tasks, and Forge's Scope overlap rule orders them.
- Each test file starts with `STORY = "FORGE-ONECHAT-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
