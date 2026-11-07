"""Resolve the timing inventory when it is the only default-merge conflict."""
import json
from pathlib import Path

from forge import repo


def resolve(top: Path) -> bool:
    if repo.git("diff", "--name-only", "--diff-filter=U", cwd=top).splitlines() != [".test_durations"]:
        return False
    try:
        ours, incoming = (json.loads(repo.git("show", f":{stage}:.test_durations", cwd=top))
                          for stage in (2, 3))
    except ValueError:
        return False
    if not isinstance(ours, dict) or not isinstance(incoming, dict):
        return False
    (top / ".test_durations").write_text(
        json.dumps(ours | incoming, sort_keys=True, indent=4) + "\n", encoding="utf-8", newline="\n")
    repo.git("add", "--", ".test_durations", cwd=top)
    repo.git("commit", "-q", "--no-edit", cwd=top)
    return True
