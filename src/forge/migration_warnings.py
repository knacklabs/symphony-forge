"""Advisory migration-number collisions between open work branches."""
from __future__ import annotations

import re
from pathlib import Path

from forge import board, repo, story


def warnings(top: Path) -> list[str]:
    from forge.nextstep import branch_tips

    current = repo.current_branch(top)
    default = f"origin/{repo.default_branch(top)}"
    lanes = ("task/", "fix/", "story/")

    def added(ref: str) -> dict[int, str]:
        result = repo.run("git", "diff", "--name-only", "-z", "--no-renames",
                          "--diff-filter=A", f"{default}...{ref}", "--",
                          ":(glob)**/migrations/**", cwd=top)
        numbers = {}
        if result.returncode == 0:
            for path in result.stdout.split("\0"):
                parts = path.split("/")
                if "migrations" in parts:
                    for part in parts[parts.index("migrations") + 1:]:
                        if match := re.match(r"([0-9]+)", part):
                            numbers[int(match[1])] = match[1]
                            break
        return numbers

    own = added("HEAD") if current.startswith(lanes) else None
    if own == {}:
        return []  # Most items add no migrations, so do not read their peers.
    branches = {ref.removeprefix("refs/remotes/origin/"): ref
                for ref in branch_tips(top)
                if ref.startswith(tuple(f"refs/remotes/origin/{lane}" for lane in lanes))
                and repo.ITEM.fullmatch(_item(ref.removeprefix("refs/remotes/origin/")))}
    if own is not None:
        branches.pop(current, None)
    states = {branch: f"{ref}:{repo.state_path(_item(branch))}"
              for branch, ref in branches.items()}
    texts = board._blob_texts(top, list(states.values()))
    changes = {branch: added(ref) for branch, ref in sorted(branches.items())
               if story.json_of(texts.get(states[branch])).get("status")
               not in ("dropped", "merged", "done")}
    if own is not None:
        changes = {current: own, **changes}

    found = []
    items = list(changes)
    for index, branch in enumerate(items):
        if own is not None and branch != current:
            break
        for other in items[index + 1:]:
            for number in sorted(changes[branch].keys() & changes[other].keys()):
                found.append(f"Warning: {_item(branch)} and {_item(other)} add migration number "
                             f"{changes[branch][number]}. Change one number before merge.")
    return found


def _item(branch: str) -> str:
    item = branch.split("/", 1)[1]
    return re.sub(r"-(T[0-9]+)$", r"/\1", item) if branch.startswith("task/") else item
