"""forge land: build a started task or fix, close it, run fix rounds, then merge or hand it off.

Each step is the existing command, run in-process, so a rerun continues from what the records show.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from functools import partial
from graphlib import TopologicalSorter
from pathlib import Path

from forge import board, checks, close, codex, machine, merge, nextstep, repo, review, score, spotted, story, task, worker

NEEDS_CHOICE = 3
REFUSALS = {
    "rerun": ("GitHub has not started the re-run of {check}.", "forge land {item}"),
    "one_or_all": ("Give one change or --all, not both and not neither.",
                   "forge land <item>, or forge land --all"),
    "one_run": ("A land run already works in this repo.", "wait for it to end, then forge land --all"),
    "note_all": ("Give one change with --note.", 'forge land <item> --note "<text>"'),
}
# A child of forge land --all: lend its queue place while close waits for CI.
QUEUED = "FORGE_LAND_QUEUED"
SLOT_WAIT, SLOT_RESUME = "::forge-land-wait::", "::forge-land-resume::"
# A change that left the train waits for the train to end before it merges, and a failed check of its
# own stops it for you instead of a fix round; a train member merges without its own close or re-run,
# because the train already tested it.
HELD, TRAIN, HOLD = "::forge-land-held::", "FORGE_LAND_TRAIN", "FORGE_LAND_HOLD"
LEFT = "FORGE_LAND_LEFT"
TRAIN_LIMIT = 5
ONE_BY_ONE = "so the ready changes merge one at a time, each with its own check."
UP_TO_DATE = ("Train: GitHub requires each pull request to be up to date with {default}, so a train cannot "
              "save checks. The ready changes merge one at a time.")
IN_CLOSE = ("reviewing", "fixing", "waiting for checks", "ready")
say = partial(print, flush=True)


def land(args: argparse.Namespace) -> int:
    if bool(args.item) == bool(getattr(args, "all", False)):
        repo.refuse(REFUSALS["one_or_all"])
    if args.item is None:
        if getattr(args, "note", None) is not None:
            repo.refuse(REFUSALS["note_all"])
        return _land_all()
    queued = os.environ.pop(QUEUED, "") == "1"
    member, hold = os.environ.pop(TRAIN, ""), os.environ.pop(HOLD, "") == "1"
    left = os.environ.pop(LEFT, "") == "1"
    item = args.item
    match = repo.ITEM.fullmatch(item)
    if not match or not (match["task"] or match["fix"]):
        repo.refuse(repo.REFUSALS["bad_item"], item=item)
    if item == merge.ENABLE:
        repo.refuse(merge.REFUSALS["owner_merges"], item=item)
    top = close._worktree(item)
    pin = repo.config(top)["version"]
    state, branch = repo.read_state(item, top) or {}, repo.current_branch(top)
    step = argparse.Namespace(item=item, dismiss=None, because=None, wait_for_progress=True,
                              note=getattr(args, "note", None))
    if queued and not member:  # a train member merges alone, with no queue place to lend
        step.check_slot = _check_slot
    rounds = 0
    conflict_retry = False
    review_retry = False
    try:
        if member:  # the train tested this change; its own close and re-run would only move its head
            step.train = member
            say(f"Merging {item}.")
            return merge.merge(step)
        close.check_stop(item, state, top)
        # A session round carries its count until ready or a recorded choice.
        saved = state.get("land") or {}
        rounds = int(os.environ.pop("FORGE_LAND_ROUNDS", "0")) or (
            saved.get("rounds", 0) if state.get("status") != "ready" and saved.get("stop") == state.get("stop")
            else 0)
        merged = _merged(top, branch)
        status = state.get("status", "started")
        start = repo.git("log", "-1", "--diff-filter=A", "--format=%H", "--",
                         repo.state_path(item), cwd=top)
        if _pending(top, item):  # a round is out with the session's subagent, whatever the status
            _problems(top, item)
            say(f"Next: run the subagent, forge handback {item}, then forge land {item}")
            return 0
        head = repo.git("rev-parse", "HEAD", cwd=top)
        # A completed session round handed back at this HEAD made no commit; it goes to close.
        handed = codex.record(top, item).get("native") or {}
        if not merged and state.get("kind") not in ("story-done", "migrate", "adopt") and (
                step.note is not None or (task.unbuilt_fix(item, state, top) or
                status == "started" and head == start or
                status == "working" and
                repo.git("log", "-1", "--format=%s", cwd=top) == f"{item} is working") and
                (handed.get("head"), handed.get("outcome")) != (head, "completed")):
            say(f"Building {item}.")
            step.land_rounds = rounds
            if _handed_out(step, top):
                return 0
        while True:
            repo.resume_pin(top, pin, rounds)
            step.land_rounds = rounds
            say(f"Closing {item}.")
            try:
                close.close(step)
            except repo.Refused as error:
                if error.entry is checks.REFUSALS["conflict"] and not conflict_retry:
                    conflict_retry = True
                    continue
                red = error.entry is checks.REFUSALS["red"]
                failing = worker._failing(branch) if red else []
                if (red and str(error).splitlines()[0] == checks.REFUSALS["red"][0].format(
                        names="forge-pr-check") and len(failing) == 1 and
                        failing[0][0] == "forge-pr-check" and any(
                            f"The committed review at the head of {branch} is {problem}" in failing[0][1]
                            for problem in ("missing.", "for a commit that isn't part of this branch.",
                                            "out of date:"))):
                    if review_retry:
                        raise repo.Refused(str(error).split("\nNext: ")[0], f"forge close {item}",
                                           error.code, error.entry) from None
                    review_retry = True
                    continue
                if red and _rerun(top, item, branch):
                    continue
                if red and left:  # it left a red train: its own check failed too, so it stops for you
                    raise
                what = ("the review's serious findings" if error.entry is close.REFUSALS["blocked"]
                        else "the failing tests" if error.entry is close.REFUSALS["tests_failed"]
                        # In a queue run, close's own check gate decides (a skipped required check
                        # fails there too); one change's fix rounds still use the worker's reading.
                        else "the failing checks" if red and (queued or failing) else "")
                if not what:
                    raise
                if queued and not (red and failing):
                    raise repo.Refused(str(error).split("\nNext: ")[0], f"forge land {item}",
                                       error.code, error.entry) from None
                if rounds >= 1:
                    rounds += 1  # this stop says why itself, so no stop line
                    say(f"Stopped after one fix round: {item} still has {what}.")
                    raise
                rounds += 1
                say(f"Fix round {rounds} of 1: the worker fixes {what}.")
                step.land_rounds = rounds
                if _handed_out(step, top):
                    return 0
                continue
            stacked_on = (repo.read_state(item, top) or {}).get("stacked_on")
            if stacked_on and not task._merged(
                    f"origin/{repo.default_branch(top)}", stacked_on, top):
                return 0
            # Merged since close looked: close again, so its merged path reports and tidies.
            if not merged and _merged(top, branch):
                merged = True
                continue
            if merged:  # Forge's tidy-up, where the agent merges and the item was recorded ready
                ready = repo.ready_path(item, top)
                receipt = json.loads(ready.read_text(encoding="utf-8")) if ready.is_file() else {}
                if receipt.get("review") != "clean" or receipt.get("tidied") or close.merger(top, state) != "agent":
                    return 0
            elif close.merger(top, state) != "agent":
                url = json.loads(close._gh(top, "pr", "view", branch, "--json", "url"))["url"]
                say(f"{item} is ready; a human merges its pull request: {url}")
                return 0
            if hold:
                _hold()
            say(f"Merging {item}.")
            try:
                return merge.merge(step)
            except repo.Refused as error:
                if error.entry is not checks.REFUSALS["conflict"] or conflict_retry:
                    raise
                conflict_retry = True
    except repo.Refused as error:
        _problems(top, item)
        if rounds <= 1 and error.entry not in (checks.REFUSALS["wait_ended"], merge.REFUSALS["train_moved"]):
            say(f"Stopped: {item} needs you.")
        if error.entry == close.REFUSALS["hotspot"]:
            problem, _, next_step = str(error).partition("\nNext: ")
            raise repo.Refused(problem, f"{next_step}, then forge land {item}",
                               NEEDS_CHOICE, error.entry) from None
        raise


def _handed_out(step: argparse.Namespace, top: Path) -> bool:
    """Run a round; a round handed to the session's subagent stops land until its hand-back."""
    worker.work(step)
    step.note = None
    if not _pending(top, step.item):
        return False
    _problems(top, step.item)
    say(f"Next: run the subagent, forge handback {step.item}, then forge land {step.item}")
    return True


def _pending(top: Path, item: str) -> bool:
    """A round handed to the session's subagent that its session still holds."""
    pending = codex._json(codex._item_file(top, item, ".json", "Build")).get("pending") or {}
    return any(run["id"] == (pending.get("entry") or {}).get("id") for run in machine.entries())


def _problems(top: Path, item: str) -> None:
    """Show the coordinator the evidence that also goes into the worker's brief."""
    state = repo.read_state(item, top) or {}
    findings = score.open_findings(state.get("review") or {})
    _, failing = worker._fix_round(state)
    if findings:
        say("Open findings:")
        for finding in findings:
            say(f"- {finding.get('title', '')} ({finding.get('file', '')}:"
                f"{finding.get('line', '')}): {finding.get('body', '')}")
    if failing:
        say("Failing checks:")
        for name, tail in failing:
            say(f"- {name}\n{tail}")


def _rerun(top: Path, item: str, branch: str) -> bool:
    """Re-run the pull request's failed checks once per pushed head, when every failure is a job
    whose first attempt's log names none of the change's files. Laptop repos never wait for
    GitHub checks. Any gh call that fails means no re-run."""
    default = repo.default_branch(top)
    cfg = repo.config(top)
    marker = repo.forge_dir(top) / "reruns" / repo.git("rev-parse", "HEAD", cwd=top)
    if cfg["test_place"] != "ci" or marker.exists():
        return False
    listed = _listed(top, branch)
    if listed is None:
        return False
    failing = [check for check in listed if check.get("bucket") not in ("pass", "skipping")]
    # forge-pr-check verifies the review itself; replaying CI cannot repair its findings.
    if any(check.get("name", "") == "forge-pr-check" or check.get("name", "").startswith("forge-pr-check (")
           for check in failing):
        return False
    logs = _failed_logs(top, branch)
    if not logs or any(_attempt(top, run) != 1 for run in logs):
        return False
    changed = [path for path in repo.git("diff", "--name-only", "-z", "--no-renames",
                                         f"origin/{default}...HEAD", cwd=top).split("\0") if path]
    if _names(logs, changed):
        return False
    runs: dict[str, list[str]] = {}
    for check in failing:
        runs.setdefault(re.search(r"/runs/(\d+)/", check["link"])[1], []).append(check.get("name", "a check"))
    marker.parent.mkdir(exist_ok=True)
    marker.touch()
    for names in runs.values():
        for name in names:
            say(f"Re-running {name} once: its failure names none of this change's files and "
                "CI runs this repo's tests.")
    late = _restart(top, list(runs))
    if late == "gh":
        return False
    if late:
        repo.refuse(REFUSALS["rerun"], check=", ".join(runs[late]), item=item)
    return True


def _listed(top: Path, branch: str) -> list[dict] | None:
    """The pull request's checks. gh exits non-zero when a check fails, so read what it printed either way."""
    try:
        listed = json.loads(repo.run("gh", "pr", "checks", branch, "--json", "name,bucket,link",
                                     cwd=top).stdout)
    except ValueError:
        return None
    return listed if isinstance(listed, list) else None


def _own(check: dict, skip: set[int]) -> bool:
    """Forge's own review: its status, and the run of forge.yml's pull_request_target workflow."""
    run = re.search(r"/runs/(\d+)/", check.get("link") or "")
    return check.get("name", "").startswith("forge-pr-check") or (
        check.get("name") == "Review pull request" and bool(run) and int(run[1]) in skip)


def _failed_logs(top: Path, branch: str, skip: set[int] = frozenset()) -> dict[str, list[str]] | None:
    """Run id to the full failed-job logs of the checks that failed, leaving out Forge's own review (its
    status, and the "Review pull request" job of a run in skip). None when any other failing check is not
    a "fail" with a job link, or its log cannot be read."""
    listed = _listed(top, branch)
    if listed is None:
        return None
    runs: dict[str, list[str]] = {}
    for check in listed:
        if check.get("bucket") in ("pass", "skipping") or _own(check, skip):
            continue
        job = re.search(r"/runs/(\d+)/job/(\d+)", check.get("link") or "")
        if check.get("bucket") != "fail" or not job:
            return None
        log = repo.run("gh", "run", "view", "--job", job[2], "--log-failed", cwd=top)
        if log.returncode:
            return None
        runs.setdefault(job[1], []).append(log.stdout)
    return runs


def _names(logs: dict[str, list[str]], paths) -> bool:
    """Whether a failed log holds one of the paths, written with / or \\."""
    return any(path in text or path.replace("/", "\\") in text
               for texts in logs.values() for text in texts for path in paths)


def _restart(top: Path, runs: list[str]) -> str:
    """Run the failed jobs of each run again and wait for their second attempt. "" when they started,
    "gh" when GitHub refused, else the run that had not started in time."""
    for run in runs:
        if repo.run("gh", "run", "rerun", run, "--failed", cwd=top).returncode:
            return "gh"
    # ponytail: FORGE_CHECKS_WAIT is the wait seam, as in checks.wait (tests set 0 to look once).
    deadline = time.monotonic() + float(os.environ.get("FORGE_CHECKS_WAIT", "600"))
    for run in runs:
        while (_attempt(top, run) or 0) <= 1:
            left = deadline - time.monotonic()
            if left <= 0:
                return run
            time.sleep(min(15, left))
    return ""


def _attempt(top: Path, run: str) -> int | None:
    """The run's latest attempt number, or None when gh can't say."""
    done = repo.run("gh", "run", "view", run, "--json", "attempt", cwd=top)
    try:
        attempt = json.loads(done.stdout).get("attempt") if not done.returncode else None
    except (ValueError, AttributeError):
        return None
    return attempt if isinstance(attempt, int) else None


def _merged(top: Path, branch: str) -> bool:
    return (close._pull_request(top, branch) or {}).get("state") == "MERGED"


def _check_slot(waiting: bool) -> None:
    """Lend this child's place during CI, then wait for the queue to return it."""
    say(SLOT_WAIT if waiting else SLOT_RESUME)
    if not waiting and not sys.stdin.readline():
        raise SystemExit("The land queue ended before this close could resume.")


def _hold() -> None:
    """Wait until the queue says the train ended: a merge now would move the default branch under its check."""
    say(HELD)
    if not sys.stdin.readline():
        raise SystemExit("The land queue ended before this merge could start.")


def _land_all() -> int:
    """One run per repo, from the main checkout: a merge may remove the worktree it started in."""
    top = machine.main_checkout(Path.cwd())
    os.chdir(top)
    # Never deleted: the system lets go of the lock when its run ends, however it ends.
    with (repo.forge_dir(top) / "land-all.lock").open("ab") as lock:
        if not codex._try_lock(lock):
            repo.refuse(REFUSALS["one_run"])
        try:
            return _queue(top)
        finally:
            codex._unlock(lock)


def _queue(top: Path) -> int:
    """Close and merge every change in close, bases before stacked fixes, otherwise oldest first.
    Run up to the agent places at once. A change
    not yet ready waits for an older one in the run that shares a file with it, unless a human
    merges: then nothing merges in the run, so nothing waits."""
    repo.git("fetch", "-q", "origin", cwd=top)
    default = repo.default_branch(top)
    hold = repo.merge_setting(top) == "agent"
    live = {run.get("item") for run in machine.entries() if run.get("repo_root") == top.as_posix()}
    changes, needs, stacked, branches = [], {}, {}, {}
    prs = {pr.get("headRefName"): pr for pr in board._machine_prs(top)}
    for branch, tree in story.worktrees(top).items():
        found = None if branch.startswith("story/") else task.branch_item(branch, tree)
        if not found:
            continue
        item, state = found
        state = nextstep.at_ref(top, item, state, prs.get(branch))
        if state.get("status") == "dropped":
            continue
        age = (int(repo.git("log", "-1", "--diff-filter=A", "--format=%ct", "--",
                            repo.state_path(item), cwd=tree) or 0), item)
        if state.get("stop"):  # close decides whether the owner recorded a choice
            try:
                close.check_stop(item, state, tree)
            except repo.Refused as error:
                problem, _, step = str(error).partition("\nNext: ")
                needs[item] = age, problem, step
                continue
            state = repo.read_state(item, tree) or state
        status = state.get("status")
        if status not in IN_CLOSE:
            say(f"Left out {item}: its builder is not done yet.")
        elif item in live or any(run.get("process") and codex._alive(run["process"]) is not False
                                 for run in board.active_runs(tree, item)):  # a live CI wait
            say(f"Left out {item}: another command works on it.")
        elif _merged(tree, branch):
            say(f"Left out {item}: its pull request already merged.")
        else:
            files = {path for path in repo.git("diff", "--name-only", "-z", "--no-renames",
                                               f"origin/{default}...HEAD", cwd=tree).split("\0")
                     if path and path != spotted.PATH and not path.startswith(".factory/")}
            pr = prs.get(branch)  # the board's readiness: its checks and pull request, as they are
            ready = nextstep._item_readiness(item, state, tree, board._checks(
                pr, repo.config(tree)["checks"])[0], pr=pr)[0] == "ready"
            changes.append((age, item, files, ready))
            stacked[item] = state.get("stacked_on")
            branches[item] = branch
    changes.sort()
    queued = {item: age for age, item, *_ in changes}
    dependencies = TopologicalSorter({
        item: [stacked[item]] if stacked[item] in queued else []
        for _, item, *_ in changes})
    dependencies.prepare()
    available = list(dependencies.get_ready())
    order = {}
    while available:
        item = min(available, key=queued.__getitem__)
        available.remove(item)
        order[item] = len(order)
        dependencies.done(item)
        available.extend(dependencies.get_ready())
    changes.sort(key=lambda change: order[change[1]])
    running: dict[str, tuple[subprocess.Popen, threading.Thread, list[str]]] = {}
    slots: dict[str, str] = {}
    finished, waiting, retried, merged, ready_prs = set(), set(), set(), [], []
    # Two to five ready changes get one combined check; the others close meanwhile and merge after it.
    # forge.yml runs the app's tests only where "tests" is a required check (prcheck.py's ci_tests), so
    # that is the check that must report the combined run; any other check name proves no test ran.
    plan = (_form_train(top, default, changes, branches, stacked)
            if hold and sum(change[3] for change in changes) > 1
            and repo.test_place(settings := repo.default_config(top)) == "ci"
            and "tests" in settings["checks"] else None)
    members = {member[0] for member in plan["members"]} if plan else set()
    held, notes, handled, last = set(), [], set(), []
    former = set(members)

    def ride() -> None:
        try:
            handled.update(_train(top, default, plan, merged, needs, notes, last))
            # One change left a red train: the rest, if two or more, are tested again from a fresh default branch.
            rest = [change for change in changes if change[1] in former - set(last)]
            if last and not handled and len(rest) > 1:
                repo.git("fetch", "-q", "origin", cwd=top)
                if again := _form_train(top, default, rest, branches, stacked):
                    handled.update(_train(top, default, again, merged, needs, notes, [], second=True))
        except Exception as error:  # a failed train must not stop the others
            say(f"Train: stopped: {str(error).splitlines()[0] if str(error) else type(error).__name__}, {ONE_BY_ONE}")
    train = threading.Thread(target=ride, daemon=True)

    def spawn(item: str) -> tuple[subprocess.Popen, threading.Thread, list[str]]:
        return _child(top, item, slots, {LEFT: "1"} if item in last else None,
                      held=held, hold=plan and train.is_alive())
    if plan:
        train.start()
    while len(finished) < len(changes):
        if plan and members and not train.is_alive():  # members it did not merge go one at a time
            finished.update(handled)
            members.clear()
        if not (plan and train.is_alive()):
            for item in list(held):
                held.discard(item)
                try:
                    running[item][0].stdin.write("go\n")
                    running[item][0].stdin.flush()
                except (KeyError, BrokenPipeError):  # it ended already; the result below owns it
                    pass
        # A returning child takes a free place before any new close starts.
        for item, (child, _, _) in running.items():
            if slots[item] == SLOT_RESUME and child.poll() is None and (
                    sum(value == "active" for value in slots.values()) < machine.half_cores()):
                slots[item] = "active"
                try:
                    child.stdin.write("resume\n")
                    child.stdin.flush()
                except BrokenPipeError:  # The child ended after poll; the result below owns it.
                    pass
        for index, (age, item, files, ready) in enumerate(changes):
            if item in running or item in finished or item in members:
                continue
            if item in last and not (former - set(last)) <= finished:  # it merges after every other former member
                continue
            parent = stacked[item]
            if parent and parent not in queued and not task._merged(f"origin/{default}", parent, top):
                needs[item] = (age, *needs[parent][1:]) if parent in needs else (
                    age, f"its base {parent} is not merged.", f"forge land {parent}")
                finished.add(item)
                continue
            if hold and parent in queued:
                if parent not in finished:
                    continue
                if parent in needs:
                    needs[item] = (age, *needs[parent][1:])
                    finished.add(item)
                    continue
            # A change not ready yet that shares a file with a train member waits for the train.
            other = next(((name, min(files & theirs)) for _, name, theirs, _ in changes
                          if name in members and files & theirs), None)
            if other and not ready:
                if item not in waiting:
                    say(f"{item} waits for {other[0]}: both change {other[1]}.")
                    waiting.add(item)
                continue
            # The hold first, so a held change says whom it waits for whatever the places are doing.
            older = next(((other, min(files & theirs)) for _, other, theirs, _ in changes[:index]
                          if other not in finished and files & theirs), None)
            if older and not ready and hold:
                if item not in waiting:
                    say(f"{item} waits for {older[0]}: both change {older[1]}.")
                    waiting.add(item)
                continue
            # Keep queue order: the next change starts once every started one has entered close.
            if sum(value == "active" for value in slots.values()) >= machine.half_cores() or any(
                    child.poll() is None and f"Closing {other}." not in lines
                    for other, (child, _, lines) in running.items()):
                continue
            say(f"Starting {item}.")
            running[item] = spawn(item)
        for age, item, *_ in changes:
            if item not in running or running[item][0].poll() is None:
                continue
            child, reader, lines = running.pop(item)
            reader.join()
            slots.pop(item)
            child.stdin.close()
            # Two closes fetching at the same moment can collide on git's lock of a shared ref.
            if child.returncode and item not in retried and any("cannot lock ref" in line for line in lines):
                retried.add(item)
                say(f"{item} met another change's git lock; starting it again once.")
                running[item] = spawn(item)
                continue
            finished.add(item)
            url = next((line.rsplit(": ", 1)[1] for line in lines
                        if line.startswith(f"{item} is ready; a human merges")), None)
            if child.returncode == 0 and url:
                ready_prs.append((order[item], f"{item} {url}"))
                say(f"{item} is ready for a human merge.")
            elif child.returncode == 0:
                merged.append(item)
                say(f"{item} merged.")
            else:
                needs[item] = _stop(item, age, lines, child.returncode)
                say(f"{item} stopped: {needs[item][1]}")
        time.sleep(0.5)
    stopped = sorted(needs, key=lambda item: needs[item][0])
    ready_prs = [line for _, line in sorted(ready_prs)]  # queue order: bases before stacked fixes
    say(f"Merged ({len(merged)}): {', '.join(merged) or 'none'} · Ready to merge ({len(ready_prs)}): "
        f"{', '.join(ready_prs) or 'none'} · Needs you ({len(stopped)}): {', '.join(stopped) or 'none'}")
    for item in stopped:
        say(f"- {item}: {needs[item][1]}\n  Next: {needs[item][2]}")
    for note in notes:
        say(note)
    return 1 if stopped else 0


def _stop(item: str, age: int, lines: list[str], code: int | None) -> tuple[int, str, str]:
    """What stopped a change: land's refusal, which follows its stop line and may run over several lines."""
    at = max((n for n, line in enumerate(lines) if line.startswith("Next: ")), default=0)
    said = max((n for n, line in enumerate(lines[:at]) if line == f"Stopped: {item} needs you."),
               default=at - 2) + 1
    return (age, "\n".join(lines[said:at]), lines[at][len("Next: "):]) if at else (
        age, f"its land run ended with exit code {code}.", f"forge land {item}")


def _tree(top: Path, one: str, two: str | None = None) -> str | None:
    """The tree of a commit, or of merging two commits; None when the merge clashes."""
    if two is None:
        return repo.git("rev-parse", f"{one}^{{tree}}", cwd=top)
    done = repo.run("git", "merge-tree", "--write-tree", one, two, cwd=top)
    return None if done.returncode else done.stdout.split()[0]


def _ruled(top: Path, paths: set[str]) -> bool:
    """Forge merges some files with its own rule, which GitHub does not have: a shared one is a clash."""
    if not paths:
        return False
    listed = repo.git("check-attr", "merge", "--", *sorted(paths), cwd=top).splitlines()
    return any(line.rsplit(": ", 1)[1] not in ("unspecified", "unset") for line in listed)


def _form_train(top: Path, default: str, changes: list, branches: dict[str, str],
                stacked: dict[str, str | None]) -> dict | None:
    """The ready changes that share one combined check, in queue order, and why each other ready change
    stays out. None when fewer than two fit, or when GitHub wants each pull request up to date."""
    base = repo.git("rev-parse", f"origin/{default}", cwd=top)
    tip, members, out, taken, trees = base, [], [], set(), [_tree(top, base)]
    for age, item, files, ready in changes:
        if not ready:
            continue
        head = repo.git("rev-parse", branches[item], cwd=top)
        fork = repo.git("merge-base", base, head, cwd=top)
        theirs = set(repo.git("diff", "--name-only", "--no-renames", "-z", fork, base, cwd=top).split("\0"))
        try:  # merge.py accepts only this record, which the item's own close wrote at this head
            receipt = json.loads(repo.ready_path(item, top).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            receipt = None
        merged = None
        if "forge.toml" in files:
            why = "it changes forge.toml"
        elif "forge.toml" in theirs:  # its checks gate would follow settings older than the ones read here
            why = "it was ready before the default branch changed forge.toml"
        elif not (isinstance(receipt, dict) and receipt.get("review") == "clean" and receipt.get("commit") == head):
            why = "it has no ready record from its own close"
        elif stacked[item] and not task._merged(f"origin/{default}", stacked[item], top):
            why = f"it builds on {stacked[item]}, which has not merged"
        elif _tree(top, base, head) is None or _ruled(top, files & theirs):
            why = "it clashes with the default branch"
        elif (merged := _tree(top, tip, head)) is None or _ruled(top, files & taken):
            why = "it clashes with a change already in the train"
        elif len(members) == TRAIN_LIMIT:
            why = "the train already has five changes"
        else:
            why = ""
        if why:
            out.append(f"{item} stays out of the train: {why}.")
            continue
        taken |= files
        tip = repo.git("commit-tree", merged, "-p", tip, "-p", head, "-m", "Forge merge train", cwd=top)
        trees.append(merged)
        members.append((item, branches[item], head, age, files))
    if len(members) < 2:
        for line in out:  # no train, but each change still hears why it stays out
            say(line)
        return None
    if _up_to_date_rule(top, default):
        say(UP_TO_DATE.format(default=default))
        return None
    return {"tip": tip, "members": members, "trees": trees, "out": out}


def _up_to_date_rule(top: Path, default: str) -> bool | None:
    """Whether GitHub requires each pull request to be up to date with the default branch, from the
    rules read and the older branch protection read; None when neither can be read."""
    asked = []
    for endpoint in (f"rules/branches/{default}", f"branches/{default}/protection/required_status_checks"):
        done = repo.run("gh", "api", f"repos/{{owner}}/{{repo}}/{endpoint}", cwd=top, timeout=60)
        try:
            found = json.loads(done.stdout) if done.returncode == 0 else None
        except ValueError:
            found = None
        if isinstance(found, list):
            asked.append(any(isinstance(rule, dict) and rule.get("type") == "required_status_checks"
                             and (rule.get("parameters") or {}).get("strict_required_status_checks_policy") is True
                             for rule in found))
        elif isinstance(found, dict):
            asked.append(found.get("strict") is True)
    return any(asked) if asked else None


def _red(top: Path, members: list, branch: str, tip: str, reran: bool, leave: bool) -> tuple[str, str]:
    """What a red combined check means, once every job has finished: ("rerun", "") after it ran the failed
    jobs again, ("leave", change) for the one change whose files the logs name, ("alone", why) when each
    change goes one at a time, and ("other", "") when the logs cannot be read."""
    own = {run["id"] for run in checks.own_runs(top, members[0][0], tip)}
    if not _settled(top, branch, own):
        return "alone", "the combined check did not finish"
    if reran:
        return "alone", "the combined check failed again"
    logs = _failed_logs(top, branch, own)
    if logs is None:
        return "other", ""
    named = [member[0] for member in members if _names(logs, member[4])]
    if len(named) == 1 and leave:
        return "leave", named[0]
    if named:
        return "alone", f"the combined check failed in files of {', '.join(named[:-1])}{' and ' if named[1:] else ''}{named[-1]}"
    say("Train: the combined check failed in no change's files. Forge runs the failed jobs again once.")
    return ("alone", "Forge could not run the failed jobs again") if _restart(top, list(logs)) else ("rerun", "")


def _settled(top: Path, branch: str, own: set[int]) -> bool:
    """Wait until no check but Forge's own review still runs; False at the limit, as _restart waits."""
    deadline = time.monotonic() + float(os.environ.get("FORGE_CHECKS_WAIT", str(90 * 60)))
    while True:
        listed = _listed(top, branch)
        if listed is None or not any(check.get("bucket") == "pending" and not _own(check, own)
                                     for check in listed):
            return True
        left = deadline - time.monotonic()
        if left <= 0:
            return False
        time.sleep(min(15, left))


def _train(top: Path, default: str, plan: dict, merged: list[str], needs: dict, notes: list[str],
           last: list[str], second: bool = False) -> set[str]:
    """Test the members together on a temporary draft pull request, then merge each in order. Returns
    the members it merged or stopped; the rest go one at a time. A red check that names one change adds
    it to last, which merges after the others. It closes the pull request and deletes its branch, but
    only the ones it made."""
    members, tip = plan["members"], plan["tip"]
    names = ", ".join(member[0] for member in members)
    branch = f"forge-merge-train/{tip[:12]}"
    number, handled, pushed = None, set(), False
    try:  # an empty lease refuses a branch at another commit; porcelain tells a new branch ("*") from one
        # already at this commit ("="), which git calls up to date and Forge did not make: leave it alone.
        made = repo.run("git", "push", "--porcelain", f"--force-with-lease=refs/heads/{branch}:", "origin",
                        f"{tip}:refs/heads/{branch}", cwd=top)
        if made.returncode or not any(line.startswith("*\t") for line in made.stdout.splitlines()):
            say(f"Train: could not create {branch}, {ONE_BY_ONE}")
            return handled
        pushed = True
        created = repo.run("gh", "pr", "create", "--draft", "--base", default, "--head", branch, "--title",
                           f"Forge merge train: {names} (do not merge)", "--body",
                           "Forge tests these changes together once, then merges each in order. "
                           "Do not merge this pull request: Forge closes it and deletes its branch.", cwd=top)
        text = (created.stdout + created.stderr).lower()
        if created.returncode:
            say(f"Train: this repo allows no draft pull requests, {ONE_BY_ONE}"
                if "draft pull requests are not supported" in text else
                f"Train: could not open a pull request for {branch}, {ONE_BY_ONE}")
            return handled
        found = re.search(r"/pull/(\d+)", created.stdout)
        if found:
            number = found[1]
        else:
            try:
                number = str(json.loads(repo.run("gh", "pr", "list", "--head", branch, "--json", "number",
                                                 cwd=top).stdout)[0]["number"])
            except (ValueError, IndexError, KeyError, TypeError):
                pass
        say(f"Train: testing {len(members)} ready changes together: {names}.")
        for line in plan["out"]:
            say(line)
        reran = False
        while True:
            try:
                checks.wait(top, members[0][0], tip,
                            [name for name in repo.default_config(top)["checks"] if name != "forge-pr-check"],
                            branch=branch, progress=True, train=True)
                break
            except repo.Refused as error:
                # A red check, and a job that ran out of time, say which files broke it in their logs.
                kind, what = (_red(top, members, branch, tip, reran, not second)
                              if error.entry in (checks.REFUSALS["red"], checks.REFUSALS["timeout"]) else ("other", ""))
                if kind == "rerun":
                    reran = True
                    continue
                if kind == "leave":
                    say(f"Train: the combined check failed in files of {what}. {what} leaves the train and "
                        "merges last, one at a time, with its own check.")
                    last.append(what)
                elif kind == "alone":
                    say(f"Train: {what}, so each change merges one at a time with its own check.")
                else:  # another stop, or logs Forge cannot read: today's line, which names the failed checks
                    say(f"Train: the combined check failed: {str(error).splitlines()[0].rstrip('.')}. "
                        f"The ready changes merge one at a time, each with its own check.")
                return handled
        say(f"Train: the combined check passed. Forge merges {len(members)} changes in order.")
        for k, (item, member_branch, head, age, _) in enumerate(members):
            if line := _stale(top, default, plan["trees"][k], item, member_branch, head):
                say(line)
                return handled
            # merge.py looks at main again at the moment of the merge; the head is GitHub's to match then.
            child, reader, lines = _child(top, item, {}, {TRAIN: plan["trees"][k]})
            child.wait()
            reader.join()
            child.stdin.close()
            if child.returncode:  # a move during its merge sends it and the rest one at a time, not to you
                if line := _stale(top, default, plan["trees"][k], item, member_branch, head):
                    say(line)
                    return handled
                handled.add(item)
                needs[item] = _stop(item, age, lines, child.returncode)
                say(f"{item} stopped: {needs[item][1]}")
                return handled
            handled.add(item)
            merged.append(item)
            say(f"{item} merged.")
        repo.git("fetch", "-q", "origin", default, cwd=top)
        if _tree(top, f"origin/{default}") != plan["trees"][-1]:
            notes.append(f"Train: after the last merge, {default} does not match what the train tested. "
                         f"Check {default}: the next pull request check or the nightly full run tests it.")
            say(notes[-1])
        return handled
    finally:
        if number:
            repo.run("gh", "pr", "close", number, cwd=top)
        if pushed:
            repo.run("git", "push", f"--force-with-lease=refs/heads/{branch}:{tip}", "origin", "--delete",
                     branch, cwd=top)


def _stale(top: Path, default: str, tested: str, item: str, branch: str, head: str) -> str | None:
    """The Train line that says why a member cannot merge in the train now, or None. The default branch
    must hold the tree the train tested so far, and the pull request the commit it tested."""
    repo.git("fetch", "-q", "origin", default, cwd=top)
    if _tree(top, f"origin/{default}") != tested:
        return (f"Train: {default} no longer matches what the train tested, so the remaining changes "
                "merge one at a time, each with its own check.")
    shown = repo.run("gh", "pr", "view", branch, "--json", "headRefOid,mergeStateStatus", cwd=top)
    try:
        current = json.loads(shown.stdout) if shown.returncode == 0 else {}
    except ValueError:
        current = {}
    if current.get("headRefOid") != head:
        return f"Train: {item} changed after the combined check, so it and the remaining changes merge one at a time."
    if current.get("mergeStateStatus") == "BEHIND":
        return UP_TO_DATE.format(default=default)
    return None


def _child(top: Path, item: str, slots: dict[str, str], extra: dict[str, str] | None = None, *,
           held: set[str] | None = None, hold: bool = False) -> tuple[subprocess.Popen, threading.Thread, list[str]]:
    """forge land <item> in its own process, since close and merge change the working folder; its
    lines come out prefixed with the change's name."""
    code = (f"import sys; sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r}); "
            "from forge.cli import main; raise SystemExit(main())")
    child = subprocess.Popen([sys.executable, "-c", code, "land", item], cwd=top,
                             env={**os.environ, QUEUED: "1", **({HOLD: "1"} if hold else {}), **(extra or {})},
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
    lines: list[str] = []
    slots[item] = "active"

    def relay() -> None:
        for line in child.stdout:
            if line.rstrip("\n") in (SLOT_WAIT, SLOT_RESUME):
                slots[item] = line.rstrip("\n")
                continue
            if line.rstrip("\n") == HELD and held is not None:
                held.add(item)
                continue
            lines.append(line.rstrip("\n"))
            say(f"{item}: {lines[-1]}")
    reader = threading.Thread(target=relay, daemon=True)
    reader.start()
    return child, reader, lines


COMMANDS = [{
    "words": "land", "run": "land", "changes_state": True,
    "help": "Build, close, fix and merge a task or fix",
    "args": [(('item',), {"nargs": "?", "help": "the task or fix to land"}),
             (("--note",), {"metavar": "TEXT", "help": "guide the first round this run starts"}),
             (("--all",), {"action": "store_true",
                           "help": "close and merge every change in close, oldest first"})],
    "position": 165,
    "listing": "| `forge land <item>` / `forge land --all` | Builds, closes, runs at most one fix round and merges a "
               "task or fix where the repo allows agent merges; `--all` closes and merges every change "
               "in close, oldest first, several at a time, and tests two to five ready changes together once "
               "where the agent merges and CI runs the tests; `--note \"<text>\"` guides one item's "
               "first round; run it in the background |",
}]
