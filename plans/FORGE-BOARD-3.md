# The board's data knows who owns what, what shipped when, and what was left

6 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Every person on the board shows as their GitHub username, for past work too.
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

1. **Every person the board names shows as a GitHub username with their name beside it, for past and new work, in Forge's repo and in client repos.**
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

1. `forge board --json` gives every person field (`started_by`, `approved_by`, `merged_by`,
   `developer`, trends people) as `{login, name}`; `viewer` is the caller's GitHub login
   (`task.github_login`). Trends key people by login. When only a git name exists, `login` is
   null and the name stays. Tests: one board read in a new repo and one in the adopted fixture.
2. `forge assign <KEY|KEY/TASK> <login>` writes the Developer column of `plans/<KEY>.md` on the
   story branch (a whole story fills its unassigned parts; a story with no plan is refused and
   says to plan it first). The board JSON carries `owner` per story and part. `forge next` for
   that login offers those parts first. skill.md, both synced copies and docs/commands.md say how
   to assign. Tests: assign a story, assign a part, refuse a story with no plan, next order for
   the assignee.
3. `rounds[]` gains `seconds` {work, in_line, waiting_for_person, waiting_for_checks} from the
   intervals `time_records` already computes before it writes the sentence. Older rounds keep
   `line` with `seconds: null`. Tests: a two-round fix shows both rounds' seconds; an adopted
   older item shows null.
4. `forge board --json` gains `known_issues`: item, file, line, title, gain, work, harm,
   `kept` (lived with or follow-up) and reason, read from each item's review history on the
   default branch, not limited to 7 days. Findings from before scores show null scores. Tests:
   a Gain 3 follow-up and a lived-with finding appear; a dismissed finding with no keep does not.
5. `releases` [{tag, date, items}] from git tags reachable from the default branch, oldest first;
   each finished item gets `released_in`; a story's plan-to-release time comes from its approval
   date and its release tag date. No tags: `releases: []` and `release_note: "no releases
   tagged"`. Tests: a repo with two tags, a repo with none.
6. The upgrade's last step (beside today's time-history rebuild in backfill.py) fills logins from
   pull request authors and mergers, owners from the Developer column, known issues from review
   history and releases from tags. It is idempotent and quiet without GitHub; the next close
   retries. Tests: upgrade the adopted fixture and read the board; run it twice.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| OWNERS | GitHub usernames everywhere | `{login, name}` on every person field, `viewer`, trends by login; pins the board JSON wiring the other parts add to | 1 | src/forge/board_facts.py, src/forge/board.py, src/forge/board_trends.py | tests/test_board_logins.py | | no | |
| ASSIGN | Give a story to a developer | `forge assign`, `owner` in the JSON, next-step order for the assignee, guide and command docs | 2 | src/forge/story.py, src/forge/cli.py, src/forge/nextstep.py, src/forge/templates/skill.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md, docs/commands.md | tests/test_assign.py | OWNERS | no | |
| ROUNDS | Time per round | `rounds[].seconds` from the intervals | 3 | src/forge/time_records.py | tests/test_round_seconds.py | | no | |
| KNOWN | Known issues list | `known_issues` from review history | 4 | src/forge/known_issues.py | tests/test_known_issues.py | OWNERS | no | |
| RELEASES | Releases from tags | `releases`, `released_in`, plan-to-release time | 5 | src/forge/releases.py | tests/test_releases.py | OWNERS | no | |
| BACKFILL | Past work filled in on upgrade | the upgrade fills owners, known issues and releases | 6 | src/forge/backfill.py | tests/test_board_backfill_people.py | ASSIGN, KNOWN, RELEASES | no | |

New moving parts: none

## Notes

- Tokens and cost stay out of this story; FORGE-COST-1 owns them, and the board hides them until then.
- Teammates' live runs stay local to each laptop; the Mainline team board shares them later.
