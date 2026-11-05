# Security audit skill for client apps

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- Every client repo gets Cloudflare's security-audit skill, copied in at one fixed version. It has an MIT licence. (Source: your decision, 5 Nov 2026)
- The agent suggests a security check once before an app first takes real data. There are two such moments: when a sample-data prototype is about to stop being sample data, and at the Deploy on Mainline step. A person can also ask for the check at any time. Forge stores no new record and adds no command, so a new session can suggest it again. (Source: your decision, 5 Nov 2026; the two moments and the possible repeat are the planner's choice)
- The check never runs by itself. The agent asks first, because the check uses many model calls. It does not run on each pull request or on a fake-data demo. It does not block a merge or a launch. (Source: your decision, 5 Nov 2026)
- The check uses the skill's standard mode. A person can ask for a narrower check to spend less. The agent says before it starts that the cost is not yet measured on a client app. (Source: your decision, 5 Nov 2026; the narrower check is the skill's own option)
- The agent tells the owner each confirmed finding in plain words, and the owner decides what to do. Reports stay outside the repo, because they describe weaknesses. (Source: your decision, 5 Nov 2026)
- The agent says plainly what the check does not cover. It reads code and runs the app only in a safe sandbox, so it does not replace a penetration test. Parts it did not read stay named as not read. (Source: the trial on Forge, 5 Nov 2026)
- A new client repo gets all of this at `forge init`. An existing client repo gets it with `forge sync` after upgrade. Forge's own repo gets the same copy. (Source: the Forge review rules)

Design: none (this story adds a skill and guide text, and no screen)

## Why

A client app can begin to hold real customer data with no security check first. Forge's reviews look at one change at a time, and nothing checks the whole app before it goes live. The one trial on Forge's own code found no confirmed problem and read about half of what it planned, so the skill's value on a client app is not proven yet.

## Done when

1. **A new client repo has the skill at `forge init`, and an existing client repo has it after upgrade and `forge sync`.**
2. **The agent's guide says to suggest the check once at each of the two moments, and to run it when a person asks.**
3. **The guide says that the check never runs by itself, and never blocks a pull request, a merge or a launch, and Forge adds no check of its own for it.**
4. **The guide says that each confirmed finding goes to the owner in plain words, and that the report is written outside the repo.**

## Risks

Risks: none one-way. The part reverts with its pull request.

Trade-off: the skill adds about 350 KB to each of the two agent folders in every client repo, also in apps that never run it.

Trade-off: Forge keeps no record that the check was suggested, so a new session can suggest it again. The alternative is a new record, for a small annoyance.

Trade-off: the copy stays at one fixed version until a Forge release updates it, so the skill's later fixes do not arrive by themselves.

Trade-off: the suggestion is a written rule with no check, so an agent can forget it. Forge does not block on it, by your decision.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Upstream: https://github.com/cloudflare/security-audit-skill at commit c1c8a8c, folder `skills/security-audit`, MIT licence. Fetch that exact commit into `src/forge/templates/skills/security-audit/`. Copy its `LICENSE` beside `SKILL.md` and add a first-line source comment or `NOTICE.md` naming the repo and commit, as `simplified-technical-english` does. Leave out `validate-findings.test.cjs` and `validate-coverage-ledger.test.cjs`: clients do not need upstream's tests. Change no upstream text except where a line points to a file that is not shipped.

Ship it the way `src/forge/plain_english.py` ships its skill, to `.claude/skills/security-audit/` and `.codex/skills/security-audit/`. Reuse that code by generalising it if that is shorter than a second module. Add no setting, no command and no Forge state.

The two `.cjs` validators must not fail a client repo's `eslint .`: check how sync treats the impeccable skill's scripts, and treat these the same way. `doctor` and sync must not report the copies as hand-changed.

Guide text in `src/forge/templates/skill.md`, then `forge sync` so that `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` match. Put one short section near Coaching or under step 6 of The journey, with a "You can say" phrase such as "Check the app's security". The worker brief needs no change, because the coordinator asks and starts the check. `docs/guide.md` gets one line if it lists the shipped skills.

The output folder is the skill's default, `~/security-audit-skill/<repo>/run-<N>`, outside the repo. The guide says never to paste a report's weakness details into a pull request, an issue or a commit. A fix for a finding goes through the normal flow, in plain words.

### Done-when details

1. Extend `tests/test_fix_plain_english_skill.py`-style cases at the strongest boundary: run `forge init` on a new repo, and `forge sync` on a repo adopted on an earlier release, then check that both hosts' copies match the template and that the upstream test files are absent.
2, 3, 4. One test reads the guide through the synced `SKILL.md` and checks the rule's meaning in its paragraph: the two moments, ask first, no block, owner, outside the repo. Keep it to one test per rule, as `tests/test_rules.py` requires.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SKILL | Ship the skill and the guide rule | The fixed copy of the skill, its shipping to both hosts, the guide section, the synced copies and the tests for new and existing repos. | 1, 2, 3, 4 | `src/forge/templates/skills/security-audit/`, `src/forge/plain_english.py`, `src/forge/sync.py`, `src/forge/templates/skill.md`, `docs/guide.md`, `.claude/skills/`, `.codex/skills/`, `tests/test_security_audit_skill.py`, `tests/test_setup.py` | `tests/test_security_audit_skill.py` (`test_1`, `test_2`, new) | | no | |

New moving parts: none

## Notes

- **Scores (F x H >= 2 x C).** Shipping the skill with a written suggestion: F 2 (apps going live, weekly across clients), H 3 (one client's data leaking is a P0), C 2 (one more skill, and each run uses model calls). 6 >= 4. Kept.
- A Forge record that the check was suggested: F 2, H 1, C 2. 2 < 4. Cut.
- A refusal or a `forge next` line that waits for the check: cut by the owner's decision that it never blocks.
- **Trial on Forge, 5 Nov 2026.** Quick mode, reading only, 10 agents, about 9 minutes, no confirmed finding, 5 of 10 planned areas read. The first run on a real client app is the next proof, and it is not part of this story's Done-when.
- **Planner choices the owner did not make.** The two moments that count as "first takes real data". No record of the suggestion, so it can repeat in a new session. No change to the worker brief.
- No client repo is named in this story's code, tests, texts or commits.
