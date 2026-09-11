---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-10)"
date: 2026-09-10
stories: []
---

# Closeout binds to the product diff, and closes with one command

## Context

Marking a task done took longer than building it. On WF-1 T2 the build was
clean at 08:05; closeout ran four and a half hours, six reviews, one grill,
a plan rewrite, a human re-approval and a Codex launch that changed nothing,
and was still open. Three small fix commits were the only product change.

The cause was what each closeout record was bound to. The review stamp
hashed the contract text, the brief text and every tracked file. The
delegate launch hashed the contract text and the brief. The task grill
hashed seven contract fields including write scope, required tests and
verify commands. The plan approval hashed the whole plan file, which carried
a hand-written copy of the contract. None of those is the code a reviewer
read. So a scope widening, a decision record, a test rename or a contract
re-record staled a review of unchanged code, and one contract edit orphaned
the launch, staled the stamp and staled the grill at once. The repair for a
scope stray (`amend-scope`) satisfied `stage done` but not the grill, which
read only the contract, so the coordinator re-recorded — and triggered the
cascade. Closing was also five commands in a fixed order, each recomputing
its own hash and refusing when it disagreed with the last.

## Decision

A closeout record binds to the thing it is about, and only that.

- The review stamp binds to `delta_id`, the hash of the branch's product
  diff from the stage base. A stamp recorded under the old rule that is
  still fresh by that rule is converted in place; a stale one stays stale.
- The delegate launch binds to the stage: a successful write launch inside
  it. The contract at launch time is evidence on the row, not a match.
- After stage start, the task grill binds to objective, acceptance criteria,
  plan contracts, `user_facing` and the plan. `write_scope`,
  `required_tests` and `verify_commands` are measurement fields with their
  own gate; a record made under the old rule is accepted while those fields
  have not moved. Before stage start nothing changes.
- One function, `product_excluded_prefixes`, says what is not product, for
  the measure, the review scope, the stamp and the grill alike.
- Every task plan carries a rendered `<!-- forge:contract -->` block —
  objective, criteria, effective scope with amendments, tests, verify,
  budget — re-rendered by the recorder, `task plan save` and `amend-scope`,
  and excluded from every plan digest. The cold reader is handed the
  recorded contract, authoritative over any copy in the plan. The delegate
  brief, the grill brief and the review brief read one effective scope.
- A contract re-record never touches the review stamp, and says which of
  the two kinds of field moved.
- `forge task close <id>`: clean tree, open items, `delta_id`, proof, review
  only if no stamp covers this delta, measure, stage done, seal. A done
  stage whose delta moved reopens itself. Re-running repeats only what the
  new delta needs. The explicit verbs stay.

## Consequences

Nothing previously reviewed becomes unreviewed: the set of paths a review
never judged is the same set the stamp now ignores, so the stamp stales on
exactly the changes the reviewer would have read and on nothing else. The
seal proves the bytes shipping are the bytes reviewed, which a tree hash
could not. Shipped work is never re-evaluated; in-flight records convert on
first check with no extra launch. What is given up: a scope widening no
longer costs a cold read of the plan — it costs a reason, a stage record
and a line in the review brief, which are the checks that can judge it.
