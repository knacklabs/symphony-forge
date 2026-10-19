"""Advisory migration-number collisions between open work branches."""
from __future__ import annotations

import re
from pathlib import Path

from forge import board, repo, story


def before_close(top: Path) -> bool:
    """Print warnings and report whether this close refreshed origin."""
    fetched = repo.command_fact("fetched origin", top, dict)
    fresh = not fetched.get("all")
    for warning in warnings(top):
        print(warning)
    return fresh and bool(fetched.get("all"))


def fetch_default(top: Path, default: str, *, refreshed: bool) -> None:
    """Reuse the warning snapshot initially; fetch again after CI, when main can have moved."""
    if not refreshed or not repo.command_fact("fetched origin", top, dict).get("all"):
        repo.git("fetch", "-q", "origin", default, cwd=top)


def warnings(top: Path) -> list[str]:
    from forge.nextstep import branch_tips

    current = next((branch for branch, path in story.worktrees(top).items()
                    if path.resolve() == top.resolve()), "")
    default = f"origin/{repo.default_branch(top)}"
    lanes = ("task/", "fix/", "story/")
    fetched = repo.command_fact("fetched origin", top, dict)
    if not fetched.get("all"):
        result = repo.run("git", "fetch", "-q", "--prune", "origin",
                          "+refs/heads/*:refs/remotes/origin/*", cwd=top)
        if result.returncode:
            return ["Warning: Forge could not refresh origin's branches. "
                    "Check the remote and run this command again."]
        fetched["all"] = True

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
    tips = branch_tips(top)
    default = tips.get(f"refs/remotes/{default}", default)
    head = tips.get(f"refs/heads/{current}", "HEAD")
    branches = {ref.removeprefix("refs/remotes/origin/"): tip
                for ref, tip in tips.items()
                if ref.startswith(tuple(f"refs/remotes/origin/{lane}" for lane in lanes))
                and _items(ref.removeprefix("refs/remotes/origin/"))}
    if own is not None:
        branches[current] = head
    states = {(branch, item): (f"{ref}:{repo.state_path(item)}",
                              f"{default}:{repo.state_path(item)}")
              for branch, ref in branches.items() for item in _items(branch)}
    texts = board._blob_texts(top, [spec for pair in states.values() for spec in pair])
    changes, names = {}, {}
    for branch, ref in sorted(branches.items()):
        for item in _items(branch):
            peer_spec, landed_spec = states[branch, item]
            state = story.json_of(texts.get(peer_spec))
            if not state or branch.startswith("task/") and state.get("branch") != branch:
                continue
            # A squash leaves the old tip intact. Its state on main proves it landed;
            # stories keep approved JSON, so use the board's resolved completion.
            if (state.get("status") not in ("dropped", "merged", "done")
                    and (landed_spec not in texts or branch.startswith("story/")
                         and story.completed(top, item, default).get("status") != "done")):
                changes[branch] = own if own is not None and branch == current else added(ref)
                names[branch] = item
            break
    if own is not None:
        if current not in changes:
            return []
        changes = {current: changes.pop(current), **changes}

    found = []
    items = list(changes)
    for index, branch in enumerate(items):
        if own is not None and branch != current:
            break
        for other in items[index + 1:]:
            for number in sorted(changes[branch].keys() & changes[other].keys()):
                found.append(f"Warning: {names[branch]} and {names[other]} add migration number "
                             f"{changes[branch][number]}. Change one number before merge.")
    return found


def _items(branch: str) -> list[str]:
    kind, _, name = branch.partition("/")
    items = ([f"{name[:i]}/{name[i + 1:]}" for i, char in enumerate(name) if char == "-"]
             if kind == "task" else [name])
    return [item for item in items if repo.ITEM.fullmatch(item)]
