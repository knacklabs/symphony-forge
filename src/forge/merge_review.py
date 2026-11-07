"""Keep a clean review and isolate changes to Git's merge of its reviewed head."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from forge import repo


def base(top: Path, item: str, state: dict[str, Any], target: str,
         previous: dict[str, Any]) -> str:
    """Return a synthetic base only when the earlier review still covers its inputs."""
    from forge import review

    reviewed = previous.get("commit")
    if (not reviewed or "skipped" in previous or review.blocking(previous)
            or state.get("stacked_on") or target.startswith("forge-stack/")):
        return ""
    if previous.get("blocking_level") == "P0" and review.blocking_level(top, item, state, target) != "P0":
        return ""
    if repo.run("git", "merge-base", "--is-ancestor", reviewed, "HEAD", cwd=top).returncode:
        return ""
    incoming = repo.git("merge-base", target, "HEAD", cwd=top)
    if repo.run("git", "merge-base", "--is-ancestor", incoming, reviewed, cwd=top).returncode == 0:
        return ""
    old_base = repo.git("merge-base", target, reviewed, cwd=top)
    if "/" in item:
        key = item.split("/", 1)[0]
        if repo.run("git", "show", f"{reviewed}:plans/{key}.md", cwd=top).stdout != review.task(top, item)[0]:
            return ""
        def entry(commit: str) -> Any:
            shown = repo.run("git", "show", f"{commit}:plans/roadmap.json", cwd=top)
            items = json.loads(shown.stdout).get("items", []) if shown.returncode == 0 else []
            return next((value for value in items if value.get("key") == key), {})
        if entry(reviewed) != entry("HEAD"):
            return ""
    else:
        shown = repo.run("git", "show", f"{reviewed}:{repo.state_path(item)}", cwd=top)
        if shown.returncode:
            return ""
        saved = json.loads(shown.stdout)
        if any(saved.get(key, "") != state.get(key, "") for key in ("why", "done_when")):
            return ""
    if (review.before_coding(top, old_base, reviewed) != review.before_coding(top, old_base)
            or any(review.commit_paragraph(top, old_base, label, reviewed) !=
                   review.commit_paragraph(top, old_base, label)
                   for label in ("Functional check:", "Proof list:"))):
        return ""
    merged = repo.run("git", "merge-tree", "--write-tree", "--no-messages", reviewed, incoming, cwd=top)
    if merged.returncode not in (0, 1):
        merged.check_returncode()
    # A separate index leaves the worker's staged changes untouched.
    with tempfile.TemporaryDirectory(prefix="forge-merge-review-") as folder:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(folder) / "index")}
        repo.run("git", "read-tree", merged.stdout.splitlines()[0], cwd=top, env=env).check_returncode()
        repo.run("git", "reset", "-q", "HEAD", "--", ".factory", "plans",
                 cwd=top, env=env).check_returncode()
        tree = repo.run("git", "write-tree", cwd=top, env=env)
        tree.check_returncode()
    return repo.git("commit-tree", tree.stdout.strip(), "-p", reviewed,
                    "-m", "Earlier review merged with the default branch", cwd=top)


def covers(top: Path, item: str, state: dict[str, Any], target: str,
           previous: dict[str, Any]) -> bool:
    from forge import review

    merged = base(top, item, state, target, previous)
    if not merged:
        return False
    files = repo.git("diff", "--name-only", "-z", merged, "HEAD", cwd=top).split("\0")
    return not any(path and not path.startswith(review.BOOKKEEPING) for path in files)
