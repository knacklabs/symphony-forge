---
reader: codex (gpt-6.1-sol)
read_at: 2026-11-05T21:10:05.765147+00:00
seconds: 210.507
read_hash: 884ff6fd687b30f5fd792194459a17455e74c501
round: 1
passed: no
doc_seen: 884ff6fd687b30f5fd792194459a17455e74c501
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
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
