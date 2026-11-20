"""Reconcile remote branch work before close chooses its review head."""
import json
import os
import subprocess
import tempfile
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


def squash_replay(top: Path, baseline: str, original: str, target: str, tree: str) -> str:
    """Keep record snapshots before one product commit, with all worker messages.

    Review history reads first-parent snapshots. Fixes also need their start record
    before the product work, so a teammate can still recognise a completed build.
    """
    commits = repo.git("rev-list", "--reverse", "--first-parent", f"{baseline}..{original}",
                       cwd=top).splitlines()
    messages, parent = [], target
    with tempfile.TemporaryDirectory() as folder:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(folder) / "index")}
        repo.git("read-tree", target, cwd=top, env=env)
        for sha in commits:
            message = repo.git("show", "-s", "--format=%B", sha, cwd=top)
            messages.append(message)
            paths = repo.git("diff", "--name-only", "-z", f"{sha}^", sha, "--",
                             ".factory", "plans", cwd=top).rstrip("\0").split("\0")
            if not paths[0]:
                continue
            for path in paths:
                entry = repo.git("ls-tree", sha, "--", path, cwd=top)
                if entry:
                    updated = repo.run("git", "update-index", "--index-info", input=entry + "\n",
                                       cwd=top, env=env)
                    updated.check_returncode()
                else:
                    repo.git("update-index", "--force-remove", "--", path, cwd=top, env=env)
            snapshot = repo.git("write-tree", cwd=top, env=env)
            saved = repo.run("git", "commit-tree", snapshot, "-p", parent,
                             input=message, cwd=top)
            saved.check_returncode()
            parent = saved.stdout.strip()
    saved = repo.run("git", "commit-tree", tree, "-p", parent, cwd=top,
                     input="Replay the part's final changes\n\n" + "\n\n".join(reversed(messages)))
    saved.check_returncode()
    return saved.stdout.strip()


def push_replay(top: Path, branch: str, tags: list[str]) -> bool:
    path = replay_file(top, branch)
    if not path.exists():
        return False
    pending = json.loads(path.read_text(encoding="utf-8"))
    # Earlier review rounds cite commits that the replay drops. This tag lets another machine
    # read them. It is made here, since a fetch that prunes tags would remove an unpushed one.
    kept = f"refs/tags/forge-replayed/{branch}/{pending['original']}"
    repo.git("update-ref", kept, pending["original"], cwd=top)
    published = repo.run("git", "push", "-q", "--atomic", "-u",
                         f"--force-with-lease=refs/heads/{branch}:{pending['lease']}",
                         "origin", branch, *tags, kept, cwd=top)
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
