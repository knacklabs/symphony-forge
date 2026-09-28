from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from forge import checks, close, codex, repo

COMMANDS = [{
    "words": "merge", "run": "merge", "changes_state": False,
    "help": "Merge a ready item when this repo allows it",
    "args": [(('item',), {})], "position": 160,
    "listing": "| `forge merge <item>` | Merges a ready item when the default branch allows agent merges |",
}]

REFUSALS = {
    "disabled": ("forge merge is disabled by merge = \"human\" in the default branch's forge.toml.",
                 "ask the repo owner to set merge = \"agent\" on the default branch"),
    "not_ready": ("Forge has no clean ready record for {item}.", "forge close {item}"),
    "changed": ("The pull request's head changed since Forge recorded {item} ready.", "forge close {item}"),
    "pr": ("Forge needs an open pull request for {item} targeting {default} from {branch}.",
           "open or correct its pull request, then forge close {item}"),
    "merge_failed": ("GitHub did not merge the pull request for {item}: {reason}.", "check the pull request, then forge merge {item}"),
    "pending": ("GitHub has not finished merging the pull request for {item}.", "check the pull request, then forge merge {item}"),
    "remote_branch": ("Forge could not delete the remote branch for {item}.",
                      "check the branch on GitHub, then forge merge {item}"),
    "worktree": ("Forge could not remove the worktree for {item}.",
                 "unlock it or close programs using it, then forge merge {item}"),
}
def merge(args: argparse.Namespace) -> int:
    top, item = repo.root(), args.item
    config = repo.default_config(top)
    if repo.merge_setting(top) != "agent":
        repo.refuse(REFUSALS["disabled"])
    path = repo.ready_path(item, top)
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        receipt = {}
    head = receipt.get("commit") if isinstance(receipt, dict) else None
    if (not isinstance(receipt, dict) or receipt.get("review") != "clean"
            or not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40,64}", head)):
        repo.refuse(REFUSALS["not_ready"], item=item)
    worktree = close._worktree(item)
    branch = repo.current_branch(worktree)
    default = repo.default_branch(top)
    shown = repo.run("gh", "pr", "view", branch, "--json",
                     "number,state,baseRefName,headRefName,headRefOid,title,isDraft", cwd=top)
    try:
        pr = json.loads(shown.stdout) if shown.returncode == 0 else {}
    except ValueError:
        pr = {}
    if (not isinstance(pr, dict) or pr.get("state") not in ("OPEN", "MERGED") or (pr.get("state") == "OPEN" and pr.get("isDraft") is not False)
            or pr.get("baseRefName") != default or pr.get("headRefName") != branch
            or not isinstance(pr.get("number"), int) or not isinstance(pr.get("title"), str)):
        repo.refuse(REFUSALS["pr"], item=item, default=default, branch=branch)
    if pr.get("headRefOid") != head:
        repo.refuse(REFUSALS["changed"], item=item)
    if pr["state"] == "OPEN":
        if repo.git("rev-parse", branch, cwd=top) != head:
            repo.refuse(REFUSALS["changed"], item=item)
        checks.wait(top, item, head, config["checks"])
        done = repo.run("gh", "pr", "merge", str(pr["number"]), "--squash",
                        "--subject", pr["title"], "--match-head-commit", head, cwd=top)
        after = repo.run("gh", "pr", "view", str(pr["number"]), "--json", "state", "--jq", ".state", cwd=top)
        merged = after.returncode == 0 and after.stdout.strip() == "MERGED"
        if not merged and done.returncode:
            reason = (done.stderr or done.stdout or "GitHub gave no reason").strip().splitlines()[-1]
            repo.refuse(REFUSALS["merge_failed"], item=item, reason=reason)
        if not merged:
            repo.refuse(REFUSALS["pending"], item=item)
    main_checkout = repo.forge_dir(top).parent.parent
    pending = receipt.get("pending_archives")
    if pending is None:
        pending = sorted(_conversations(main_checkout, item))
        receipt["pending_archives"] = pending
        _save_ready(path, receipt)
    if not isinstance(pending, list) or not all(isinstance(thread, str) for thread in pending):
        repo.refuse(REFUSALS["not_ready"], item=item)
    failed_archives = []
    for thread in pending[:]:
        try:
            archived = codex.archive(main_checkout, item, "Fix", thread)
        except Exception:
            archived = False
        if not archived:
            failed_archives.append(thread)
            continue
        pending.remove(thread)
        _save_ready(path, receipt)
    remote_ref = f"refs/heads/{branch}"
    remote = repo.run("git", "ls-remote", "--heads", "origin", remote_ref, cwd=top)
    if remote.returncode:
        repo.refuse(REFUSALS["remote_branch"], item=item)
    remote_head = remote.stdout.split()[0] if remote.stdout.strip() else None
    if remote_head and remote_head != head:
        repo.refuse(REFUSALS["remote_branch"], item=item)
    if remote_head:
        deleted = repo.run("git", "push", f"--force-with-lease={remote_ref}:{head}",
                           "origin", "--delete", branch, cwd=top)
        if deleted.returncode:
            repo.refuse(REFUSALS["remote_branch"], item=item)
    repo.git("fetch", "-q", "origin", default, cwd=top)
    dirty = bool(repo.git("status", "--porcelain", cwd=worktree))
    advanced = repo.git("rev-parse", branch, cwd=worktree) != head
    if advanced:
        print(f"Merged {item}. Its worktree at {worktree} has local commits outside the merged pull request, so Forge left it and its local branch in place.")
    elif dirty:
        print(f"Merged {item}. Its worktree at {worktree} has uncommitted changes, so Forge left it and its local branch in place.")
    else:
        if top == worktree:
            os.chdir(main_checkout)
        removed = repo.run("git", "worktree", "remove", str(worktree), cwd=main_checkout)
        if removed.returncode:
            repo.refuse(REFUSALS["worktree"], item=item)
        if repo.run("git", "show-ref", "--verify", f"refs/heads/{branch}", cwd=main_checkout).returncode == 0:
            repo.git("branch", "-D", branch, cwd=main_checkout)
        print(f"Merged {item} and removed its worktree and local branch.")
    if dirty or advanced:
        receipt["tidied"] = True
        _save_ready(path, receipt)
    else:
        path.unlink(missing_ok=True)
    if failed_archives:
        print(f"Forge could not archive these Codex conversations for {item}: "
              f"{', '.join(failed_archives)}. Codex can archive them later.")
    return 0


def _save_ready(path: Path, receipt: dict) -> None:
    saved = path.with_suffix(".tmp")
    saved.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    os.replace(saved, path)


def _conversations(top: Path, item: str) -> set[str]:
    base = repo.forge_dir(top) / "threads" / ("task" if "/" in item else "fix") / item
    found = {saved} if isinstance(saved := codex.record(top, item).get("conversation"), str) else set()
    try:
        for line in base.with_suffix(".log").read_text(encoding="utf-8").splitlines():
            thread = json.loads(line).get("conversation")
            if isinstance(thread, str):
                found.add(thread)
    except (OSError, ValueError):
        pass
    return found
