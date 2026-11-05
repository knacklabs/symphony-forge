---
reader: codex (gpt-6.1-sol)
read_at: 2026-11-05T21:14:05.850696+00:00
seconds: 78.928
read_hash: a4823ec6011b8a4a393e7c42a88ac42bc5ac0516
round: 2
passed: yes
doc_seen: a4823ec6011b8a4a393e7c42a88ac42bc5ac0516
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: bc0d108a8c22bf4afa837e38dc530d6bdb39e978
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1ad88-f507-7e01-b472-6e5a0a917f5f
session:
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
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Plan gap: the standalone renderer cannot call the shared Python checks as specified.

   Raise: Plan gap. `plans/FORGE-UISTANDARDS-1.md:118` pins Python functions for CANVAS to call, but defines no executable bridge from JavaScript. The renderer runs directly through Node (`src/forge/templates/design/support.js:3`); clients install Forge in an isolated tool environment (`docs/guide.md:17-20`). Finding the impeccable launcher supplies only the external checker, not Forge’s small checks. CHECKS must pin how the installed renderer invokes those shared checks.
   
   Case: normal use - an agent renders a canvas in an installed client repo.
   
   Gain 4, Work 2, Harm 2
   Disposition: cut

2. Blocking: Not done: item 2 writes images before checking whether the canvas overflows.

   Raise: Not done. `plans/FORGE-UISTANDARDS-1.md:83` says to write both screenshots and then check sideways scroll. This contradicts item 2’s promise that a failing canvas writes no images. The current renderer publishes each image immediately (`src/forge/templates/design/support.js:43`); its cleanup removes only the temporary folder. Keep output temporary until every screen passes, and test that an overflow failure leaves no published images.
   
   Case: normal use - a canvas passes the code checks but is wider than 375 pixels.
   
   Gain 4, Work 2, Harm 2
   Disposition: cut

3. Blocking: Not done: the shell check can pass without any search control.

   Raise: Not done. `plans/FORGE-UISTANDARDS-1.md:99` accepts `CommandDialog` or `CommandInput` anywhere in the app’s sources. Forge already ships their definitions in `src/forge/templates/starter/libs/shared/ui/src/components/ui/command.tsx:32` and `:63`; their presence proves nothing is rendered in the top bar. Also, the `<Sidebar` trigger never checks an ordinary HTML canvas built with `<aside>`. Pin the shell rule for both supported formats and test a shell without search while the shipped components remain present.
   
   Case: normal use - a client builds its shell using the shipped component library, or draws it as HTML.
   
   Gain 4, Work 2, Harm 2
   Disposition: cut

4. Blocking: Plan gap: the promised waiver has no contract for Forge’s small checks.

   Raise: Plan gap. `plans/FORGE-UISTANDARDS-1.md:38` and `:100` promise recovery through an inline impeccable comment or its ignore configuration. The vendored documentation assigns those suppressions to impeccable’s detector (`src/forge/templates/skills/impeccable/reference/hooks.md:15`, `:70`). It cannot suppress Forge’s separate spacing expressions, title parser or shell check. Their rule names, suppression handling and recovery test are unspecified; the cases at plan line 101 check only that waiver instructions appear.
   
   Case: normal use - an existing app hits a small-check false alarm and follows the refusal’s instructions.
   
   Gain 4, Work 2, Harm 2
   Disposition: cut

5. Advisory: the proposed cache does not survive a second close command.

   Raise: Plan gap. `plans/FORGE-UISTANDARDS-1.md:100` says `repo.command_fact` makes a second close of the same commit run nothing. That cache explicitly lasts only for the current command and is discarded afterward (`src/forge/repo.py:96-117`). Remove the cross-command promise; the named helper cannot provide it.
   
   Gain 2, Work 1, Harm 1
   Disposition: cut

## Round 2

6. Advisory: Plan gap: the new shipped-file inventory edit is outside every task’s scope.

   Raise: Plan gap. `plans/FORGE-UISTANDARDS-1.md:85` requires updating `tests/test_split_ships.py`, but CHECKS’s Scope and Tests cells at line 125 omit it. That test compares the complete shipped inventory (`tests/test_split_ships.py:68`), so delivering `ui-checks.js` without updating it fails the existing test. Assign the file and its test to CHECKS.
   
   Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

7. Advisory: the revised shell-fold rule rejects a correctly split sidebar.

   Raise: Functional. `plans/FORGE-UISTANDARDS-1.md:110` identifies the shell by `<SidebarProvider>` but requires `<Sidebar collapsible="icon">` in that same file. A layout rendering `<SidebarProvider><AppSidebar /></SidebarProvider>` fails even when `AppSidebar` correctly renders the folding sidebar. The shipped library separates these responsibilities: the provider accepts children (`src/forge/templates/starter/libs/shared/ui/src/components/ui/sidebar.tsx:56`), while `collapsible` belongs to Sidebar (`:154`). Unlike the search check, the fold check allows no imported component lookup. This is a new false refusal introduced by the shell-rule revision.
   
   Case: normal use - a client keeps its sidebar component separate from its layout.
   
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)
