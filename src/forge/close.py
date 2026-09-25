"""forge close: close a task or fix by the close rule.

Merge the default branch in, review the head (unless the committed review still covers it) and
commit the result, push and open or update the pull request, then wait for the checks forge.toml
names on exactly that pushed head. Nothing is committed after the checks: GitHub holds when they
finished. A human merges.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from forge import checks, repo, review

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
    "blocked": ("The review left serious findings open: {findings}.",
                'forge work {item}, or forge close {item} --dismiss <n> --because '
                '"<file:line> <reason>"'),
}
BEGIN, END = "<!-- forge:begin -->", "<!-- forge:end -->"


def close(args: argparse.Namespace) -> int:
    item = args.item
    top = _worktree(item)
    state, cfg = repo.read_state(item, top) or {}, repo.config(top)
    if not cfg["checks"]:
        repo.refuse(REFUSALS["no_checks"])
    dismissals = _dismissals(args, item)
    branch, default = repo.current_branch(top), repo.default_branch(top)
    pr = _pull_request(top, branch)
    if pr and pr["state"] == "MERGED":
        return _merged(top, item)

    _merge_default(top, item, branch, default)
    result = state.get("review") or {}
    fresh = result.get("tree") == review.fingerprint("HEAD", item, top, state)
    if dismissals and not fresh:
        repo.refuse(REFUSALS["stale_dismiss" if result else "bad_dismiss"], item=item)
    if not fresh:
        result = review.run(top, item, state, cfg, f"origin/{default}")
        repo.add_step(state, "review")
    for number, because in dismissals:
        if not 1 <= number <= len(result["findings"]):
            repo.refuse(REFUSALS["bad_dismiss"], item=item)
        _check_line(top, item, result["commit"], because.split()[0])
        result["dismissals"] = [d for d in result["dismissals"] if d["finding"] != number]
        result["dismissals"].append({"finding": number, "because": because})
    serious = review.blocking(result)
    if not fresh or dismissals:
        result["status"] = "blocked" if serious else "clean"
        state.update(review=result, status="fixing" if serious else "waiting for checks")
        _save(top, item, state, f"Review of {item}: {result['status']}")
    head = repo.git("rev-parse", "HEAD", cwd=top)
    repo.git("push", "-q", "-u", "origin", branch, cwd=top)
    _publish(top, item, state, branch, default, pr, result)

    if serious:
        for number, finding in serious:
            print(f"{number}. {finding['priority']} {finding['title']} "
                  f"({finding['file']}:{finding['line']})\n{finding['body']}\n")
        repo.refuse(REFUSALS["blocked"], item=item, findings="; ".join(
            f"finding {n} ({f['title'].rstrip('.')})" for n, f in serious))
    checks.wait(top, item, head, cfg["checks"])
    print(f"Ready: {item} has a clean review and green checks. A human merges its pull request.")
    return 0


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


def _check_line(top: Path, item: str, commit: str, where: str) -> None:
    """A dismissal's file:line must be a real line of the reviewed commit."""
    path, _, line = where.rpartition(":")
    shown = repo.run("git", "show", f"{commit}:{path}", cwd=top)
    if shown.returncode or not 1 <= int(line) <= len(shown.stdout.splitlines()):
        repo.refuse(REFUSALS["no_such_line"], where=where, item=item)


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


def _save(top: Path, item: str, state: dict[str, Any], message: str) -> None:
    repo.write_state(item, state, top)
    repo.commit_state(message, repo.state_path(item), top=top)


def _gh(top: Path, *args: str) -> str:
    done = repo.run("gh", *args, cwd=top)
    if done.returncode:
        raise subprocess.CalledProcessError(done.returncode, ["gh", *args], done.stdout,
                                            done.stderr)
    return done.stdout


def _pull_request(top: Path, branch: str) -> dict[str, Any] | None:
    """The branch's open pull request, else its merged one, else None."""
    prs = json.loads(_gh(top, "pr", "list", "--head", branch, "--state", "all",
                         "--json", "number,state,body"))
    return next((pr for state in ("OPEN", "MERGED") for pr in prs if pr.get("state") == state),
                None)


def _publish(top: Path, item: str, state: dict[str, Any], branch: str, default: str,
             pr: dict[str, Any] | None, result: dict[str, Any]) -> None:
    """Open the pull request, or replace only Forge's block in its body."""
    block = _block(result)
    # The body goes through a file under .git/forge/: in argv it meets length limits, and a
    # multi-line argument can't pass through a Windows .cmd shim.
    body_file = repo.forge_dir(top) / f"pr-body-{item.replace('/', '-')}.md"
    if pr is None:
        title, summary = _title(top, item, state)
        body_file.write_bytes(f"{summary}\n\n{block}\n".encode("utf-8"))
        url = _gh(top, "pr", "create", "--base", default, "--head", branch, "--title", title,
                  "--body-file", str(body_file))
        print(f"Opened the pull request: {url.strip()}")
        return
    body = pr.get("body") or ""
    marked = re.compile(re.escape(BEGIN) + ".*?" + re.escape(END), re.S)
    new = (marked.sub(lambda _: block, body, count=1) if marked.search(body)
           else f"{body.rstrip()}\n\n{block}\n")
    if new != body:
        body_file.write_bytes(new.encode("utf-8"))
        _gh(top, "pr", "edit", str(pr["number"]), "--body-file", str(body_file))
        print("Updated the pull request's review block.")


def _block(result: dict[str, Any]) -> str:
    """Forge's block in the pull request body: every finding, numbered for --dismiss."""
    because = {d["finding"]: d["because"] for d in result["dismissals"]}
    lines = [BEGIN, f"Forge review of {result['commit'][:12]}: {result['status']}.", ""]
    for n, finding in enumerate(result["findings"], 1):
        note = (f"dismissed because {because[n]}" if n in because
                else "blocks the merge" if finding["priority"] in review.SERIOUS else "advisory")
        lines.append(f"{n}. {finding['priority']} {finding['title']} "
                     f"({finding['file']}:{finding['line']}): {note}")
    return "\n".join([*lines, END])


def _title(top: Path, item: str, state: dict[str, Any]) -> tuple[str, str]:
    """A task's Name and "What it delivers"; a fix's why and done-when lines."""
    if "/" in item:
        row = review.task(top, item)[2]
        title, summary = row.get("name", ""), row.get("what it delivers", "")
    else:
        title, summary = state.get("why", ""), state.get("done_when", "")
    return " ".join(title.split()) or item, " ".join(summary.split())


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
