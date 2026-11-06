"""Reconcile remote branch work before close chooses its review head."""
import subprocess
from pathlib import Path

from forge import repo, review


def reconcile(top: Path, branch: str) -> None:
    target = f"refs/remotes/origin/{branch}"
    found = repo.run("git", "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}", cwd=top)
    if found.returncode == 2:  # This branch has not been published yet.
        return
    if found.returncode:
        raise subprocess.CalledProcessError(found.returncode, found.args, found.stdout, found.stderr)
    repo.git("fetch", "-q", "origin", f"+refs/heads/{branch}:{target}", cwd=top)
    if not repo.run("git", "merge-base", "--is-ancestor", target, "HEAD", cwd=top).returncode:
        return
    same = repo.git("rev-parse", "HEAD^{tree}", cwd=top) == repo.git(
        "rev-parse", f"{target}^{{tree}}", cwd=top)
    print("The local and remote branches diverged, as after an amended or rebased commit. "
          + ("Their trees are the same." if same else "Their trees differ."), flush=True)
    merged = repo.run("git", "merge", "--no-edit", target, cwd=top)
    if merged.returncode:
        files = repo.git("diff", "--name-only", "--diff-filter=U", cwd=top).splitlines()
        if files:
            item = (review.branch_item(branch, top) or (branch, {}))[0]
            repo.refuse(("The merge of the remote branch conflicts in {files}.",
                         "in {path}, resolve the conflicts and commit the merge, then forge close {item}"),
                        files=", ".join(files), path=top, item=item)
        repo.refuse(("The merge of the remote branch failed: {problem}",
                     "in {path}, finish or abort the merge, then retry this command"),
                    problem=merged.stderr.strip(), path=top)
