"""Reconcile remote branch work before close chooses its review head."""
import json
import subprocess
from pathlib import Path

from forge import checks, repo, review


def replay_file(top: Path, branch: str) -> Path:
    return repo.forge_dir(top) / f"pending-replay-{branch.replace('/', '-')}.json"


def save_replay(top: Path, branch: str, original: str, lease: str) -> None:
    """Keep the rollback head and lease until the reviewed replay is published."""
    path = replay_file(top, branch)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"original": original, "lease": lease}), encoding="utf-8")
    temporary.replace(path)


def replay_baseline(top: Path, item: str, base: str, target: str, original: str) -> str:
    """A commit with the default branch's tree that counts as already holding what is not the
    part's own work: its start, the default branch, and every commit that a merge on the part's
    line took from its parent's unmerged branch. Such a commit descends from the start and
    lacks the part's own state file, which its first commit adds. Replay and merge skip all of them."""
    def has(old: str, new: str) -> bool:
        return repo.run("git", "merge-base", "--is-ancestor", old, new, cwd=top).returncode == 0

    merged = repo.git("log", "--first-parent", "--merges", "--format=%P", f"{base}..{original}", cwd=top)
    taken = [commit for line in merged.splitlines() for commit in line.split()[1:]
             if has(base, commit) and not has(commit, target)
             and repo.run("git", "cat-file", "-e", f"{commit}:{repo.state_path(item)}", cwd=top).returncode]
    parents = dict.fromkeys((base, target, *taken))
    return repo.git("-c", "user.name=Forge", "-c", "user.email=forge@localhost",
                    "commit-tree", f"{target}^{{tree}}", *(arg for parent in parents for arg in ("-p", parent)),
                    "-m", "Follow-up replay baseline", cwd=top)


def push_replay(top: Path, branch: str, tags: list[str]) -> bool:
    path = replay_file(top, branch)
    if not path.exists():
        return False
    pending = json.loads(path.read_text(encoding="utf-8"))
    published = repo.run("git", "push", "-q", "--atomic", "-u",
                         f"--force-with-lease=refs/heads/{branch}:{pending['lease']}",
                         "origin", branch, *tags, cwd=top)
    if published.returncode:
        repo.git("reset", "--keep", pending["original"], cwd=top)
        path.unlink()
        item = (review.branch_item(branch, top) or (branch, {}))[0]
        repo.refuse(("Git refused the replayed push, so Forge restored the original commits in this checkout.",
                     "check the remote branch and reconcile {branch}, then forge close {item}"),
                    branch=branch, item=item)
    path.unlink()
    return True


def reconcile(top: Path, branch: str) -> None:
    if replay_file(top, branch).exists():
        return  # Its captured lease protects the old remote history until the final push.
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
    checks.required(top, repo.default_branch(top))
