# The board's data knows who owns what, what shipped when, and what was left

6 parts · Risks: none one-way · New moving parts: none

## What changes for you

- In the board's data, every person carries their GitHub username beside their name, for past
  work too. The new board page in the next story shows it; today's page keeps showing names.
- A manager can give a story, or one of its parts, to a developer by GitHub username. That
  developer's next step then starts those parts first, and the board shows the owner.
- Each round of a part or fix keeps how long it took: work, waiting in line, waiting for a
  person and waiting for checks.
- The problems a review kept below the bar are listed per item and per file, with their scores
  and why they were kept.
- Forge reads the repo's releases from its tags: what each release carried, and when each story
  went live.
- After an upgrade, Forge fills owners, known issues and releases in for past work from git and
  GitHub. A fact Forge never recorded stays unknown; it is never guessed.

## Why

The owner approved a new board design on 15 October 2026: a manager and a developer read the
board in a minute, a manager assigns stories, go-live means released, and velocity shows each
person as a share of the team. A check of the design against Forge's data found the gaps this
story closes: people show as a mix of git names and logins, there is no way to assign a story,
round times are folded into sentences, kept review findings are only a count, and releases are
not known at all. The board page itself is the next story; it needs these facts first.

## Done when

1. **Every person the board's data names carries a GitHub username beside the name, for past and new work, in Forge's repo and in client repos.**
2. **A manager can give a story or one part to a developer by GitHub username; that developer's next step starts those parts first, and the board shows the owner.**
3. **Each round of a part or fix records how long it took, split into work, waiting in line, waiting for a person and waiting for checks.**
4. **Every problem a review kept below the bar is listed with its item, file, score and why it was kept, for all work since the repo adopted Forge.**
5. **Forge lists the repo's releases from its tags, what each one carried and when each story was released; a repo with no tags gets an empty list that says so.**
6. **On upgrade, Forge fills owners, known issues and releases in for past work from git and GitHub, and anything it never recorded stays unknown.**

## New and existing repos

- **New repos** (init or adoption): every fact above from their first item. The guide tells the
  coordinator how to assign a story. Tested on a repo made by `forge init`.
- **Existing repos** (on upgrade to this release): the upgrade backfills owners, known issues
  and releases from git and GitHub. Rounds closed before the upgrade keep their sentence and show
  no per-round time. Findings from before review scores existed show "no score". Tested on the
  adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Assigning writes the plan's Developer column through the story's own pull
request, so it reverts with that pull request. The backfill only reads git and GitHub and writes
derived facts that the next upgrade can rebuild.

## For the builders

### Done-when details

Story owner: a story's owner is the `Owner: <login>` line written directly under
`## For the builders` in its plan. A part's Developer cell overrides the owner for that part; a
part with an empty cell belongs to the owner.

1. People stay strings for today's readers, so today's page keeps working and keeps showing names. `forge board --json` adds a login beside each person
   field, without changing the existing ones: `started_by_login`, `approved_by_login`,
   `developer_login`, `merged_by.login` (already an object) and `login` on each trends person;
   `viewer` is the caller's GitHub login (`task.github_login`). Trends key people by login and keep
   the name. Owner decision 15 October (narrow): logins come only from records that already hold
   them (pull request authors and mergers, plan Developer cells, the viewer's own login); Forge
   never looks a plain git author up through GitHub, so the board needs no GitHub CLI. When only
   a git name exists, the login is null and the name stays; the upgrade backfill fills what pull
   requests show. The current HTML board keeps working
   unchanged. Tests: one board read in a new repo and one in the adopted fixture; the HTML board
   still renders.
2. `forge assign <KEY> <login>` writes the story's `Owner:` line; `forge assign <KEY/TASK> <login>`
   writes that part's Developer cell. A story with no plan is refused and says to plan it first.
   The command commits on the story branch and pushes it, so every checkout sees it after a fetch.
   `forge next` reads the owner and Developer cells from the story branch on the remote, and for
   that login offers its parts first. The board JSON carries `owner` per story and per part.
   skill.md, both synced copies and docs/commands.md say how to assign. Tests: assign a story,
   assign a part, refuse a story with no plan, and a second clone that fetches and sees the new
   order for the assignee.
3. `rounds[]` gains `seconds` {work, in_line, waiting_for_person, waiting_for_checks} for every
   round that is still recorded on its own. Owner decision 15 October (narrow): rounds that
   history compaction has already folded together keep only the folded total, and their
   `seconds` is null; keeping per-round times through compaction is a follow-up, not this part.
   Older rounds recorded before this release keep `line` with `seconds: null`. Tests: a
   two-round fix shows both rounds; a compacted history shows null seconds for the folded rounds
   and real seconds for the rest; an adopted older item shows null.
4. `known_issues` lists item, file, line, title, gain, work, harm, `kept` (lived with or
   follow-up) and reason. Source: the item's persisted known list on the default branch; for
   items merged before that list existed, the review history on the pull request's original head
   (`refs/pull/<n>/head`, the same source backfill.py already reads). Findings from before scores
   show null scores. Tests: a Gain 3 follow-up and a lived-with finding appear; a squash-merged
   item from before the list shows its kept findings from the pull request head; a dismissed
   finding with no keep does not appear.
5. A release is a tag reachable from the default branch whose name looks like a version
   (`v1.2.3` or `1.2.3`, with an optional suffix); Forge's own `forge-start/` and `forge-plan/`
   tags and any other names are never releases. A release's date is its GitHub release's
   publish date, else its annotated tag date, else unknown; a commit date is never used.
   Membership: a finished part or fix belongs to the earliest release tag whose commit contains
   its merge commit; that tag is its `released_in`. A story is released in the tag that carries
   its last part; until then its `released_in` is null even when some parts are released. Shape:
   `releases: [{tag, date, items: [ids]}]` oldest first, and `released_in` on each row.
   Finished work with no `released_in` is the next release. Plan-to-release time needs a known
   date and is otherwise unknown. No release tags: `releases: []` and `release_note: "no
   releases tagged"`. Tests, through `forge board --json`: a repo with two version tags plus
   Forge's bookkeeping tags; a story whose parts land in two releases; a lightweight tag with
   and without a GitHub release; a repo with no tags.
6. The upgrade's last step (beside today's time-history rebuild in backfill.py) fills logins from
   pull request authors and mergers, owners from the Developer column, known issues from the
   sources in item 4, and releases by the rule in item 5. It is idempotent and quiet without
   GitHub; the next close retries. Tests: upgrade the adopted fixture and read the board; run it
   twice.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| OWNERS | GitHub usernames everywhere | login fields beside every person field, `viewer`, trends by login | 1 | src/forge/board_facts.py, src/forge/board_trends.py, src/forge/board.py | tests/test_board_logins.py | | no | |
| ROUNDS | Time per round | `rounds[].seconds`, kept through compaction | 3 | src/forge/time_records.py | tests/test_round_seconds.py | | no | |
| ASSIGN | Give a story to a developer | `forge assign`, the `Owner:` line, publication to the story branch, next-step order, `owner` in the board JSON, guide and command docs | 2 | src/forge/story.py, src/forge/task.py, src/forge/cli.py, src/forge/nextstep.py, src/forge/board.py, src/forge/templates/skill.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md, docs/commands.md | tests/test_assign.py | OWNERS | no | |
| KNOWN | Known issues list | `known_issues` in the board JSON from the persisted list and pull request heads | 4 | src/forge/known_issues.py, src/forge/board.py | tests/test_known_issues.py | ASSIGN | no | |
| RELEASES | Releases from tags | `releases`, `released_in`, `release_note` in the board JSON | 5 | src/forge/releases.py, src/forge/board.py | tests/test_releases.py | KNOWN | no | |
| BACKFILL | Past work filled in on upgrade | the upgrade fills owners, known issues and releases | 6 | src/forge/backfill.py | tests/test_board_backfill_people.py | RELEASES | no | |

New moving parts: none

## Notes

- Follow-up (owner, 15 October): keep each round's seconds through history compaction.

- Tokens and cost stay out of this story; FORGE-COST-1 owns them, and the board hides them until then.
- Teammates' live runs stay local to each laptop; the Mainline team board shares them later.
