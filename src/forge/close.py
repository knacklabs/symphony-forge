"""forge close: close a task or fix by the close rule.

Merge the default branch in, review the head (unless the committed review still covers it) and
commit the result, push and open or update the pull request, then wait for the checks forge.toml
names on exactly that pushed head. Nothing is committed after the checks: GitHub holds when they
finished. A human merges.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from forge import __version__, checks, codex, init, repo, review, spotted, story

REFUSALS = {
    "not_started": ("Forge has not started {item} in any worktree of this repo.", "forge next"),
    "no_checks": ("forge.toml names no checks for close to wait for.", "forge doctor"),
    "conflict": ("Merging {default} into {branch} conflicts in {files}.",
                 "git -C {path} merge origin/{default}, fix the conflicts and commit, "
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
    question = codex.record(top, item).get("question")
    if question:
        repo.refuse(REFUSALS["question"], item=item, question=question)
    state, cfg = repo.read_state(item, top) or {}, repo.config(top)
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

    _merge_default(top, item, branch, default)
    spotted.check(top, item)
    if not migrating:
        _synced(top, item)
    light = review.blocking_level(top, item, state, f"origin/{default}") == "P0"
    previous = state.get("review") or {}
    result = previous
    fresh = result.get("changed") == review.fingerprint("HEAD", item, top, state, f"origin/{default}")
    if dismissals and not fresh:
        repo.refuse(REFUSALS["stale_dismiss" if result else "bad_dismiss"], item=item)
    if not fresh:
        # read after the merge, which may change the command
        command = review.close_test(top, f"origin/{default}")
        failed, tested = review.test_run(top, command, f"origin/{default}")
        if failed:  # a review would only report the same failure
            state.update(tests=tested, status="fixing")
            _save(top, item, state, f"Tests of {item} failed")
            repo.refuse(REFUSALS["tests_failed"], command=command, item=item)
        state.pop("tests", None)
        start, clock = repo.now(), time.monotonic()
        outcome = "failed"
        selected: dict[str, str] = {}
        try:
            result = review.run(top, item, state, cfg, f"origin/{default}", selected, previous,
                                light=light, tested=tested)
            dismissed = {}
            for dismissal in previous.get("dismissals", []):
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
    noted = (spotted.PATH,) if spotted.record(top, item, state, f"origin/{default}", result) else ()
    if not fresh or dismissals:
        result["status"] = "blocked" if serious else "clean"
        state.update(review=result, status="fixing" if serious else "waiting for checks")
        _save(top, item, state, f"Review of {item}: {result['status']}", *noted)
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
        repo.refuse(REFUSALS["blocked"], item=item, findings="; ".join(
            f"finding {n} ({f['title'].rstrip('.')})" for n, f in serious))
    # forge-pr-check runs from the base branch, which has no Forge until migrate's or adopt's PR merges.
    start, clock = repo.now(), time.monotonic()
    outcome = "failed"
    try:
        checks.wait(top, item, head, [name for name in cfg["checks"]
                                      if not (migrating and name == "forge-pr-check")])
        outcome = "passed"
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


def merger(top: Path, state: dict[str, Any]) -> str:
    """"human" for migrate, adopt and the merge switch's fix, else the repo's merge setting."""
    return "human" if state.get("kind") in ("migrate", "adopt") or state.get("why") == WHY else repo.merge_setting(top)


def _worktree(item: str) -> Path:
    """The checkout on the item's own branch: the one its state names. An earlier item's state
    reaches later branches through the default branch, so the file alone proves nothing."""
    for block in repo.git("worktree", "list", "--porcelain", cwd=repo.root()).split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines())
        branch = fields.get("branch", "").removeprefix("refs/heads/")
        state = repo.read_state(item, Path(fields["worktree"])) if branch else None
        if state and state.get("branch") == branch:
            return Path(fields["worktree"])
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
    repo.git("fetch", "-q", "origin", default, cwd=top)
    done = repo.run("git", "merge", "-q", "--no-edit", f"origin/{default}", cwd=top)
    if done.returncode == 0:
        return
    files = repo.git("diff", "--name-only", "--diff-filter=U", cwd=top).splitlines()
    if not files:
        raise subprocess.CalledProcessError(done.returncode, ["git", "merge"], done.stdout,
                                            done.stderr)
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
        status = repo.run("git", "status", "--porcelain", "-z", "--untracked-files=all",
                          cwd=check).stdout
        # sync's new hook shims are never committed, even when the hooks folder is in the checkout (husky).
        hooks = repo.git("rev-parse", "--git-path", "hooks/", cwd=check)
        stale = [entry[3:] for entry in status.split("\0") if entry and not entry.startswith(f"?? {hooks}")]
    finally:
        repo.git("worktree", "remove", "-f", str(check), cwd=top)
        repo.git("branch", "-D", branch, cwd=top)
    if stale:
        repo.refuse(REFUSALS["unsynced"], kind=kind, files=", ".join(stale),
                    verb="aren't" if len(stale) > 1 else "isn't", path=top, item=item)


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
             pr: dict[str, Any] | None, result: dict[str, Any]) -> None:
    """Open the pull request, or replace only Forge's block in its body. While the review is
    blocked, the pull request is a draft."""
    block = _block(result, review.functional_check(top, f"origin/{default}"))
    draft = result["status"] == "blocked"
    # The body goes through a file under .git/forge/: in argv it meets length limits, and a
    # multi-line argument can't pass through a Windows .cmd shim.
    body_file = repo.forge_dir(top) / f"pr-body-{item.replace('/', '-')}.md"
    if pr is None:
        title, why, summary = _title(top, item, state)
        notes = f"{state['notes']}\n\n" if state.get("notes") else ""  # migrate's plan
        body_file.write_bytes(f"Why: {why}\nDone when: {summary}\n\n{notes}{block}\n".encode("utf-8"))
        create = ("--base", default, "--head", branch, "--title", title, "--body-file",
                  str(body_file))
        url = ((draft and _draft(top, "pr", "create", "--draft", *create))
               or _gh(top, "pr", "create", *create))
        print(f"Opened the pull request: {url.strip()}")
        return
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
    if result["status"] == "blocked":
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
    """The item's pull request merged: name `forge story done` once the story's last one has."""
    print(f"The pull request for {item} is merged.")
    key, _, name = item.partition("/")
    if name:
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
             (('--because',), {"action": "append", "metavar": "FILE:LINE_REASON"})],
    "position": 150,
    "listing": "| `forge close <item>` | Closes a task or fix by the close rule |",
}]
