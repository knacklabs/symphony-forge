from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from forge import checks, close, codex, repo, story

COMMANDS = [{
    "words": "merge", "run": "merge", "changes_state": False,
    "help": "Merge a ready item when this repo allows it",
    "args": [(('item',), {})], "position": 160,
    "listing": "| `forge merge <item>` | Merges a ready item when the default branch allows agent merges |\n"
               "| `forge merge enable` | Run by the repo owner in their own terminal: opens the change that lets the agent merge ready pull requests, for the owner to merge |",
}]
ENABLE = "let-the-agent-merge"
# The switch's fix is known by what it records when it starts.
WHY, DONE = "Let the agent merge this repo's ready pull requests.", 'The default branch\'s forge.toml sets merge = "agent".'

REFUSALS = {
    "disabled": ("forge merge is disabled by merge = \"human\" in the default branch's forge.toml.",
                 "the repo owner runs forge merge enable in their own terminal"),
    "owner_only": ("Only the repo owner switches on agent merges, so Forge won't do it from an agent's shell.",
                   "the repo owner runs forge merge enable in their own terminal"),
    "enabled": ("The default branch's forge.toml already lets the agent merge.", "forge next"),
    "not_default": ("forge merge enable runs on the default branch, {default}.", "git switch {default}, then forge merge enable"),
    "taken": ("The fix let-the-agent-merge holds other work, so Forge left it alone.",
              "finish or remove that fix, then forge merge enable"),
    "owner_merges": ("{item} changes the merge setting in forge.toml, so only the repo owner merges its pull request.",
                     "the repo owner merges its pull request, then forge next"),
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
    if item == "enable":
        return _enable(top)
    config = repo.default_config(top)
    if repo.merge_setting(top) != "agent":
        repo.refuse(REFUSALS["owner_merges" if item == ENABLE else "disabled"], item=item)
    path = repo.ready_path(item, top)
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        receipt = {}
    head = receipt.get("commit") if isinstance(receipt, dict) else None
    if (not isinstance(receipt, dict) or receipt.get("review") != "clean"
            or not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40,64}", head)):
        repo.refuse(REFUSALS["not_ready"], item=item)
    if close.changes_merge(top, head):
        repo.refuse(REFUSALS["owner_merges"], item=item)
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


def _enable(top: Path) -> int:
    """Open the fix that sets merge = "agent", or continue it after an interruption, then close it
    so the owner can merge it. Agent merges loosen a gate on the agent itself, so an agent's shell
    may never run this."""
    if any(os.environ.get(variable) for variable in story.COORDINATORS):
        repo.refuse(REFUSALS["owner_only"])
    repo.check_pin(top, item=ENABLE, words="merge enable")
    default = repo.default_branch(top)
    if repo.current_branch(top) != default:
        repo.refuse(REFUSALS["not_default"], default=default)
    if repo.default_config(top)["merge"] == "agent":
        repo.refuse(REFUSALS["enabled"])
    branch, ref, rel = f"fix/{ENABLE}", f"origin/{default}", repo.state_path(ENABLE)
    path = story.worktrees(top).get(branch)
    if path is None:
        if repo.run("git", "show-ref", "--verify", "-q", f"refs/heads/{branch}", cwd=top).returncode == 0:
            repo.refuse(REFUSALS["taken"])
        path = story.add_worktree(top, branch, ref)
        repo.write_state(ENABLE, repo.add_step({"kind": "fix", "why": WHY, "done_when": DONE, "branch": branch,
                                                "base": repo.git("rev-parse", ref, cwd=top), "status": "started"},
                                               "start"), path)
    state = repo.read_state(ENABLE, path) or {}
    base = repo.git("merge-base", "HEAD", ref, cwd=path)
    changed = set(repo.git("diff", "--name-only", base, cwd=path).splitlines()
                  + repo.git("ls-files", "--others", "--exclude-standard", cwd=path).splitlines())
    edits = [line for line in repo.git("diff", "-U0", base, "--", "forge.toml", cwd=path).splitlines()
             if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    if ((state.get("why"), state.get("done_when")) != (WHY, DONE) or changed - {rel, "forge.toml"}
            or not all(re.fullmatch(r"[+-]merge[ \t]*=.*", line.rstrip("\r")) for line in edits)):
        repo.refuse(REFUSALS["taken"])
    repo.commit_state(f"Start the fix: {WHY}", rel, top=path)
    toml = path / "forge.toml"
    toml.write_bytes(_switched(toml.read_bytes().decode("utf-8")).encode("utf-8"))
    repo.commit_state('Set merge = "agent" in forge.toml', "forge.toml", top=path)
    close.close(argparse.Namespace(item=ENABLE, dismiss=None, because=None))
    print("Next: merge its pull request to switch on agent merges.")
    return 0


def _switched(text: str) -> str:
    """forge.toml with merge = "agent": the setting replaced, or added as a top-level key above the
    first line that isn't a comment, so before any table, in the file's own line endings."""
    new, found = re.subn(r"^merge[ \t]*=[^\r\n]*", 'merge = "agent"', text, count=1, flags=re.M)
    ending = "\r\n" if "\r\n" in text else "\n"
    return new if found else re.sub(r"^(?!#)", 'merge = "agent"' + ending, text, count=1, flags=re.M)


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
