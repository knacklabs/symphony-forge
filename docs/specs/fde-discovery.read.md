---
reader: codex (gpt-6-sol)
read_at: 2026-09-26T09:41:19+00:00
read_hash: 17286420154c9a30354df6c0380fd7c7d26aa29e
amended_hash: 89f7439cd413288a69795500bde7bffaebf9283c
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The office-hours requirement conflicts with an accepted decision.
   [Decision 0089](/docs/decisions/0089-fde-discovery-without-gstack.md:29) says gstack is removed and Forge discovery needs no third-party bundle. The spec requires `/office-hours` for new projects and big ideas. The decision needs an explicit amendment before approval.
   Disposition: keep the owner chose (2026-09-26) to record "gstack stays, only for office-hours" in this spec rather than a new decision; the Why says 0089 is narrowed, not replaced.

2. The interview routes overlap.
   The spec defines a “big new idea” as an ask no existing spec covers, which also describes many ordinary new stories. It does not say which route wins or when an ask is a fix, a story, or a new idea.
   Disposition: keep Discovery by size now names the routes: new project or unspecced ask goes to office-hours and wins; an ask a confirmed spec covers is a story; one correcting shipped behaviour is a fix.

3. The problem-card destination is unresolved.
   The existing [DISCOVERY.md template](/src/forge/templates/skeleton/docs/product/DISCOVERY.md:5) has `## Problem`, while the spec adds `## Problems`; the [Brief template](/src/forge/templates/skeleton/docs/product/BRIEF.md:5) has no problem field. Specify where existing problem text goes, where the card heading goes in the Brief, and the six field labels used by each card.
   Disposition: keep Problem cards now give the six field labels, put the card heading in the Brief's Summary, and keep old `## Problem` text in place, written into a card.

4. Reading context notes directly contradicts the current inbox rule.
   [docs/context/README.md](/docs/context/README.md:9) requires ledger registration and harvesting rather than ad hoc reading. The spec excludes `forge context mark` while telling the agent to read notes and populate cards. It must reconcile that workflow and its CI ledger check.
   Disposition: keep that inbox ledger is the old Forge's; the new Forge ships no docs/context ledger (its skeleton has none) and the old rules go away at the switch, now said in Problem cards.

5. The payback command lacks a reproducible input contract.
   Pin the flag names, units and rounding rule, valid confidence values, treatment of zero or negative inputs, and which missing values form a “partial set.” These choices can change the answer at the 3- and 12-month boundaries.
   Disposition: keep the payback rule now pins the flags, confidence values and default, the output lines, exact comparison with one-decimal display, zero value, and each refusal.

6. The option recommendation does not follow from the stated formula.
   Payback is defined for a build cost and value, but the agent must compare a full build, the smallest slice, and not building. State which options receive separate estimates and how “best payback” selects among them when not building has no payback quotient.
   Disposition: keep Options now say every building option gets its own payback answer, the fewest months wins among build or slice-first, ties go to the smaller build, else don't build or find out first.

7. The success-check lifecycle conflicts with the confirmed-body lock.
   [spec confirmation](/src/forge/records.py:145) stores a hash of the body, and [roadmap add](/src/forge/records.py:213) refuses a changed body. Appending `Result` changes that body, so the spec’s promise that a later story can be added needs a defined hash and reconfirmation rule.
   Disposition: keep After ship now says spec measure refuses a body changed since confirmation, then refreshes the confirmed hash, so roadmap add still accepts the spec.

8. “Every roadmap story is done” needs a source of truth.
   Roadmap items have a status, but [story done](/src/forge/story.py:170) records completion in story state without updating the roadmap item. Specify which record `forge next` reads, and whether a spec with no linked stories can become due.
   Disposition: keep After ship now reads story state on the default branch as landed, needs at least one roadmap item naming the spec, and says an unnamed spec is never due.

9. The spec’s success target measures a different question from its metric.
   It names FDE confidence in choosing what to build, but targets the share who say discovery *helped* them choose. Define one check-in question and how the result is assessed if fewer than five FDEs have used it by the check date.
   Disposition: cut the FDE-confidence half is gone (owner chose the problem-card share, 2026-09-26); the target now covers fewer than five specs.

10. The `.gstack/` deletion is a one-way step without a Risks entry.
    The spec says migration and the switch delete the store after retaining design docs. Name that loss, the preservation boundary, and the recovery source under Risks.
    Disposition: defer the .gstack deletion sentence is cut and deleting gstack stores in migration or the switch is now Out of scope.

11. Cut or defer: the impeccable requirement in this spec.
    The [current Forge skill](/src/forge/templates/skill.md:82) already makes impeccable the UI skill. The spec’s Why and success measure do not call for another UI-tool change.
    Disposition: defer the impeccable sentence is cut; Out of scope now says UI tooling is unchanged.
