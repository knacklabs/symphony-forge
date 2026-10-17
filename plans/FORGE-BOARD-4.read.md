---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-14T19:29:50.994336+00:00
seconds: 104.027
read_hash: b013e63568e4bfebfbc6bcf97a5ce0fbc6bcdb6e
round: 3
passed: yes
doc_seen: b013e63568e4bfebfbc6bcf97a5ce0fbc6bcdb6e
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: a2a6067542517548a676583f883692a41480fb38
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a13bd1-e3cc-7d53-b2b7-3bb59797c0fe
session:
blocked_rounds: 0
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Markdown rendering has no rule preventing repository content from executing with the board’s assignment authority.
   Raise: Security. `plans/FORGE-BOARD-4.md:69-74` puts Git-backed Markdown and assignment on the same server, but specifies neither inert rendering nor rejection of executable HTML and URLs. An HTML event handler in a plan could access the page’s token and assignment route. The formatting tests would pass. Existing rendering escapes repository text (`src/forge/board_visuals.py:288-295`).
   Gain 4, Work 2, Harm 4

   Disposition: cut
2. Blocking: Split: SERVER → transport and shell, then staged page cutover.
   Raise: Plan gap. `plans/FORGE-BOARD-4.md:98` requires SERVER to remove the old board once equivalent facts are served, but NOW, DETAIL and PAGES provide that content only after SERVER merges (`:86-89`). Removing the old HTML and rendering code also exceeds the approximately 400-line task limit before adding the server: `src/forge/board.html:207` and `src/forge/board_visuals.py:41-341` contain over 500 rendering lines.
   Gain 5, Work 2, Harm 3

   Disposition: cut
3. Blocking: Showing every item without scrolling in about 120 words contradicts the named client-sized fixture.
   Raise: Not done. `plans/FORGE-BOARD-4.md:32,67-68` requires all items, their story rail and figures to fit. `tests/board_fixture.py:57-61,92-101` supplies six building stories, six active parts and ten open fixes, alongside other planned work. Their titles already consume the word budget before owners, attention cards and controls. No bound or overflow rule reconciles these requirements.
   Gain 5, Work 2, Harm 3

   Disposition: cut
4. Blocking: Trap: command-lifetime caching and one-time fetching can make the live page permanently stale.
   Raise: Plan gap. `plans/FORGE-BOARD-4.md:57-61` specifies polling, but tests only initial JSON equality. The CLI retains `repo.command_cache()` throughout the command (`src/forge/cli.py:165-166`), including cached event reads (`src/forge/board.py:192-205`), while fetching currently happens once on entry (`:51-54`). No rule or test requires later polls to observe local changes or a teammate’s merged assignment.
   Gain 5, Work 3, Harm 3

   Disposition: cut
5. Blocking: SERVER does not pin the browser interfaces that the later tasks share.
   Raise: Plan gap. `plans/FORGE-BOARD-4.md:86-90` assigns separate modules to parallel builders without defining module entry points, snapshot updates, navigation, item selection, drawer opening or assignment-control integration. Those names cross shell, Now, detail and assignment ownership. SERVER names no shared stubs or test crossing those boundaries, as required by `.codex/skills/forge/SKILL.md:970-975`.
   Gain 4, Work 2, Harm 2

   Disposition: cut
6. Blocking: The plan-reading server contract has no owner.
   Raise: Plan gap. `plans/FORGE-BOARD-4.md:69-72` requires reading plans from Git, but DETAIL owns only browser files (`:88`); SERVER exposes only the page and `/board.json` (`:57-61`). Board rows contain no plan text (`src/forge/board.py:505-537`). The endpoint, response and Git-ref selection must be pinned before DETAIL can consume them; existing ref-selection behavior lives in `src/forge/story.py:529-560`.
   Gain 4, Work 2, Harm 3

   Disposition: cut
7. Advisory: Unproven: item 5: the specified data source cannot enumerate an older unreleased change.
   Raise: Not done. `plans/FORGE-BOARD-4.md:75` promises every item since the last tag, but `/board.json` matches the trimmed command output. `src/forge/board.py:230,254-257,803-818` removes older completions, with a six-week retention exception. In a repo releasing quarterly, an unreleased fix merged eight weeks ago can be absent. PAGES owns only JavaScript (`plans/FORGE-BOARD-4.md:89`), and its tags/no-tags tests do not require this case.
   Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

8. Blocking: Rendering a readable plan contradicts the blanket prohibition on command text.
   Raise: Not done. `plans/FORGE-BOARD-4.md:69-72` requires rendering the plan’s owner-facing text, while `:79-80` bans commands anywhere. This very plan contains `forge board` and `forge board --json` above the builders section (`:7,31,43`). Faithful rendering and the command scan cannot both pass.
   Gain 4, Work 1, Harm 2

   Disposition: cut
9. Blocking: The four figures and the Me filter have no defined meaning.
   Raise: Plan gap. `plans/FORGE-BOARD-4.md:12-13,64` names these features without identifying the figures or deciding whether “your items” means owner, assignee or starter. The design reference at `:99-100` supplies no path, address or embedded contract. These choices are materially different in the current data: `src/forge/board.py:505-509` distinguishes starter and developer, and `src/forge/board_facts.py:305-306` exposes several count groups.
   Gain 4, Work 2, Harm 2

   Disposition: cut
10. Blocking: The pipeline mapping omits the normal “Can start now” state.
    Raise: Functional. `plans/FORGE-BOARD-4.md:65-67` mixes item stages with dependency statuses but omits `Can start now`, which `src/forge/nextstep.py:578-579` emits for an available, unstarted part and `src/forge/board.py:655-657` exports. Such parts may have no item row until assigned (`:583-588`). The layout and word-count checks can pass while these planned cards disappear.
    Gain 3, Work 2, Harm 2

   Disposition: cut
11. Blocking: The assignment task can start before its required command exists.
    Raise: Plan gap. `plans/FORGE-BOARD-4.md:90` lists only NOW and DETAIL as prerequisites; the dependency on the previous story exists only in Notes (`:96-97`). `forge assign` is absent from current command registration (`src/forge/cli.py:24-35`) and belongs to the preceding story’s ASSIGN task. Task admission enforces the table’s After entries, not Notes (`src/forge/task.py:273-276`).
    Gain 4, Work 1, Harm 2

   Disposition: cut
12. Blocking: Unproven: item 4: assigning a story without a plan has no page-level refusal behavior.
    Raise: Test. The preceding story explicitly refuses this operation (`story/FORGE-BOARD-3:plans/FORGE-BOARD-3.md:60-65`). Roadmap-only stories are normal board entries (`src/forge/board_facts.py:303`). This plan specifies only successful assignment and reading the Developer column (`plans/FORGE-BOARD-4.md:73-74`), so its test passes if a refused assignment silently fails or appears successful.
    Gain 3, Work 2, Harm 2

   Disposition: cut
13. Blocking: Cut or defer: story-to-story nesting and lifetime figures.
    Raise: Plan gap. `plans/FORGE-BOARD-4.md:64,76` adds both beyond the promised story-with-parts view and weekly merged-work view (`:32,35`). Current dependency maps describe waits, not story parentage (`src/forge/board.py:656-675`), and trend facts cover six weeks rather than a lifetime (`src/forge/board_trends.py:45-46,88-98`). These additions require new behavior without a corresponding Done-when outcome.
    Gain 3, Work 1, Harm 2

   Disposition: cut
14. Blocking: The changed board command has no task updating the shipped coordinator guide.
    Raise: Gate. `AGENTS.md:97-99` requires a template or worker-brief update when command behavior changes. No task owns either file (`plans/FORGE-BOARD-4.md:86-90`). The shipped guide still describes a static HTML board with pinned sections and folding lists (`src/forge/templates/skill.md:277-283`), contradicting the proposed live application.
    Gain 3, Work 1, Harm 2

   Disposition: cut
15. Blocking: Unproven: item 6: an axe scan does not prove keyboard operation of the new interactions.
    Raise: Test. `plans/FORGE-BOARD-4.md:79-80` promises keyboard reachability but names only command scanning and axe. NOW, DETAIL and ASSIGNUI name no keyboard interaction check (`:87-90`). Mouse-click tests and axe can pass when a generic card has a click handler but cannot receive keyboard focus, leaving its detail and assignment controls unreachable.
    Gain 3, Work 2, Harm 2

   Disposition: cut

## Round 2

16. Blocking: The newly required visual comparison has no runnable reference.
    Raise: Plan gap. `plans/FORGE-BOARD-4.md:57-62` requires screenshots beside the approved artboards. Those files require `./support.js` (`docs/board-design/Manager.dc.html:6`), which is absent from the checkout. Their repeated content uses custom elements and non-executable `text/x-dc` scripts (`:41,146-147`). Opening these files produces unresolved templates rather than the approved screens, so builders cannot perform the specified comparison.
    Gain 4, Work 2, Harm 2

    Disposition: cut
17. Blocking: The new overflow counts leave hidden items without a defined way to open them.
    Raise: Functional. `plans/FORGE-BOARD-4.md:83-84` caps stages and stories but specifies only “and N more,” with no expansion or full-list behavior. The existing fixture already has ten working fixes (`tests/board_fixture.py:92-101`), so some disappear behind the cap. The new overflow-count test (`plans/FORGE-BOARD-4.md:89-91`) passes even when those items’ details are unreachable. The existing board makes overflow expandable (`src/forge/board_visuals.py:101-102`).
    Gain 4, Work 2, Harm 3

    Disposition: cut
18. Blocking: Returning assignment refusal messages verbatim conflicts with the command-text prohibition.
    Raise: Not done. `plans/FORGE-BOARD-4.md:99-100` requires returning and displaying the command’s refusal message, while `:108-111` prohibits commands everywhere outside the plan. Forge’s refusal text includes a `Next:` command (`src/forge/repo.py:65-71`), printed directly by the CLI (`src/forge/cli.py:167-169`). For example, the missing-tool refusal includes `forge doctor` (`src/forge/repo.py:36`). No rule defines a command-free presentation of that response.
    Gain 3, Work 1, Harm 2

    Disposition: cut
19. Blocking: Unproven: item 2: the newly specified figures have no numerical acceptance check.
    Raise: Test. `plans/FORGE-BOARD-4.md:85-91` introduces a recent-item median and waiting-for-person percentage, but its tests check layout, overflow, a startable card and word count. Existing timing facts expose several different quantities (`src/forge/time_records.py:355-360`); they do not prove these new aggregates. A page showing the arithmetic mean for durations of one, two and nine hours would pass every named check while displaying four hours instead of the two-hour median.
    Gain 3, Work 2, Harm 2

    Disposition: cut

## Round 3

No findings.
