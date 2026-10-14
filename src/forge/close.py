"""forge close: close a task or fix by the close rule.

Bring the default branch in, push and open the pull request so CI runs during review. Commit and
publish the result, then wait for the checks forge.toml names on exactly that pushed head.
Nothing is committed after the checks: GitHub holds when they finished. A human merges.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from forge import __version__, checks, codex, githooks, init, repo, review, score, spotted, story, sync, task, time_records

REFUSALS = {
    "not_started": ("Forge has not started {item} in any worktree of this repo.", "forge next"),
    "no_checks": ("forge.toml names no checks for close to wait for.", "forge doctor"),
    "conflict": ("Merging {default} into {branch} conflicts in {files}.",
                 "git -C {path} merge origin/{default}, follow Keeping work moving in "
                 ".codex/skills/forge/SKILL.md or .claude/skills/forge/SKILL.md and commit, "
                 "then forge close {item}"),
    "merge_failed": ("Merging {default} into {branch} failed; the merge was aborted: {problem}",
                     "forge close {item}"),
    "replay_conflict": ("Replaying this fix's own commits onto {default} conflicts in {files}.",
                        "in {path}, run git rebase --rebase-merges=rebase-cousins --onto origin/{default} {base}, "
                        "resolve the conflicts and run git rebase --continue, preserve any earlier "
                        "merge edits, publish with git push --force-with-lease=refs/heads/{branch}:{lease} "
                        "origin {branch}, then forge close {item}"),
    "replay_remote": ("The remote branch has commits this checkout does not have, so Forge left it alone.",
                      "fetch and reconcile {branch}, then forge close {item}"),
    "replay_push": ("Git refused the replayed push, so Forge restored the original commits in this checkout.",
                    "check the remote branch and reconcile {branch}, then forge close {item}"),
    "bad_dismiss": ("Each --dismiss needs a finding number from the latest review and its own "
                    "--because that starts with the file:line proving that finding wrong.",
                    'forge close {item} --dismiss <n> --because "<file:line> <reason>"'),
    "stale_dismiss": ("The branch changed since the review those finding numbers came from.",
                      "forge close {item}"),
    "no_such_line": ("{where} is not a line of the reviewed commit, so it can't prove a finding "
                     "wrong.", 'forge close {item} --dismiss <n> --because "<file:line> <reason>"'),
    "no_such_base_line": ("{where} is not a line of the base commit, so it can't prove a finding "
                          "wrong.", 'forge close {item} --dismiss <n> --because "<file:line> <reason>"'),
    "blocked": ("The review left serious findings open: {findings}.",
                'forge work {item}, or forge close {item} --dismiss <n> --because '
                '"<file:line> <reason>"'),
    "hotspot": ("Review round {round} of {item} still finds serious problems in {file}, which an "
                "earlier round flagged too, so Forge stops sending the worker back. {question}",
                'forge close {item} --resolve <narrow|split|accept> --reason "<human\'s choice>"'),
    "bad_choice": ("Record the human's choice only on a stopped review loop, with a non-empty "
                   "--reason and no finding dismissals.",
                   'forge close {item} --resolve <narrow|split|accept> --reason "<human\'s choice>"'),
    "stuck": ("The worker can't get past the same problem, so Forge stopped sending it back. "
              "Ask the human:\n{question}",
              'forge close {item} --resolve <switch|same|narrow|split> --reason "<human\'s choice>"'),
    "chosen": ("The owner's choice is recorded; the worker's next round follows it.", "forge work {item}"),
    "unsynced": ("This {kind} changes Forge's version, but {files} {verb} what forge sync writes "
                 "for it.", "forge sync in {path}, commit what it wrote, then forge close {item}"),
    "unsynced_forge": ("This {kind} pins Forge {pinned}, but Forge {installed} is running close, "
                       "so it can't tell whether the {kind}'s files are what {pinned} writes.",
                       "uv tool install git+https://github.com/knacklabs/symphony-forge@{pinned}, "
                       "then forge close {item}"),
    "tests_failed": ("`{command}` failed on this machine; the "
                     "next worker round gets its output.", "forge work {item}"),
    "question": ("The worker is waiting for an answer:\n{question}",
                 'forge work {item} --note "<answer>"'),
    "merge_switch": ("The merge switch must change only forge.toml's top-level merge setting to agent; "
                     "it contains another change.",
                     "the repo owner removes the extra change, then forge close {item}"),
}
BEGIN, END = "<!-- forge:begin -->", "<!-- forge:end -->"
# forge merge enable's fix is known by these; only the repo owner merges it.
WHY, DONE = "Let the agent merge this repo's ready pull requests.", 'The default branch\'s forge.toml sets merge = "agent".'


def close(args: argparse.Namespace) -> int:
    from forge.merge import ENABLE

    item = args.item
    top = _worktree(item)
    state, cfg = repo.read_state(item, top) or {}, repo.config(top)
    switch = (item == ENABLE and state.get("kind") == "fix" and
              (state.get("why"), state.get("done_when")) == (WHY, DONE))
    choice, reason = getattr(args, "resolve", None), getattr(args, "reason", None)
    continued = (os.environ.pop("FORGE_CLOSE_ACCEPTED", "") == "1" and choice == "accept"
                 and reason and (state.get("stop") or {}).get("choice") == choice
                 and state["stop"].get("reason") == reason.strip())
    if choice or reason is not None:
        stuck = "question" in (state.get("stop") or {})
        if (not choice or not reason or not reason.strip() or
                not state.get("stop") or (state["stop"].get("choice") and not continued
                                          and state["stop"].get("by") != "default") or
                args.dismiss or args.because or
                (choice == "accept" if stuck else choice in ("switch", "same"))):
            repo.refuse((REFUSALS["bad_choice"][0], REFUSALS["stuck"][1]) if stuck
                        else REFUSALS["bad_choice"], item=item)
        if not continued:
            if choice == "switch":  # the next forge work runs this item on the other tool
                state["tool"] = "claude" if state["stop"]["tool"] == "codex" else "codex"
            if choice == "accept":
                result = state["review"]
                dismissed = {d["finding"] for d in result["dismissals"]}
                result["dismissals"].extend(
                    {"finding": number, "because": f"Human accepted the remaining finding: {reason}",
                     "accepted": True}
                    for number, _ in enumerate(result["findings"], 1) if number not in dismissed)
                result["status"] = "clean"
                score.remember(_known(top, item, state, f"origin/{repo.default_branch(top)}", result),
                               result, sum(step["step"] == "review" for step in state.get("steps", [])), {})
            if area := state["stop"].get("area") or state["stop"].get("file"):
                state["settled_areas"] = sorted({*state.get("settled_areas", []), area})
            defaulted = state["stop"].get("by") == "default"
            # the next worker round hears the owner's choice, including one reversing the default
            state["stop"].update(by="owner", worker_round=state.get("round"))
            state["stop"].update(choice=choice, reason=reason.strip())
            state["status"] = "waiting for checks" if choice == "accept" else "fixing"
            _save(top, item, state, f"Record the human's review loop choice: {choice}")
            if not defaulted:
                repo.record_event(top, item, "owner wait end", wait_id=state["stop"].get("wait_id"))
                _push(top, repo.current_branch(top))  # every machine's board sees the wait end
                _refresh_record(top, item, state)
        if choice in ("switch", "same"):
            print(f"Recorded the human's choice.\nNext: forge work {item}")
            return 0
        if choice != "accept":
            print(f"Recorded the human's choice. {choice.capitalize()} the part as agreed, "
                  f"then forge work {item}.")
            return 0
        if not continued:
            print("Recorded the human's choice.")
    had_stop = bool(state.get("stop"))
    if not switch:
        check_stop(item, state, top)
    question = codex.record(top, item).get("question")
    if question:
        repo.refuse(REFUSALS["question"], item=item, question=question)
    if not cfg["checks"]:
        repo.refuse(REFUSALS["no_checks"])
    dismissals = _dismissals(args, item)
    branch, default = repo.current_branch(top), repo.default_branch(top)
    pr = _pull_request(top, branch)
    migrating = state.get("kind") in ("migrate", "adopt")  # Forge isn't on the default branch yet
    if pr and pr["state"] == "MERGED":
        if migrating:  # forge-pr-check can run now that the default branch has Forge, so require it
            init.protect(top, default, cfg["checks"])
        _attach(top, item, branch)
        return _merged(top, item)

    previous = state.get("review") or {}
    legacy_diff = None
    if (previous and "branch_diff" not in previous and previous.get("changed") ==
            review.fingerprint("HEAD", item, top, state, f"origin/{default}")):
        legacy_diff = review.fingerprint(previous["commit"], item, top, state,
                                         f"origin/{default}", branch_diff=True)
    try:
        _merge_default(top, item, branch, default)
    except repo.Refused as error:
        if error.entry in (REFUSALS["conflict"], REFUSALS["replay_conflict"]):
            if not time_records.pending_merge_wait(top, item, (pr or {}).get("body") or "", reason="merge conflict"):
                repo.record_event(top, item, "owner wait start", reason="merge conflict")
            _push(top, branch)
            if pr:  # keep its review block; only the shared time record changes
                _refresh_record(top, item, state, pr)
            else:
                _publish(top, item, state, branch, default, pr,
                         {"status": "reviewing", "findings": [], "dismissals": []}, ("", ""))
        raise
    if pending := time_records.pending_merge_wait(top, item, (pr or {}).get("body") or "", reason="merge conflict"):
        repo.record_event(top, item, "owner wait end", wait_id=pending["id"])
        _refresh_record(top, item, state, pr)
    if "/" in item and (limit := state.get("part_line_limit")) and not state.get("allow_large"):
        excluded = [f":(exclude,glob){path}**" for path in review.BOOKKEEPING]
        excluded += [path.replace(":(glob)", ":(exclude,glob)") for path in repo.TEST_PATHS]
        stats = repo.git("diff", "--numstat", "-z", "--no-renames", f"origin/{default}...HEAD",
                         "--", ".", *excluded, cwd=top)
        lines = sum(int(number) for record in stats.split("\0")
                    for number in record.split("\t", 2)[:2] if number.isdigit())
        if lines > limit:
            stop = state.get("stop") or {}
            if stop.get("size") and not stop.get("choice"):
                repo.refuse(REFUSALS["stuck"], item=item, question=stop["question"])
            # A recorded answer holds until a worker round has run on it.
            if not stop.get("question") or stop.get("choice") and stop.get("worker_round") != state.get("round"):
                stuck_stop(top, item, state, cfg, f"It changes {lines} lines outside tests, "
                           f"over its limit of {limit}.", size=True)
            repo.refuse(REFUSALS["chosen"], item=item)  # the answer waits for its worker round
    if (state.get("stop") or {}).get("size"):  # the part fits again or is allowed: no question
        state.pop("stop")
    repo.resume_pin(top, cfg["version"], getattr(args, "land_rounds", None), accepted=choice == "accept",
                    before=getattr(args, "pin_before", None))
    if switch:
        files = set(repo.git("diff", "--name-only", "--no-renames", f"origin/{default}",
                             "HEAD", cwd=top).splitlines())
        if (files - {"forge.toml", repo.state_path(item)} or
                repo.git("diff", "--summary", f"origin/{default}", "HEAD", "--", "forge.toml", cwd=top)):
            repo.refuse(REFUSALS["merge_switch"], item=item)
        settings = tomllib.loads(repo.git("show", "HEAD:forge.toml", cwd=top))
        original = tomllib.loads(repo.git("show", f"origin/{default}:forge.toml", cwd=top))
        if (settings.pop("merge", None) != "agent" or
                settings != {key: value for key, value in original.items() if key != "merge"}):
            repo.refuse(REFUSALS["merge_switch"], item=item)
    for record in repo.git("diff", "--numstat", "-z", "--no-renames", "--diff-filter=A",
                           f"origin/{default}...HEAD", "--", "tests/", cwd=top).split("\0"):
        added, _, rest = record.partition("\t")
        _, _, path = rest.partition("\t")
        if added == "-" and path:
            print(f"Test fixture {path} is binary; replace it with plain text files.",
                  file=sys.stderr)
            return 1
    spotted.check(top, item)
    if not migrating:
        _synced(top, item)
    light = review.blocking_level(top, item, state, f"origin/{default}") == "P0"
    result = previous
    changed = review.fingerprint("HEAD", item, top, state, f"origin/{default}")
    branch_diff = review.fingerprint("HEAD", item, top, state, f"origin/{default}",
                                     branch_diff=True)
    fresh = choice == "accept" or result.get("branch_diff", legacy_diff) == branch_diff
    if switch:
        fresh = fresh and result.get("mechanical") is True and not review.blocking(result)
    if choice != "accept" and (review.blocking(result) or
                               any(d.get("accepted") for d in result.get("dismissals", []))):
        fresh = fresh and result.get("changed") == changed
    refreshed = fresh and (result.get("changed") != changed or
                           result.get("branch_diff") != branch_diff)
    if fresh:
        result.update(changed=changed, branch_diff=branch_diff)
    if dismissals and not fresh:
        repo.refuse(REFUSALS["stale_dismiss"] if result else REFUSALS["bad_dismiss"], item=item)
    round_number = sum(step["step"] == "review" for step in state.get("steps", []))
    choice_round = 0
    if (state.get("stop") or {}).get("choice"):
        # Earlier stops omitted the round or stored the attempted next review.
        path = repo.state_path(item)
        chosen = repo.git("log", "-1", "--first-parent", "--format=%H",
                          "-G", '"choice":', "--", path, cwd=top)
        at_choice = json.loads(repo.git("show", f"{chosen}:{path}", cwd=top))
        choice_round = sum(step["step"] == "review" for step in at_choice.get("steps", []))
    if (not switch and not fresh and round_number - choice_round >= 3 and
            review.blocked_rounds(top, item)[0] >= 3 and
            score.loop_stops(previous, _known(top, item, state, f"origin/{default}", previous), round_number)):
        file = review.blocking(previous)[0][1]["file"]
        state.update(stop={"file": file, "round": round_number + 1, "at": repo.now()}, status="hotspot")
        state["stop"]["wait_id"] = repo.record_event(top, item, "owner wait start", reason="review loop")
        _save(top, item, state, f"Review of {item} stopped after three blocked rounds")
        _push(top, branch)  # every machine's board sees the stop
        _refresh_record(top, item, state, pr)
        check_stop(item, state, top)
    evidence = (review.functional_check(top, f"origin/{default}"),
                review.proof_list(top, f"origin/{default}"))
    repo.record_event(top, item, "close result")  # a stuck worker counts failures once per close
    failed = 0
    if not fresh:
        if pending := time_records.pending_merge_wait(top, item, (pr or {}).get("body") or ""):
            repo.record_event(top, item, "owner wait end", wait_id=pending["id"])
        # read after the merge, which may change the command
        command = review.close_test(top, f"origin/{default}")
        _push(top, branch)
        pr = _publish(top, item, state, branch, default, pr,
                      {"status": "reviewing", "findings": [], "dismissals": []}, evidence)
        start, clock = repo.now(), time.monotonic()
        outcome = "failed"
        selected: dict[str, str] = {}
        # shortcut: an interrupted review waits for tests; add cancellation if immediate interruption is needed.
        with ThreadPoolExecutor(max_workers=1) as pool:
            testing = pool.submit(review.test_run, top, command, f"origin/{default}", always=switch)
            try:
                if switch:
                    head = repo.git("rev-parse", "HEAD", cwd=top)
                    identity = repo.record_event(top, item, "review result", commit=head, outcome="clean", findings=[],
                                                 review_round=review.round_number(top, item, state))
                    result = {"id": identity, "commit": head, "findings": [], "dismissals": [],
                              "changed": changed, "branch_diff": branch_diff, "mechanical": True}
                else:
                    result = review.run(top, item, state, cfg, f"origin/{default}", selected, previous,
                                        light=light, tested="Tests are running alongside this review; close waits for "
                                        f"both results before continuing. Command: `{command}`.")
                areas = _areas(top, result)
                result["dismissals"] += [
                    {"finding": number, "because": f"settled area: {where}"}
                    for number, finding in enumerate(result["findings"], 1)
                    if (where := areas[score.identity(finding["file"], finding["title"])])
                    in _settled_areas(state) and number not in
                    {d["finding"] for d in result["dismissals"]} and not (
                        score.holds(finding, result.get("blocking_level")) and finding.get("harm", 5) >= 3)]
                outcome = "blocked" if review.blocking(result) else "clean"
            finally:
                if outcome == "failed":
                    repo.record_event(top, item, "review result", outcome=outcome, findings=None,
                                      review_round=review.round_number(top, item, state))
                repo.record_timing(top, item, "review", start, clock, outcome, selected)
                failed, tested = testing.result()
                print(tested, flush=True)
                evidence = (evidence[0], review.proof_list(top, f"origin/{default}", tested))
                if failed:
                    state["tests"] = tested
                    if outcome == "failed":
                        state["status"] = "fixing"
                        _save(top, item, state, f"Tests of {item} failed")
                else:
                    state.pop("tests", None)
        repo.add_step(state, "review")
    elif state.get("tests"):
        command = review.close_test(top, f"origin/{default}")
        failed, tested = review.test_run(top, command, f"origin/{default}", always=switch)
        print(tested, flush=True)
        evidence = (evidence[0], review.proof_list(top, f"origin/{default}", tested))
        if failed:
            state["tests"] = tested
        else:
            state.pop("tests", None)
        state["status"] = "fixing" if failed or review.blocking(result) else "waiting for checks"
        _save(top, item, state, f"Tests of {item}: {'failed' if failed else 'passed'}")
    elif (command := review.close_test(top, f"origin/{default}")) and (
            (passed := review.passed_record(top, command)) and passed.exists()):
        print(review.SKIPPED.format(command=command), flush=True)
    for number, because in dismissals:
        if not 1 <= number <= len(result["findings"]):
            repo.refuse(REFUSALS["bad_dismiss"], item=item)
        from_base = _check_line(top, item, result["commit"], f"origin/{default}",
                                because.split()[0])
        result["dismissals"] = [d for d in result["dismissals"] if d["finding"] != number]
        result["dismissals"].append({"finding": number, "because": because,
                                     "from_base": from_base})
    serious = review.blocking(result)
    if not serious and not (state.get("stop") or {}).get("choice"):
        state.pop("stop", None)
    stopped = None
    round_number = sum(step["step"] == "review" for step in state.get("steps", []))
    if not fresh or dismissals:
        score.remember(_known(top, item, state, f"origin/{default}", previous), result, round_number,
                       {} if fresh else areas)
    if not fresh:
        flagged = set(state.get("flagged", []))
        files = {finding["file"] for _, finding in serious}
        crowded = score.crowded(state["known"], result, _settled_areas(state), areas) if serious else ""
        if crowded:
            stopped = {"file": crowded, "area": crowded, "proposed": score.move(state["known"], crowded)}
        elif (serious and round_number - choice_round >= 3 and
                score.loop_stops(result, state["known"], round_number)):
            default_files = set(repo.git("ls-tree", "-r", "-z", "--name-only",
                                         f"origin/{default}", cwd=top).split("\0"))
            candidates = sorted(file for file in files & flagged & default_files
                                if spotted._path(file))
            if candidates:
                stopped = {"file": candidates[0]}
        if stopped:
            stopped["at"] = repo.now()
            stopped["wait_id"] = repo.record_event(top, item, "owner wait start", reason="review loop")
            state["stop"] = stopped
        state["flagged"] = sorted(flagged | files)
    noted = (spotted.PATH,) if not switch and spotted.record(
        top, item, state, f"origin/{default}", result) else ()
    if not fresh or dismissals or refreshed or had_stop and not state.get("stop"):
        result["status"] = "blocked" if serious else "clean"
        state.update(review=result, status="hotspot" if stopped else
                     "fixing" if serious or failed else "waiting for checks")
        message = f"Review of {item}: {result['status']}"
        if stopped:
            message += f"; {stopped['file']} keeps breaking"
        _save(top, item, state, message, *noted)
    elif noted:  # a reused clean review still records what the worker spotted
        _save(top, item, state, f"Review of {item}: {result['status']}", *noted)
    head = repo.git("rev-parse", "HEAD", cwd=top)
    _push(top, branch)
    pr = _publish(top, item, state, branch, default, pr, result, evidence)
    _attach(top, item, branch)

    print(f"Review: {result['status']}.", flush=True)
    for number, finding in serious:
        print(f"{number}. {finding['priority']} {finding['title']} "
              f"({finding['file']}:{finding['line']})\n{finding['body']}\n")
    advice = [(n, f) for n, f in enumerate(result["findings"], 1)
              if not score.holds(f, result.get("blocking_level"))]
    if advice:
        print("Advice that does not block the merge:")
        for number, finding in advice:
            print(f"{number}. {finding['priority']} {finding['title']} "
                  f"({finding['file']}:{finding['line']})\n{finding['body']}\n")
    if failed and not stopped:
        repo.refuse(REFUSALS["tests_failed"], command=command, item=item)
    if serious:
        if stopped:
            repo.refuse(REFUSALS["hotspot"], item=item, round=round_number,
                        question=review.stop_question(top, item, state), **stopped)
        repo.refuse(REFUSALS["blocked"], item=item, findings="; ".join(
            f"finding {n} ({f['title'].rstrip('.')})" for n, f in serious))
    # forge-pr-check runs from the base branch, which has no Forge until migrate's or adopt's PR merges.
    try:
        checks.wait(top, item, head, [name for name in cfg["checks"]
                                     if not (migrating and name == "forge-pr-check")],
                    branch=branch, progress=getattr(args, "wait_for_progress", False))
    finally:
        pr = _publish(top, item, state, branch, default, pr, result, evidence)
    if pr and pr.get("isDraft"):  # a blocked review left it a draft
        _gh(top, "pr", "ready", str(pr["number"]))
    merge = merger(top, state)
    path = repo.ready_path(item, top)
    path.parent.mkdir(parents=True, exist_ok=True)
    if merge == "human":
        pending = time_records.pending_merge_wait(top, item, (pr or {}).get("body") or "")
        if not pending:
            repo.record_event(top, item, "owner wait start", reason="merge", commit=head)
        _publish(top, item, state, branch, default, pr, result, evidence)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"commit": head, "review": "clean"}) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    _publish(top, item, state, branch, default, pr, result, evidence)
    if merge == "agent":
        print(f"Ready: {item} has a clean review and green checks.")
        print(f"Next: forge merge {item}")
    else:
        print(f"Ready: {item} has a clean review and green checks. A human merges its pull request.")
    return 0


def _settled_areas(state: dict[str, Any]) -> list[str]:
    return [*state.get("settled_areas", []), *[(state.get("stop") or {}).get("file")] * bool((state.get("stop") or {}).get("choice"))]


def _known(top: Path, item: str, state: dict[str, Any], base: str, previous: dict[str, Any]) -> list[Any]:
    """The item's known findings; an item reviewed before the list gets its saved rounds first."""
    if "known" not in state:
        state["known"] = []
        for number, old in enumerate(review._history(top, item, base, previous), 1):  # pyright: ignore[reportPrivateUsage]
            score.remember(state["known"], old, number, _areas(top, old))
    return state["known"]


def _areas(top: Path, result: dict[str, Any]) -> dict[tuple[str, str], str]:
    return {score.identity(f["file"], f["title"]): review.area(top, result["commit"], f["file"], f["line"])
            for f in result.get("findings", [])}


def _answer_by_default(top: Path, item: str, state: dict[str, Any]) -> None:
    """Record the repo's default choice, narrow, and start a follow-up fix for each open finding."""
    from forge import task  # close imports story, which imports task

    fixes = []
    result = state.get("review") or {}
    dismissed = {d["finding"] for d in result.get("dismissals", [])}
    for number, finding in enumerate(result.get("findings", []), 1):
        if number in dismissed:
            continue
        why = " ".join(f"Review finding left open by {item}: {finding['title'].rstrip('.')} "
                       f"({finding['file']}:{finding['line']}): {score.strip(finding.get('body', ''))}".split())
        done = " ".join(f"A review no longer finds: {finding['title']}".split())
        out, here = io.StringIO(), os.getcwd()
        try:  # fix start works in the current checkout: the follow-up stacks on this item
            os.chdir(top)
            with contextlib.redirect_stdout(out):
                task.fix_start(argparse.Namespace(why=why, done=done, slug=None))
        finally:
            os.chdir(here)
        fixes.append(re.search(r"Started fix (\S+)", out.getvalue())[1])
    state["stop"].update(choice="narrow", by="default", fixes=fixes, worker_round=state.get("round"),
                         reason="Nobody answered in 30 minutes; the repo's default narrows the part "
                                "to its Done-when lines and files each open finding as a follow-up fix")
    state["status"] = "fixing"
    _save(top, item, state, "Record the repo's default review loop choice: narrow")
    repo.record_event(top, item, "owner wait end", wait_id=state["stop"].get("wait_id"))
    print("Nobody answered the review loop stop in 30 minutes, so Forge recorded the repo's default "
          "choice: narrow the part to its Done-when lines. Follow-up fixes own the open findings: "
          f"{', '.join(fixes) or 'none'}. The owner can reverse it with "
          f'forge close {item} --resolve <narrow|split|accept> --reason "<their choice>".', flush=True)


def check_stop(item: str, state: dict[str, Any], top: Path | None = None) -> None:
    """A human choice, the repo's default after 30 minutes or a later clean review releases a
    review loop stop."""
    result = state.get("review") or {}
    if (result.get("status") == "clean" and not review.blocking(result) and
            not (state.get("stop") or {}).get("choice") and "question" not in state.get("stop", {})):
        state.pop("stop", None)
    if state.get("stop") and "question" in state["stop"]:
        if not state["stop"].get("choice") and not state["stop"].get("size"):
            repo.refuse(REFUSALS["stuck"], item=item, question=state["stop"]["question"])
        return
    if state.get("stop") and not state["stop"].get("choice"):
        top = top or _worktree(item)  # land passes no checkout
        from forge.nextstep import default_due  # nextstep imports close
        if default_due(top, state):
            _answer_by_default(top, item, state)
    if state.get("stop") and not state["stop"].get("choice"):
        repo.refuse(REFUSALS["hotspot"], item=item,
                    question=review.stop_question(_worktree(item), item, state),
                    **{"round": sum(step["step"] == "review" for step in state.get("steps", [])),
                       **state["stop"]})


def stuck_round(top: Path, item: str, state: dict[str, Any], cfg: dict[str, Any],
                findings: list[dict[str, Any]]) -> None:
    """At a round's start: stop when the last two rounds both left close's tests failing or one
    same finding open. A recorded choice buys exactly one more round."""
    stop = state.get("stop") or {}
    if "question" in stop and not stop.get("choice"):
        repo.refuse(REFUSALS["stuck"], item=item, question=stop["question"])
    keys = [f'the review finding "{f.get("title", "")}" in {f.get("file", "")}' for f in findings]
    keys += ["close's tests failing"] if state.get("tests") else []
    # Each failure counts the rounds in a row that left it; a cleared one drops out. It counts only
    # with both a new close and a worker round since the last count, so reruns count once.
    # ponytail: close events live on this machine; a round on another machine counts once more.
    stuck = state.get("stuck") or {}
    closed = next((e["id"] for e in reversed(time_records.read(top, "events"))
                   if e.get("item") == item and e.get("event") == "close result"), None)
    if stuck and (stuck.get("close") == closed or stuck.get("round") == state.get("round")):
        if "question" in stop:
            state.pop("stop")
        return
    before = stuck.get("keys") or {}
    counts = {key: before.get(key, 0) + 1 for key in keys}
    same = [key for key, count in counts.items() if count >= 2]
    if "question" in stop:
        state.pop("stop")
    elif same:
        stuck_stop(top, item, state, cfg, "\n".join(f"Two rounds in a row left {key}." for key in same))
    state["stuck"] = {"keys": counts, "head": repo.git("rev-parse", "HEAD", cwd=top), "close": closed,
                      "round": state.get("round")}


def stuck_stop(top: Path, item: str, state: dict[str, Any], cfg: dict[str, Any], what: str,
               size: bool = False) -> None:
    """Stop the item and refuse with a question the coordinator can ask the owner as it is."""
    title, _, delivers = _title(top, item, state)
    tool = state.get("tool") or state.get("worker") or repo.worker(cfg, "build", False)[0]
    since = (state.get("stuck") or {}).get("head") or f"origin/{repo.default_branch(top)}"
    tried = repo.git("log", "--first-parent", "--no-merges", "--format=%s", f"{since}..HEAD",
                     "--", ".", ":(exclude).factory", cwd=top).splitlines()
    other = "claude" if tool == "codex" else "codex"
    choices = [f"switch this item to {other.title()}", f"keep {tool.title()} for one more round",
               "or narrow or split it"]
    question = (f"{title} is stuck. It should deliver: {delivers}\n{what}\n"
                f"The worker tried: {'; '.join(dict.fromkeys(tried)) or 'no new commits'}.\n"
                f"Choose one: {'; '.join(choices)}.")
    state.update(stop={"question": question, "tool": tool, **({"size": True} if size else {})},
                 status="hotspot")
    state["stop"]["wait_id"] = repo.record_event(top, item, "owner wait start", reason="stuck")
    _save(top, item, state, f"{item} is stuck; Forge asks the owner")
    share_wait(top, item, state, push=True)
    repo.refuse(REFUSALS["stuck"], item=item, question=question)


def branch_pr(top: Path, state: dict[str, Any]) -> dict[str, Any] | None:
    """The item's open pull request, found on GitHub by its branch; None without one, without
    GitHub or when the branch was never pushed."""
    branch = state.get("branch") or repo.current_branch(top)
    if repo.run("git", "rev-parse", "-q", "--verify", f"refs/remotes/origin/{branch}", cwd=top).returncode:
        return None
    with contextlib.suppress(repo.Refused, subprocess.CalledProcessError, ValueError):
        pr = _pull_request(top, branch)
        return pr if pr and pr.get("state") == "OPEN" else None
    return None


def share_wait(top: Path, item: str, state: dict[str, Any], push: bool = False) -> None:
    """Forge just recorded a wait on a person: when the branch has a pull request, publish the
    record (pushing first when the wait lives in the committed state), so every machine's board
    sees the wait."""
    if pr := branch_pr(top, state):
        if push:
            _push(top, state.get("branch") or repo.current_branch(top))
        _refresh_record(top, item, state, pr)


def merger(top: Path, state: dict[str, Any]) -> str:
    """"human" for migrate, adopt and the merge switch's fix, else the repo's merge setting."""
    return "human" if state.get("kind") in ("migrate", "adopt") or state.get("why") == WHY else repo.merge_setting(top)


def _worktree(item: str) -> Path:
    """The checkout on the item's own branch: the one its state names. An earlier item's state
    reaches later branches through the default branch, so the file alone proves nothing."""
    for branch, tree in story.worktrees(repo.root()).items():
        state = repo.read_state(item, tree)
        if state and state.get("branch") == branch:
            return tree
    repo.refuse(REFUSALS["not_started"], item=item)


def _dismissals(args: argparse.Namespace, item: str) -> list[tuple[int, str]]:
    numbers, reasons = args.dismiss or [], args.because or []
    if len(numbers) != len(reasons) or not all(re.match(r"\S+:\d+\s+\S", r) for r in reasons):
        repo.refuse(REFUSALS["bad_dismiss"], item=item)
    return list(zip(numbers, reasons))


def _check_line(top: Path, item: str, commit: str, base: str, where: str) -> bool:
    """Use the base only when the branch deleted the cited file."""
    path, _, line = where.rpartition(":")
    from_base = path in repo.git("diff", "--name-only", "-z", "--diff-filter=D", "--no-renames",
                                 base, commit, "--", path, cwd=top).split("\0")
    shown = repo.run("git", "show", f"{base if from_base else commit}:{path}", cwd=top)
    if shown.returncode or not 1 <= int(line) <= len(shown.stdout.splitlines()):
        repo.refuse(REFUSALS["no_such_base_line" if from_base else "no_such_line"],
                    where=where, item=item)
    return from_base


def _merge_default(top: Path, item: str, branch: str, default: str) -> None:
    cfg = repo.config(top)
    repo.git("fetch", "-q", "origin", default, cwd=top)
    state = repo.read_state(item, top) or {}
    base, parent = str(state.get("base", "")), str(state.get("stacked_on", ""))
    target = f"origin/{default}"
    if (state.get("kind") == "fix" and repo.ITEM.fullmatch(parent)
            and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", base)
            and task._merged(target, parent, top)
            and repo.run("git", "merge-base", "--is-ancestor", base, "HEAD", cwd=top).returncode == 0
            and repo.run("git", "merge-base", "--is-ancestor", target, "HEAD", cwd=top).returncode):
        target = repo.git("rev-parse", target, cwd=top)
        original = repo.git("rev-parse", "HEAD", cwd=top)
        remote_ref = f"refs/heads/{branch}"
        remote = repo.git("ls-remote", "--heads", "origin", remote_ref, cwd=top)
        lease = remote.split()[0] if remote else ""
        if lease and repo.run("git", "merge-base", "--is-ancestor", lease, original, cwd=top).returncode:
            repo.refuse(REFUSALS["replay_remote"], branch=branch, item=item)
        # Rebase recreates merges but drops their hand edits; retain the fix's complete own diff.
        # Both parents exclude inherited commits and default updates already merged into the fix.
        baseline = repo.git("-c", "user.name=Forge", "-c", "user.email=forge@localhost",
                            "commit-tree", f"{target}^{{tree}}", "-p", base, "-p", target,
                            "-m", "Follow-up replay baseline", cwd=top)
        merged = repo.run("git", "merge-tree", "--write-tree", "--name-only", "-z",
                          "--no-messages", baseline, original, cwd=top)
        if merged.returncode not in (0, 1):
            merged.check_returncode()
        tree, *files = merged.stdout.rstrip("\0").split("\0")
        if merged.returncode:
            repo.refuse(REFUSALS["replay_conflict"], default=default, files=", ".join(files),
                        path=top, base=baseline, branch=branch, lease=lease, item=item)
        done = repo.run("git", "rebase", "--rebase-merges=rebase-cousins", "--onto", target,
                        baseline, cwd=top)
        if done.returncode:
            files = repo.git("diff", "--name-only", "--diff-filter=U", cwd=top).splitlines()
            repo.run("git", "rebase", "--abort", cwd=top)
            if not files:
                done.check_returncode()
            repo.refuse(REFUSALS["replay_conflict"], default=default, files=", ".join(files),
                        path=top, base=baseline, branch=branch, lease=lease, item=item)
        if repo.git("rev-parse", "HEAD^{tree}", cwd=top) != tree:
            proof = review.commit_paragraph(top, baseline, "Proof list:", original)
            repo.git("read-tree", "-u", "-m", tree, cwd=top)
            repo.git("commit", "-q", "-m", "Keep the follow-up's merge edits", "-m", proof, cwd=top)
        published = repo.run("git", "push", "-q", "-u", f"--force-with-lease={remote_ref}:{lease}",
                             "origin", branch, cwd=top)
        if published.returncode:
            repo.git("reset", "--keep", original, cwd=top)
            repo.refuse(REFUSALS["replay_push"], branch=branch, item=item)
        return
    done = repo.run("git", "merge", "-q", "--no-edit", f"origin/{default}", cwd=top)
    if done.returncode == 0:
        return
    files = repo.git("diff", "--name-only", "--diff-filter=U", cwd=top).splitlines()
    if not files:
        raise subprocess.CalledProcessError(done.returncode, ["git", "merge"], done.stdout,
                                            done.stderr)
    try:
        # Read sync's inventory from a clean tree: conflicted adapters may not even parse.
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder) / "default"
            repo.git("worktree", "add", "-q", "--detach", str(base), f"origin/{default}", cwd=top)
            try:
                # Forge's own code is never generated, and sync would parse its conflicted copy
                # when Forge runs from this checkout.
                ours = Path(__file__).resolve().parent
                generated = set() if any((top / path).resolve().is_relative_to(ours) for path in files) \
                    else {Path(path).as_posix() for path in sync.files(base, cfg)}
                if folder := githooks.husky_folder(base):
                    # Sync adds Forge's line, but the rest of these hooks belongs to the user.
                    generated.difference_update((folder.resolve() / hook).relative_to(base.resolve()).as_posix()
                                                for hook in ("pre-commit", "pre-push"))
                if cfg.get("repo") == "forge-source":
                    generated.add("docs/commands.md")
            finally:
                repo.git("worktree", "remove", "-f", str(base), cwd=top)
        if set(files) <= generated:
            repo.git("restore", f"--source=origin/{default}", "--staged", "--worktree", "--",
                     *files, cwd=top)
            release = "v" + repo._pin((top / "forge.toml").read_text(encoding="utf-8"))  # pyright: ignore[reportPrivateUsage]
            # Keep argv on one line for uv's Windows .cmd shims.
            script = ("from forge import repo, sync, githooks; "
                      "top = repo.root(); cfg = repo.config(top); folder = githooks.husky_folder(top); "
                      "keep = frozenset((folder.resolve() / hook).relative_to(top.resolve()).as_posix() "
                      "for hook in ('pre-commit', 'pre-push')) if folder else frozenset(); "
                      "sync.write(top, cfg, keep); "
                      "sync.write_file(top, 'docs/commands.md', sync.command_page()) "
                      "if cfg.get('repo') == 'forge-source' else None")
            if release != cfg["version"] and repo.VERSION.fullmatch(release):
                # Isolate Python imports too: the old checkout may have set PYTHONPATH.
                done = repo.run("uv", "run", "--isolated", "--no-project", "--with",
                                f"git+https://github.com/knacklabs/symphony-forge@{release}",
                                "--python", sys.executable, "python", "-I", "-c", script, cwd=top)
            else:
                package = json.dumps((top / "src" if cfg.get("repo") == "forge-source"
                                      else Path(__file__).resolve().parent.parent).as_posix())
                done = repo.run(sys.executable, "-c",
                                f"import sys; sys.path.insert(0, {package}); {script}", cwd=top)
            done.check_returncode()
            changed = [path for path in synced_changes(top) if path in generated]
            if changed:
                repo.git("add", "-A", "--", *changed, cwd=top)
            repo.git("commit", "-q", "--no-edit", cwd=top)
            return
    except Exception as error:
        repo.git("merge", "--abort", cwd=top)
        repo.refuse(REFUSALS["merge_failed"], default=default, branch=branch,
                    problem=(getattr(error, "stderr", "") or str(error)).strip(), item=item)
    repo.git("merge", "--abort", cwd=top)
    repo.refuse(REFUSALS["conflict"], default=default, branch=branch, files=", ".join(files),
                path=top, item=item)


def _synced(top: Path, item: str) -> None:
    """An upgrade is ready only once forge sync, run by the Forge it pins on a copy of the commit
    close pushes, changes and deletes nothing."""
    toml = story.show(top, "HEAD", "forge.toml") or ""
    pinned = repo._pin(toml)  # pyright: ignore[reportPrivateUsage]
    if pinned == repo.default_config(top)["version"].removeprefix("v"):
        return
    kind = "task" if "/" in item else "fix"
    if pinned != __version__:
        repo.refuse(REFUSALS["unsynced_forge"], kind=kind, pinned=f"v{pinned}",
                    installed=f"v{__version__}", item=item)
    # forge sync refuses a detached HEAD, so the throwaway checkout gets a throwaway branch.
    check, branch = Path(tempfile.mkdtemp()) / "sync", f"forge-synced-{os.getpid()}"
    repo.git("worktree", "add", "-q", "-b", branch, str(check), "HEAD", cwd=top)
    try:
        cfg = repo.config(check)
        sync.write(check, cfg)
        if cfg.get("repo") == "forge-source":
            sync.write_file(check, "docs/commands.md", sync.command_page())
        stale = synced_changes(check)
    finally:
        repo.git("worktree", "remove", "-f", str(check), cwd=top)
        repo.git("branch", "-D", branch, cwd=top)
    if stale:
        repo.refuse(REFUSALS["unsynced"], kind=kind, files=", ".join(stale),
                    verb="aren't" if len(stale) > 1 else "isn't", path=top, item=item)


def generated_fix_proof(done: str, evidence: str, item: str) -> str:
    """Generated fixes give their first review the same proof as a worker commit."""
    return (f"Proof list:\n- {done} Evidence: {evidence} "
            f"forge close {item} reports its test run result alongside the review result "
            "(including any skip reason).")


def synced_changes(top: Path) -> list[str]:
    """The files forge sync changed in a checkout, deletions included, without its new hook shims."""
    # No rename detection, so each entry is one plain path; a rename lists its deletion and addition.
    status = repo.run("git", "status", "--porcelain", "-z", "--no-renames", "--untracked-files=all",
                      cwd=top).stdout
    # sync's new hook shims are never committed, even when the hooks folder is in the checkout (husky).
    hooks = repo.git("rev-parse", "--git-path", "hooks/", cwd=top)
    return [entry[3:] for entry in status.split("\0") if entry and not entry.startswith(f"?? {hooks}")]


def _push(top: Path, branch: str) -> None:
    """Push the branch, retrying a failed push after 1, 2 and 4 seconds before giving up."""
    tags = repo.git("for-each-ref", "--format=%(refname)", "--merged", branch,
                    "refs/tags/forge-start/", cwd=top).splitlines()
    # Replay and copied plans can detach ownership history from the work branch.
    retained = repo.git("for-each-ref", "--format=%(refname)",
                        f"refs/tags/forge-start/{branch}", f"refs/tags/forge-plan/{branch}",
                        cwd=top).splitlines()
    tags = list(dict.fromkeys(tags + retained))
    for wait in (1, 2, 4, None):
        try:
            repo.git("push", "-q", "--atomic", "-u", "origin", branch, *tags, cwd=top)
            return
        except subprocess.CalledProcessError:
            if wait is None:
                raise
            time.sleep(wait)


def _save(top: Path, item: str, state: dict[str, Any], message: str, *paths: str) -> None:
    repo.write_state(item, state, top)
    repo.commit_state(message, repo.state_path(item), *paths, top=top)


def _gh(top: Path, *args: str) -> str:
    done = repo.run("gh", *args, cwd=top)
    if done.returncode:
        if done.stderr.strip() == repo.REFUSALS["no_github"][0]:
            repo.refuse(repo.REFUSALS["no_github"])
        raise subprocess.CalledProcessError(done.returncode, ["gh", *args], done.stdout,
                                            done.stderr)
    return done.stdout


def _draft(top: Path, *args: str) -> str:
    """A gh call that makes the pull request a draft. Where the repo allows no drafts (a private
    repo on GitHub's free plan) it says so and returns ""; any other refusal still fails."""
    try:
        return _gh(top, *args)
    except subprocess.CalledProcessError as error:
        if "draft pull requests are not supported" not in error.stderr.lower():
            raise
    print("This repo doesn't allow draft pull requests, so the pull request is ready for review; "
          "forge-pr-check still blocks its merge.")
    return ""


def _pull_request(top: Path, branch: str) -> dict[str, Any] | None:
    """The branch's open pull request, else its merged one, else None."""
    prs = json.loads(_gh(top, "pr", "list", "--head", branch, "--state", "all",
                         "--json", "number,state,body,isDraft"))
    return next((pr for state in ("OPEN", "MERGED") for pr in prs if pr.get("state") == state),
                None)


def _refresh_record(top: Path, item: str, state: dict[str, Any], pr: dict[str, Any] | None = None) -> str:
    pr = pr or _pull_request(top, state.get("branch") or repo.current_branch(top))
    if not pr:
        return ""
    body = _bounded_body(time_records.refresh_record(top, item, state, pr.get("body") or ""))
    if body != (pr.get("body") or ""):
        path = repo.forge_dir(top) / f"pr-body-{item.replace('/', '-')}.md"
        path.write_bytes(body.encode("utf-8"))
        _gh(top, "pr", "edit", str(pr["number"]), "--body-file", str(path))
    return body


def _publish(top: Path, item: str, state: dict[str, Any], branch: str, default: str,
             pr: dict[str, Any] | None, result: dict[str, Any],
             evidence: tuple[str, str]) -> dict[str, Any]:
    """Open the pull request, or refresh its contract and Forge's block. While the review is
    blocked or the local tests failed, the pull request is a draft."""
    check, proof = evidence
    history = time_records.how_it_went(top, item, state, (pr or {}).get("body") or "")
    block = _block(result, "\n\n".join(part for part in (history, proof, check) if part))
    draft = (result["status"] == "blocked" or bool(state.get("tests")) or
             (pr is None and result["status"] == "reviewing"))
    # The body goes through a file under .git/forge/: in argv it meets length limits, and a
    # multi-line argument can't pass through a Windows .cmd shim.
    body_file = repo.forge_dir(top) / f"pr-body-{item.replace('/', '-')}.md"
    if pr is None:
        title, why, summary = _title(top, item, state)
        notes = f"{state['notes']}\n\n" if state.get("notes") else ""  # migrate's plan
        body_file.write_bytes(_bounded_body(f"Why: {why}\nDone when: {summary}\n\n{notes}{block}\n").encode("utf-8"))
        create = ("--base", default, "--head", branch, "--title", title, "--body-file",
                  str(body_file))
        url = _draft(top, "pr", "create", "--draft", *create) if draft else ""
        is_draft = bool(url)
        url = url or _gh(top, "pr", "create", *create)
        print(f"Opened the pull request: {url.strip()}")
        number = int(url.strip().rsplit("/", 1)[1])
        repo.record_event(top, item, "pull request published", number=number)
        return {"number": number, "state": "OPEN",
                "body": body_file.read_text(encoding="utf-8"), "isDraft": is_draft}
    if not any(event.get("item") == item and event.get("event") == "pull request published"
               and event.get("number") == pr["number"] for event in time_records.read(top, "events")):
        repo.record_event(top, item, "pull request published", number=pr["number"])
    if draft and not pr.get("isDraft"):
        _draft(top, "pr", "ready", str(pr["number"]), "--undo")
    body = pr.get("body") or ""
    marked = re.compile(re.escape(BEGIN) + ".*?" + re.escape(END), re.S)
    new = (marked.sub(lambda _: block, body, count=1) if marked.search(body)
           else f"{body.rstrip()}\n\n{block}\n")
    _, _, summary = _title(top, item, state)
    new = re.sub(r"^Done when:.*$", lambda _: f"Done when: {summary}", new, count=1, flags=re.M)
    new = _bounded_body(new)
    if new != body:
        body_file.write_bytes(new.encode("utf-8"))
        _gh(top, "pr", "edit", str(pr["number"]), "--body-file", str(body_file))
        print("Updated the pull request's review block.")
    return {**pr, "body": new}


def _bounded_body(body: str) -> str:
    """Keep every GitHub write bounded, cutting duplicated and advisory detail before the contract."""
    limit = 65536  # UTF-8 bytes also bound GitHub's character count, including emoji.
    note = ("Some detail was shortened to fit GitHub's pull request limit. "
            "Git holds the full contract and proof; missing time evidence remains unknown.")
    if len(body.encode("utf-8")) <= limit:
        return body
    body = body.replace(note + "\n", "")
    body = re.sub(r"\n<!-- forge:history .*? -->", "", body)
    body = re.sub(r"(?m)^([^\n<]+)\n(?:\1\n)+", r"\1\n", body)
    budget = limit - len((note + "\n\n\n\n").encode("utf-8"))

    def clip(text: str, size: int) -> str:
        return text.encode("utf-8")[:max(0, size)].decode("utf-8", errors="ignore")

    def cut(match: re.Match[str]) -> str:
        text = match[0]
        excess = len(body.encode("utf-8")) - budget
        if excess <= 0:
            return text
        suffix = "\n</details>" if text.startswith("<details>") else ""
        return clip(text.removesuffix("</details>"), max(256, len(text.encode("utf-8")) - excess - len(suffix))) + suffix

    # These have full source evidence elsewhere, unlike the current contract and blocking status.
    for pattern in (r"<details>.*?</details>",
                    r"Proof list:.*?(?=\n(?:## |Functional check:|<!-- forge:)|\Z)",
                    r"Functional check:.*?(?=\n(?:## |Proof list:|<!-- forge:)|\Z)",
                    r"## How it went\n.*?(?=\n(?:Proof list:|Functional check:|<!-- forge:)|\Z)"):
        body = re.sub(pattern, cut, body, flags=re.S)

    # Keep completion metadata valid even when the owner supplied an exceptionally long outcome.
    def outcome(match: re.Match[str]) -> str:
        try:
            data = json.loads(match[1])
            return "Forge-story-done: " + json.dumps({"key": clip(data["key"], 512),
                                                       "outcome": clip(data["outcome"], 2048)})
        except (ValueError, KeyError, TypeError):
            return ""

    if len(body.encode("utf-8")) > budget:
        body = re.sub(r"^Forge-story-done: (\{.*\})$", outcome, body, flags=re.M)
    # Shorten long prose before source history; retain small owner notes and the review state.
    lines = body.splitlines(keepends=True)
    protected = ("Why:", "Done when:", "Review:", "The review found", "- Finding ")
    def prose(minimum: int) -> str:
        excess = sum(len(line.encode("utf-8")) for line in lines) - budget
        essential = {next((i for i, line in enumerate(lines) if line.startswith(prefix)), -1)
                     for prefix in protected[:4]}
        for index in sorted(range(len(lines)), key=lambda i: (
                lines[i].startswith(protected), -len(lines[i]) if minimum else i)):
            if excess <= 0:
                break
            line = lines[index]
            if line.rstrip() in (BEGIN, END) or line.startswith(("<!-- forge:time-record ", "Forge-story-done:")):
                continue
            keep = max(minimum, 64 if index in essential else 0)
            size = len(line.encode("utf-8"))
            if size > keep:
                target = max(keep, size - excess)
                lines[index] = clip(line, target - 1).rstrip() + "\n" if target else ""
                excess -= size - len(lines[index].encode("utf-8"))
        return "".join(lines)
    body = prose(256)

    marker = re.search(r"<!-- forge:time-record (\{.*?\}) -->", body, re.S)
    if marker and len(body.encode("utf-8")) > budget:
        record = time_records.from_body(body)
        before, after = body[:marker.start()], body[marker.end():]
        if record:
            record = {k: record.get(k) for k in ("events", "timings", "summary", "state", "ready", "rebuilt", "clean_reviews")}
            record["truncated"] = True
            while True:
                body = before + "<!-- forge:time-record " + json.dumps(record, separators=(",", ":")) + " -->" + after
                if len(body.encode("utf-8")) <= budget:
                    break
                rows = next((record[name] for name in ("events", "timings", "clean_reviews") if record.get(name)), None)
                if rows is None:
                    break
                del rows[:max(1, len(rows) // 4)]
        else:
            body = before + after
    lines = body.splitlines(keepends=True)
    body = prose(0)
    return body.rstrip() + "\n\n" + note + "\n"


def _block(result: dict[str, Any], check: str) -> str:
    """Forge's block in the pull request body: the open blocking findings plainly first, or one
    `Review: clean` line, then the dismissed and advisory findings folded away, then the worker's
    functional check from its commit message. Each finding is a bullet naming its --dismiss number
    in text, since GitHub renumbers an ordered list."""
    because = {d["finding"]: d for d in result["dismissals"]}
    blocking, rest, below = [], [], {"follow-up": [], "live with": []}
    for n, finding in enumerate(result["findings"], 1):
        outcome, scores = score.bar(score.of(finding)), score.of(finding)
        line = "Gain {}, Work {}, Harm {}".format(*scores) if scores else ""
        note = (f"dismissed because {because[n]['because']}"
                + (" (evidence from the base)" if because[n].get("from_base") else "")
                if n in because
                else "blocks the merge" if score.holds(finding, result.get("blocking_level"))
                else line if outcome in below
                else "advisory: " + " ".join(score.strip(finding.get("body", "")).split()))
        note += f"; {line}" if line and note != "blocks the merge" and note != line else ""
        (blocking if note == "blocks the merge" else below[outcome] if note.startswith("Gain ")
         else rest).append(f"- Finding {n} ({finding['priority']}): {finding['title']} "
                           f"({finding['file']}:{finding['line']}): {note}")
    if result["status"] == "reviewing":
        lines = [BEGIN, "Review: running; CI is running alongside it."]
    elif result["status"] == "blocked":
        lines = [BEGIN, "The review found serious problems.", "", *blocking]
    else:
        lines = [BEGIN, f"Review: clean, {len(because)} dismissed, {len(rest) - len(because) + sum(map(len, below.values()))} advice."]
    folded = [*rest, *[line for name, title in (("follow-up", "Follow-ups:"), ("live with", "Lived with:"))
                       if below[name] for line in ("", title, *below[name])]]
    folded = folded[1:] if folded[:1] == [""] else folded
    if folded:
        lines += ["", "<details>", "<summary>Dismissed and advisory findings</summary>", "", *folded,
                  "", "</details>"]
    return "\n".join([*lines, *(["", check] if check else []), END])


def _title(top: Path, item: str, state: dict[str, Any]) -> tuple[str, str, str]:
    """A short title and the why and done-when lines for a new pull request."""
    if "/" in item:
        _, doc, row = review.task(top, item)
        story_title = re.search(r"^# (.+)$", (top / "plans" / f"{item.split('/')[0]}.md").read_text(encoding="utf-8"), re.M)
        title = f"{story_title[1]}: {row.get('name', '')}" if story_title else row.get("name", "")
        why, summary = doc.get("Why", ""), row.get("what it delivers", "")
    else:
        why, summary = state.get("why", ""), state.get("done_when", "")
        # The first sentence: it ends at . ! or ? (and any closing quote or bracket) before a
        # space or the end, never in v1.2.10. The closing quote or bracket stays.
        first = re.split(r"[.!?]([\"')\]]?)(?=\s|$)", why, maxsplit=1)
        title = " ".join("".join(first[:2]).split())
        if len(title) > 70:  # a title the owner reads at a glance; no space: a hard cut
            title = title[:title.rfind(" ", 0, 71) if " " in title[:71] else 70].rstrip(",;:.!?")
    return " ".join(title.split()) or item, " ".join(why.split()), " ".join(summary.split())


def _attach(top: Path, item: str, branch: str) -> None:
    """Link the pull request in the item's recorded Codex chat; a failure never stops the close."""
    try:
        if codex.record(top, item).get("conversation") and not codex.attach(top, item, json.loads(
                _gh(top, "pr", "view", branch, "--json", "number,url,headRefName"))):
            raise RuntimeError(f"see {repo.work_log(top, item)}")
    except Exception as error:
        print(f"Could not link the pull request in its Codex chat "
              f"({(getattr(error, 'stderr', '') or str(error)).strip()}). The next forge close tries again.")


def _merged(top: Path, item: str) -> int:
    """A merged task needs no outcome step when its merge already recorded completion."""
    print(f"The pull request for {item} is merged.")
    key, _, name = item.partition("/")
    if name:
        if story.completed(top, key, story.landed_ref(top)).get("status") == "done":
            print("Next: forge next")
            return 0
        tasks = review.rows(review.task(top, item)[1].get("Tasks", ""))
        # ponytail: the newest 1,000 merged pull requests; search by branch when a repo has more.
        merged = {pr.get("headRefName") for pr in json.loads(_gh(
            top, "pr", "list", "--state", "merged", "--limit", "1000", "--json", "headRefName"))}
        if all(f"task/{key}-{row.get('id', '').strip('`')}" in merged for row in tasks):
            print(f'Every part of {key} is merged.\nNext: forge story done {key} "<outcome>"')
    return 0


COMMANDS = [{
    "words": "close", "run": "close", "changes_state": True,
    "help": "Close a task or fix by the close rule",
    "args": [(('item',), {}), (('--dismiss',), {"type": int, "action": "append", "metavar": "N"}),
             (('--because',), {"action": "append", "metavar": "FILE:LINE_REASON"}),
             (('--resolve',), {"choices": ["narrow", "split", "accept", "switch", "same"]}),
             (('--reason',), {"help": "The human's choice after a review loop stop"})],
    "position": 150,
    "listing": "| `forge close <item>` | Closes a task or fix by the close rule |",
}]
