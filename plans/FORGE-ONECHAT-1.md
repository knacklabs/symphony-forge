# One main chat approves every Forge repo's stories

## What changes for you

- You approve a story in any of your Forge repos, such as myclaw or the trial client, from the one
  main chat, the same way as today: in Plan Mode. No new chat is needed for an approval.
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
2. `forge init`, `forge migrate`, `forge sync` and `forge next` add the repo's main checkout, as an
   absolute resolved path, to `forge/repos` in the user's config folder (`$XDG_CONFIG_HOME`, else
   `~/.config`; `%APPDATA%` on Windows), once; reading skips missing checkouts, folders without
   `forge.toml` and repeated lines; a failed write doesn't fail the command.
3. A Plan Mode approval in a chat started in one repo records the approval of the one story
   waiting in another remembered repo, committed on that repo's story branch (running its git
   hooks), with every existing check applied, the sign-off gate read from the story's repo, and
   the replay marker checked and kept in the story's repo; two matching stories across repos
   record nothing.
4. A matching story in a repo pinned to another Forge version records nothing, and the refusal
   names both versions and says to bring that repo's pin to the installed version.
5. The guide says one chat approves stories in every Forge repo this machine has used, and the
   Remote Control skill's description and example no longer say an approval needs its own
   session.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| THE-OWNER-WANTS-EVERY-FORGE-REPO-S-STORI | The spec | The confirmed spec and its roadmap item | 1 | `docs/specs/one-chat-approval.md`, `docs/specs/one-chat-approval.read.md`, `plans/roadmap.json` | | none | no |
| REGISTRY | Remembered repos | The per-machine list: `remember(top)` and `remembered()` in a new module, called from the command dispatch for init, migrate, sync and next | 2 | `src/forge/machine.py`, `src/forge/cli.py` | `tests/test_onechat_registry.py` | none | no |
| APPROVE | Approve anywhere | The approval hook matching across the chat's repo and every remembered repo, the story repo's replay marker and sign-off, and the version refusal | 3, 4 | `src/forge/approval.py` | `tests/test_onechat_approval.py` | REGISTRY | yes |
| DOCS | Say so | The guide's approval section and the Remote Control skill's wording, template and generated copy | 5 | `docs/guide.md`, `src/forge/templates/skills/remote-approval/SKILL.md`, `.claude/skills/remote-approval/SKILL.md` | `tests/test_onechat_docs.py` | APPROVE | yes |

New moving parts: none

## Risks

Risks: none

## Notes

- REGISTRY pins the names: the module `src/forge/machine.py` with `remember(top: Path) -> None`
  (never raises) and `remembered() -> list[Path]` (existing main checkouts with `forge.toml`,
  each once), and the file `forge/repos` in the config folder.
- APPROVE reads `machine.remembered()` plus the chat's own repo, and uses
  `story.stories_here(path)` for each, so every worktree of every repo is covered.
- The version check compares the story repo's `forge.toml` pin with the installed Forge before
  anything is written in that repo.
- DOCS goes last, so what it describes exists; `docs/guide.md` is also in FORGE-MERGE-1 and
  FORGE-STEER-1 tasks, and Forge's Scope overlap rule orders them.
- Each test file starts with `STORY = "FORGE-ONECHAT-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
