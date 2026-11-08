"""Resolve the timing inventory when it is the only default-merge conflict."""
import json
import os
import tempfile
from pathlib import Path

from forge import repo


def resolve(top: Path, *, tree: str = "", files: list[str] | None = None,
            ours: str = ":2", incoming: str = ":3", replay: bool = False) -> str:
    """Return the resolved tree, or leave the caller's existing conflict stop in charge.

    Replay trials use an isolated index. During rebase stage two is the default
    branch, so that caller reverses the inputs. A rejected commit returns failure
    while the merge/rebase still exists, allowing the caller to abort it.
    """
    while True:
        conflicts = files if tree else repo.git("diff", "--name-only", "--diff-filter=U", cwd=top).splitlines()
        if conflicts != [".test_durations"]:
            return ""
        try:
            local, default = (json.loads(repo.git("show", f"{ref}:.test_durations", cwd=top))
                              for ref in (ours, incoming))
        except ValueError:
            return ""
        if not isinstance(local, dict) or not isinstance(default, dict):
            return ""
        text = json.dumps(local | default, sort_keys=True, indent=4) + "\n"
        if tree:
            with tempfile.TemporaryDirectory() as folder:
                env = {**os.environ, "GIT_INDEX_FILE": str(Path(folder) / "index")}
                repo.git("read-tree", tree, cwd=top, env=env)
                blob = repo.run("git", "hash-object", "-w", "--stdin", input=text, cwd=top)
                blob.check_returncode()
                repo.git("update-index", "--cacheinfo", "100644", blob.stdout.strip(),
                         ".test_durations", cwd=top, env=env)
                return repo.git("write-tree", cwd=top, env=env)
        (top / ".test_durations").write_text(text, encoding="utf-8", newline="\n")
        repo.git("add", "--", ".test_durations", cwd=top)
        done = (repo.run("git", "-c", "core.editor=true", "rebase", "--continue", cwd=top) if replay
                else repo.run("git", "commit", "-q", "--no-edit", cwd=top))
        if not done.returncode:
            return repo.git("write-tree", cwd=top)
        if not replay:
            return ""
