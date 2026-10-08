"""forge close: close a task or fix by the close rule.

Merge the default branch in, push and open the pull request so CI runs during review. Commit and
publish the result, then wait for the checks forge.toml names on exactly that pushed head.
Nothing is committed after the checks: GitHub holds when they finished. A human merges.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from forge import __version__, checks, codex, init, repo, review, spotted, story, sync

REFUSALS = {
    "not_started": ("Forge has not started {item} in any worktree of this repo.", "forge next"),
    "no_checks": ("forge.toml names no checks for close to wait for.", "forge doctor"),
    "conflict": ("Merging {default} into {branch} conflicts in {files}.",
                 "git -C {path} merge origin/{default}, follow Keeping work moving in "
                 ".codex/skills/forge/SKILL.md or .claude/skills/forge/SKILL.md and commit, "
                 "then forge close {item}"),
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
                "earlier round flagged too, so Forge stops sending the worker back. Ask the human "
                "to narrow the part, split it, or accept the remaining findings.",
                'forge close {item} --resolve <narrow|split|accept> --reason "<human\'s choice>"'),
    "bad_choice": ("Record the human's choice only on a stopped review loop, with a non-empty "
                   "--reason and no finding dismissals.",
                   'forge close {item} --resolve <narrow|split|accept> --reason "<human\'s choice>"'),
    "unsynced": ("This {kind} changes Forge's version, but {files} {verb} what forge sync writes "
                 "for it.", "forge sync in {path}, commit what it wrote, then forge close {item}"),
    "unsynced_forge": ("This {kind} pins Forge {pinned}, but Forge {installed} is running close, "
                       "so it can't tell whether the {kind}'s files are what {pinned} writes.",
                       "uv tool install git+https://github.com/knacklabs/symphony-forge@{pinned}, "
                       "then forge close {item}"),
    "tests_failed": ("`{command}` failed on this machine, so close stopped before the review; the "
                     "next worker round gets its output.", "forge work {item}"),
    "question": ("The worker is waiting for an answer:\n{question}",
                 'forge work {item} --note "<answer>"'),
}
BEGIN, END = "<!-- forge:begin -->", "<!-- forge:end -->"
# forge merge enable's fix is known by these; only the repo owner merges it.
WHY, DONE = "Let the agent merge this repo's ready pull requests.", 'The default branch\'s forge.toml sets merge = "agent".'


def close(args: argparse.Namespace) -> int:
    item = args.item
    top = _worktree(item)
    state, cfg = repo.read_state(item, top) or {}, repo.config(top)
    choice, reason = getattr(args, "resolve", None), getattr(args, "reason", None)
    if choice or reason is not None:
        if (not choice or not reason or not reason.strip() or
                not state.get("stop") or state["stop"].get("choice") or
                args.dismiss or args.because):
            repo.refuse(REFUSALS["bad_choice"], item=item)
        result = state["review"]
        if choice == "accept":
            dismissed = {d["finding"] for d in result["dismissals"]}
            result["dismissals"].extend(
                {"finding": number, "because": f"Human accepted the remaining finding: {reason}",
                 "accepted": True}
                for number, _ in enumerate(result["findings"], 1) if number not in dismissed)
            result["status"] = "clean"
        state["stop"].update(choice=choice, reason=reason.strip())
        state["status"] = "waiting for checks" if choice == "accept" else "fixing"
        _save(top, item, state, f"Record the human's review loop choice: {choice}")
        if choice != "accept":
            print(f"Recorded the human's choice. {choice.capitalize()} the part as agreed, "
                  f"then forge work {item}.")
            return 0
        print("Recorded the human's choice.")
    had_stop = bool(state.get("stop"))
    check_stop(item, state)
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
    _merge_default(top, item, branch, default)
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
    if choice != "accept" and any(d.get("accepted") for d in result.get("dismissals", [])):
        fresh = fresh and result.get("changed") == changed
    refreshed = fresh and (result.get("changed") != changed or
                           result.get("branch_diff") != branch_diff)
    if fresh:
        result.update(changed=changed, branch_diff=branch_diff)
    if dismissals and not fresh:
        repo.refuse(REFUSALS["stale_dismiss"] if result else REFUSALS["bad_dismiss"], item=item)
    round_number = sum(step["step"] == "review" for step in state.get("steps", []))
    if (not fresh and round_number >= 3 and not state.get("stop") and
            _three_blocked_reviews(top, item)):
        file = review.blocking(previous)[0][1]["file"]
        state.update(stop={"file": file, "round": round_number + 1}, status="hotspot")
        _save(top, item, state, f"Review of {item} stopped after three blocked rounds")
        check_stop(item, state)
    if not fresh:
        # read after the merge, which may change the command
        command = review.close_test(top, f"origin/{default}")
        failed, tested = review.test_run(top, command, f"origin/{default}")
        if failed:  # a review would only report the same failure
            state.update(tests=tested, status="fixing")
            _save(top, item, state, f"Tests of {item} failed")
            repo.refuse(REFUSALS["tests_failed"], command=command, item=item)
        state.pop("tests", None)
        _push(top, branch)
        pr = _publish(top, item, state, branch, default, pr,
                      {"status": "reviewing", "findings": [], "dismissals": []})
        start, clock = repo.now(), time.monotonic()
        outcome = "failed"
        selected: dict[str, str] = {}
        try:
            result = review.run(top, item, state, cfg, f"origin/{default}", selected, previous,
                                light=light, tested=tested)
            dismissed = {}
            for dismissal in previous.get("dismissals", []):
                if dismissal.get("accepted"):
                    continue  # Acceptance covers this review, not later code or scope.
                number = dismissal["finding"]
                if not 1 <= number <= len(previous["findings"]):
                    continue
                finding = previous["findings"][number - 1]
                dismissed[(finding["file"], finding["title"])] = dismissal
            result["dismissals"] = [dict(dismissed[(finding["file"], finding["title"])],
                                         finding=number)
                                    for number, finding in enumerate(result["findings"], 1)
                                    if (finding["file"], finding["title"]) in dismissed]
            outcome = "blocked" if review.blocking(result) else "clean"
        finally:
            if outcome == "failed":
                repo.record_event(top, item, "review result", outcome=outcome)
            repo.record_timing(top, item, "review", start, clock, outcome, selected)
        repo.add_step(state, "review")
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
    if not fresh:
        flagged = set(state.get("flagged", []))
        files = {finding["file"] for _, finding in serious}
        if serious and round_number >= 3 and not state.get("stop"):
            default_files = set(repo.git("ls-tree", "-r", "-z", "--name-only",
                                         f"origin/{default}", cwd=top).split("\0"))
            candidates = sorted(file for file in files & flagged & default_files
                                if spotted._path(file))
            if candidates:
                file = candidates[0]
                stopped = {"file": file}
                state["stop"] = stopped
        state["flagged"] = sorted(flagged | files)
    noted = (spotted.PATH,) if spotted.record(top, item, state, f"origin/{default}", result) else ()
    if not fresh or dismissals or refreshed or had_stop and not state.get("stop"):
        result["status"] = "blocked" if serious else "clean"
        state.update(review=result, status="hotspot" if stopped else
                     "fixing" if serious else "waiting for checks")
        message = f"Review of {item}: {result['status']}"
        if stopped:
            message += f"; {stopped['file']} keeps breaking"
        _save(top, item, state, message, *noted)
    elif noted:  # a reused clean review still records what the worker spotted
        _save(top, item, state, f"Review of {item}: {result['status']}", *noted)
    head = repo.git("rev-parse", "HEAD", cwd=top)
    _push(top, branch)
    _publish(top, item, state, branch, default, pr, result)
    _attach(top, item, branch)

    for number, finding in serious:
        print(f"{number}. {finding['priority']} {finding['title']} "
              f"({finding['file']}:{finding['line']})\n{finding['body']}\n")
    advice = [(n, f) for n, f in enumerate(result["findings"], 1) if f["priority"] not in
              (("P0",) if result.get("blocking_level") == "P0" else review.SERIOUS)]
    if advice:
        print("Advice that does not block the merge:")
        for number, finding in advice:
            print(f"{number}. {finding['priority']} {finding['title']} "
                  f"({finding['file']}:{finding['line']})\n{finding['body']}\n")
    if serious:
        if stopped:
            repo.refuse(REFUSALS["hotspot"], item=item, round=round_number, **stopped)
        repo.refuse(REFUSALS["blocked"], item=item, findings="; ".join(
            f"finding {n} ({f['title'].rstrip('.')})" for n, f in serious))
    # forge-pr-check runs from the base branch, which has no Forge until migrate's or adopt's PR merges.
    start, clock = repo.now(), time.monotonic()
    outcome = "failed"
    try:
        with repo.record_run(top, item, "ci") as ran:
            checks.wait(top, item, head, [name for name in cfg["checks"]
                                          if not (migrating and name == "forge-pr-check")])
            outcome = ran["outcome"] = "passed"
    finally:
        repo.record_timing(top, item, "CI wait", start, clock, outcome)
    if pr and pr.get("isDraft"):  # a blocked review left it a draft
        _gh(top, "pr", "ready", str(pr["number"]))
    merge = merger(top, state)
    path = repo.ready_path(item, top)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"commit": head, "review": "clean"}) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    if merge == "agent":
        print(f"Ready: {item} has a clean review and green checks.")
        print(f"Next: forge merge {item}")
    else:
        print(f"Ready: {item} has a clean review and green checks. A human merges its pull request.")
    return 0


def _three_blocked_reviews(top: Path, item: str) -> bool:
    """Use committed review results, including older releases and later dismissals."""
    seen = set()
    path = repo.state_path(item)
    for commit in repo.git("log", "--first-parent", "--format=%H", "--", path,
                           cwd=top).split():
        result = json.loads(repo.git("show", f"{commit}:{path}", cwd=top)).get("review") or {}
        if not result or not review.blocking(result):
            return False
        if result["commit"] in seen:
            continue
        seen.add(result["commit"])
        if len(seen) == 3:
            return True
    return False


def check_stop(item: str, state: dict[str, Any]) -> None:
    """A human choice or a later clean review releases a review loop stop."""
    result = state.get("review") or {}
    if (result.get("status") == "clean" and not review.blocking(result) and
            not (state.get("stop") or {}).get("choice")):
        state.pop("stop", None)
    if state.get("stop") and not state["stop"].get("choice"):
        repo.refuse(REFUSALS["hotspot"], item=item,
                    **{"round": sum(step["step"] == "review" for step in state.get("steps", [])),
                       **state["stop"]})


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
    done = repo.run("git", "merge", "-q", "--no-edit", f"origin/{default}", cwd=top)
    if done.returncode == 0:
        return
    files = repo.git("diff", "--name-only", "--diff-filter=U", cwd=top).splitlines()
    if not files:
        raise subprocess.CalledProcessError(done.returncode, ["git", "merge"], done.stdout,
                                            done.stderr)
    # Read sync's inventory from a clean tree: conflicted adapters may not even parse.
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder) / "default"
        repo.git("worktree", "add", "-q", "--detach", str(base), f"origin/{default}", cwd=top)
        try:
            generated = {Path(path).as_posix() for path in sync.files(base, cfg)}
            if cfg.get("repo") == "forge-source":
                generated.add("docs/commands.md")
        finally:
            repo.git("worktree", "remove", "-f", str(base), cwd=top)
    if set(files) <= generated:
        repo.git("restore", f"--source=origin/{default}", "--staged", "--worktree", "--",
                 *files, cwd=top)
        done = repo.run("forge", "sync", cwd=top)
        if done.returncode:
            raise subprocess.CalledProcessError(done.returncode, ["forge", "sync"], done.stdout,
                                                done.stderr)
        changed = [path for path in synced_changes(top) if path in generated]
        if changed:
            repo.git("add", "-A", "--", *changed, cwd=top)
        repo.git("commit", "-q", "--no-edit", cwd=top)
        return
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
        done = repo.run("forge", "sync", cwd=check)
        if done.returncode:
            raise subprocess.CalledProcessError(done.returncode, ["forge", "sync"], done.stdout,
                                                done.stderr)
        stale = synced_changes(check)
    finally:
        repo.git("worktree", "remove", "-f", str(check), cwd=top)
        repo.git("branch", "-D", branch, cwd=top)
    if stale:
        repo.refuse(REFUSALS["unsynced"], kind=kind, files=", ".join(stale),
                    verb="aren't" if len(stale) > 1 else "isn't", path=top, item=item)


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
    for wait in (1, 2, 4, None):
        try:
            repo.git("push", "-q", "-u", "origin", branch, cwd=top)
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


def _publish(top: Path, item: str, state: dict[str, Any], branch: str, default: str,
             pr: dict[str, Any] | None, result: dict[str, Any]) -> dict[str, Any]:
    """Open the pull request, or replace only Forge's block in its body. While the review is
    blocked, the pull request is a draft."""
    check = review.functional_check(top, f"origin/{default}")
    proof = review.commit_paragraph(top, f"origin/{default}", "Proof list:")
    block = _block(result, "\n\n".join(part for part in (check, proof) if part))
    draft = result["status"] == "blocked" or (pr is None and result["status"] == "reviewing")
    # The body goes through a file under .git/forge/: in argv it meets length limits, and a
    # multi-line argument can't pass through a Windows .cmd shim.
    body_file = repo.forge_dir(top) / f"pr-body-{item.replace('/', '-')}.md"
    if pr is None:
        title, why, summary = _title(top, item, state)
        notes = f"{state['notes']}\n\n" if state.get("notes") else ""  # migrate's plan
        body_file.write_bytes(f"Why: {why}\nDone when: {summary}\n\n{notes}{block}\n".encode("utf-8"))
        create = ("--base", default, "--head", branch, "--title", title, "--body-file",
                  str(body_file))
        url = _draft(top, "pr", "create", "--draft", *create) if draft else ""
        is_draft = bool(url)
        url = url or _gh(top, "pr", "create", *create)
        print(f"Opened the pull request: {url.strip()}")
        return {"number": int(url.strip().rsplit("/", 1)[1]), "state": "OPEN",
                "body": body_file.read_text(encoding="utf-8"), "isDraft": is_draft}
    if draft and not pr.get("isDraft"):
        _draft(top, "pr", "ready", str(pr["number"]), "--undo")
    body = pr.get("body") or ""
    marked = re.compile(re.escape(BEGIN) + ".*?" + re.escape(END), re.S)
    new = (marked.sub(lambda _: block, body, count=1) if marked.search(body)
           else f"{body.rstrip()}\n\n{block}\n")
    if new != body:
        body_file.write_bytes(new.encode("utf-8"))
        _gh(top, "pr", "edit", str(pr["number"]), "--body-file", str(body_file))
        print("Updated the pull request's review block.")
    return {**pr, "body": new}


def _block(result: dict[str, Any], check: str) -> str:
    """Forge's block in the pull request body: the open blocking findings plainly first, or one
    `Review: clean` line, then the dismissed and advisory findings folded away, then the worker's
    functional check from its commit message. Each finding is a bullet naming its --dismiss number
    in text, since GitHub renumbers an ordered list."""
    because = {d["finding"]: d for d in result["dismissals"]}
    blocking, rest = [], []
    for n, finding in enumerate(result["findings"], 1):
        note = (f"dismissed because {because[n]['because']}"
                + (" (evidence from the base)" if because[n].get("from_base") else "")
                if n in because
                else "blocks the merge" if finding["priority"] in (("P0",) if result.get("blocking_level") == "P0" else review.SERIOUS)
                else "advisory: " + " ".join(finding.get("body", "").split()))
        (blocking if note == "blocks the merge" else rest).append(
            f"- Finding {n} ({finding['priority']}): {finding['title']} "
            f"({finding['file']}:{finding['line']}): {note}")
    if result["status"] == "reviewing":
        lines = [BEGIN, "Review: running; CI is running alongside it."]
    elif result["status"] == "blocked":
        lines = [BEGIN, "The review found serious problems.", "", *blocking]
    else:
        lines = [BEGIN, f"Review: clean, {len(because)} dismissed, {len(rest) - len(because)} advice."]
    if rest:
        lines += ["", "<details>", "<summary>Dismissed and advisory findings</summary>", "", *rest,
                  "", "</details>"]
    return "\n".join([*lines, *(["", check] if check else []), END])


def _title(top: Path, item: str, state: dict[str, Any]) -> tuple[str, str, str]:
    """A short title and the why and done-when lines for a new pull request."""
    if "/" in item:
        _, doc, row = review.task(top, item)
        story_title = re.search(r"^# (.+)$", (top / "plans" / f"{item.split('/')[0]}.md").read_text(), re.M)
        title = f"{story_title[1]}: {row.get('name', '')}" if story_title else row.get("name", "")
        why, summary = doc.get("Why", ""), row.get("what it delivers", "")
    else:
        why, summary = state.get("why", ""), state.get("done_when", "")
        title = re.split(r"[,;:.!?]", why, maxsplit=1)[0][:70]
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
             (('--resolve',), {"choices": ["narrow", "split", "accept"]}),
             (('--reason',), {"help": "The human's choice after a review loop stop"})],
    "position": 150,
    "listing": "| `forge close <item>` | Closes a task or fix by the close rule |",
}]
