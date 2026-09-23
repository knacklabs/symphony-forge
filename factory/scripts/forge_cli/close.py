"""forge task close -- one command from a built task to its open PR.

Closing a task was five commands run by hand in a fixed order -- review,
stage done, pr-ready, and after a post-seal fix `reopen --review-fix` then
the three again -- each recomputing its own fingerprint and refusing when it
disagreed with the one before. The coordinator spent turns reading "STALE",
"no launch bound", "not sealed" and deducing which command to re-run. On T2
that was 4.5 hours after a clean build.

`close` holds the stage lock from the first check to the seal, computes the
product delta once, and runs only what that delta still needs:

    clean tree -> open signals/windows -> delta_id -> proof
      -> review (only if no stamp covers this delta)
      -> measure (notes) -> stage done -> seal, push, PR

A stop names the step and the next action. Re-running after a fix repeats
only the steps the new delta needs. Nothing here is a new check: every
predicate is one `review`, `stage done` or `pr-ready` already ran.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from factory_lib import (
    load_json, repo_root, run_state_path,
    task_proof_problems, task_seal_shared_problems,
)

from .common import fail


def _stop(step: str, why: str, then: str) -> None:
    fail(f"close stopped at {step}: {why}\n  NEXT: {then}")


def _commit_task_proof(
        base: Path, story: str, task_id: str,
        proof: tuple[dict, dict, list[str]], *,
        proof_context: dict[str, object] | None = None,
) -> tuple[dict, dict, list[str]]:
    """Ship the proof close just recorded as its own commit, before the review.

    Every sealed-state reader reads a task's evidence at the commit the marker
    names. Evidence committed only with the marker sat one commit later: the
    re-bound tests.json was in the marker commit while the sealed product
    commit still held the old record, and the brief's re-rendered
    approved-input section could not be found. The coordinator used to commit
    evidence by hand before close, which hid this. Only the head moves here;
    the product tree the proof attested is checked again before its snapshot
    is replaced.
    """
    from factory_lib import task_evidence_path
    from .stages import product_tree_snapshot, protected_authority_snapshot
    from .tasks import _require_git

    rels = [
        path.relative_to(base).as_posix()
        for path in (task_evidence_path(base, story, task_id, name)
                     for name in ("verify.json", "tests.json"))
        if path.is_file()
    ]
    if not rels or not _require_git(
            base, "checking the task proof", "status", "--porcelain", "--", *rels):
        return proof
    _require_git(base, "staging the task proof", "add", "--", *rels)
    _require_git(base, "committing the task proof", "commit", "-q", "--only",
                 "-m", f"{story} {task_id}: task proof", "--", *rels)
    proof_tree, authority_tree, misses = proof
    after = product_tree_snapshot(base)
    if ({key: value for key, value in after.items() if key != "head"}
            != {key: value for key, value in proof_tree.items() if key != "head"}):
        fail(f"{task_id}: product tree moved while the task proof was committed")
    current_authority = protected_authority_snapshot(base)
    if current_authority != authority_tree:
        fail(f"{task_id}: protected Forge authority moved while the task proof "
             "was committed")
    if proof_context is not None:
        proof_context["product_tree"] = after
        proof_context["authority_tree"] = current_authority
    print(f"{task_id}: task proof committed ({after.get('head', '')[:12]}).")
    return after, current_authority, misses


def cmd_task_close(args: argparse.Namespace) -> None:
    from .review import _product_dirty, review_task
    from .stages import (
        _find, _finish_stage, _measure, _require_successful_launch,
        load_stages, reopen_stage_for_review_fix,
        run_stage_proof, selected_meaning_current, stamp_is_fresh, task_for,
    )
    from .tasks import seal_task
    from .delegate import delegation_exclusion, load_delegations

    base = Path(args.repo).resolve() if args.repo else repo_root()
    task_id = args.id
    task = task_for(base, task_id)
    if not task:
        fail(f"task {task_id} is not in the recorded decomposition")
    stage = _find(load_stages(base), task_id)
    if stage.get("status") not in ("active", "done"):
        _stop("stage", f"{task_id} has not started (stage "
              f"'{stage.get('status', 'pending')}')",
              f"`./forge stage start {task_id}` then `./forge delegate {task_id}`")

    # 1. A clean, committed product tree: the diff is what gets reviewed and
    #    sealed, so it must be a committed thing.
    dirty = _product_dirty(base)
    if dirty:
        _stop("tree", f"uncommitted product paths: {', '.join(dirty[:6])}"
              f"{' ...' if len(dirty) > 6 else ''}",
              "commit the product tree, then run close again")

    # 2. Anything the seal will refuse on, said now rather than last.
    state = load_json(run_state_path(base), default={})
    story = state.get("issue_key") or state.get("story") or ""
    problems = task_seal_shared_problems(base, story)
    if problems:
        _stop("open items", "; ".join(problems),
              "resolve them, then run close again")

    # 3. One identity for everything that follows.
    from .stages import stage_review_binding
    delta_id = stage_review_binding(base, stage, task)["delta_id"]

    # 4. A done stage whose diff moved (a post-seal fix) reopens itself. No
    #    separate verb, no hidden state flip.
    if stage.get("status") == "done":
        if stamp_is_fresh(base, stage, task):
            print(f"{task_id} is closed and its review covers the current diff.")
        else:
            reopen_stage_for_review_fix(base, task_id)
            stage = _find(load_stages(base), task_id)
            print(f"{task_id} reopened: the diff moved since it was sealed.")

    if stage.get("status") == "active":
        # These checks do not need proof or a review. Keep the final checks in
        # _finish_stage too: the stage or product can change while proof runs.
        load_delegations(base)
        measured = _measure(base, task_id, stage, task)
        if strays := measured.get("strays"):
            print(f"NOTE: {task_id} preflight measured paths outside write_scope: "
                  f"{', '.join(strays)}. This scope measurement is advisory.",
                  flush=True)
        _require_successful_launch(base, task_id, stage, task)

        # 5. Proof first. A failing required test is the cheapest stop there
        #    is, and finding it after a review turned every test fix into a
        #    review as well.
        proof_context: dict[str, object] = {}
        proof = _commit_task_proof(
            base, story, task_id,
            run_stage_proof(base, task_id, task, proof_context=proof_context),
            proof_context=proof_context,
        )

        # 6. Review only if no stamp covers THIS delta.
        if not stamp_is_fresh(base, stage, task):
            from factory_lib import selected_review_problems
            if story and not selected_review_problems(base, story, task_id, delta_id):
                from factory_lib import read_selected_review_generation
                from .stages import stamp_stage_review
                generation, _selection, generation_problems = read_selected_review_generation(
                    base, story, task_id, expected_delta_id=delta_id,
                )
                if (not generation_problems and isinstance(generation, dict)
                        and selected_meaning_current(base, stage, task, generation)):
                    with delegation_exclusion(base, task_id, kind="review-selection"):
                        if selected_review_problems(base, story, task_id, delta_id):
                            fail("selected review changed before its stamp could be restored")
                        generation, _selection, generation_problems = (
                            read_selected_review_generation(
                                base, story, task_id, expected_delta_id=delta_id,
                            )
                        )
                        if (not generation_problems and isinstance(generation, dict)
                                and selected_meaning_current(
                                    base, stage, task, generation,
                                )):
                            stamp_stage_review(
                                base, task_id,
                                lenses=("quality", "performance", "security"),
                            )
                            stage = _find(load_stages(base), task_id)
        if not stamp_is_fresh(base, stage, task):
            outcome = review_task(
                base, task_id, engine=getattr(args, "engine", "codex"),
                max_priority=getattr(args, "max_priority", "P3"),
                skill=getattr(args, "skill", None),
                proof_context=proof_context)
            if outcome["blocking"]:
                from .review import (
                    selected_generation, triage_workflow,
                    untriaged_actionable_blocking,
                )
                generation = selected_generation(base, story, task_id)
                left, total = untriaged_actionable_blocking(
                    base, story, task_id, generation=generation,
                )
                generation_id = str(
                    (generation or {}).get("generation_id") or "unknown"
                )
                if left:
                    then = (
                        f"triage every actionable finding before delegation: "
                        f"{triage_workflow(task_id)}. Then delegate the fixes "
                        f"(`./forge delegate {task_id}`), commit, and run close "
                        "again -- it reviews the whole task delta, base to tip, "
                        "and records one new generation"
                    )
                else:
                    then = (
                        "no host defect triage is required; implement the remaining "
                        "plan-contract acceptance blocker(s) via "
                        f"`./forge delegate {task_id}`, commit, and run close again "
                        "-- it reviews the whole task delta, base to tip, and records "
                        "one new generation"
                    )
                _stop(
                    "review",
                    f"selected generation {generation_id}: {outcome['blocking']} "
                    f"blocking finding(s); {left} of {total} actionable P0/P1 "
                    "defect finding(s) untriaged",
                    then,
                )
            stage = _find(load_stages(base), task_id)
        else:
            print(f"{task_id}: review stamp covers this diff ({delta_id[:12]}); "
                  "no review needed.")

        # 7. The task-owned proof bundle must be complete before the stage is
        #    made done. In particular, a user-facing task may run its functional
        #    check after the code review; close stops here, keeps the fresh stamp,
        #    and resumes without paying for another review after that proof is
        #    recorded.
        proof_problems = task_proof_problems(base, story, task, preseal=True)
        if proof_problems:
            _stop(
                "task proof", "; ".join(proof_problems),
                "record the missing or refreshed task-owned proof, then run close "
                "again -- an unchanged product delta keeps the current review",
            )

        # 8. Measure (notes), close. Same lock and same checks `stage done`
        #    holds; the proof is the one already run.
        class _Done:
            pass
        done_args = _Done()
        done_args.id = task_id
        done_args.repo = str(base)
        done_args.incomplete = ""
        with delegation_exclusion(base, task_id, kind="stage-close"):
            data = load_stages(base)
            current = _find(data, task_id)
            if current.get("status") != "active":
                fail(f"{task_id} changed state while close was waiting for "
                     "exclusive access; inspect `forge stage list` and retry.")
            _finish_stage(base, done_args, data, current, task_for(base, task_id),
                          proof=proof)

    # 9. Seal: marker, push, PR. Idempotent.
    seal_task(base, task_id)
