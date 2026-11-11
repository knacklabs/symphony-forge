"""Task dependencies and file ownership in story plans."""
import re
from pathlib import Path
from typing import Any

from forge import repo


def check(tasks: list[dict[str, Any]]) -> None:
    from forge.task import _overlap

    by_id = {task["id"]: task for task in tasks}

    def waits(task: str, other: str) -> bool:
        return any(after == other or (after in by_id and waits(after, other))
                   for after in by_id[task]["after"])

    for index, first in enumerate(tasks):
        for second in tasks[index + 1:]:
            if waits(first["id"], second["id"]) or waits(second["id"], first["id"]):
                continue
            for left in first["scope"]:
                for right in second["scope"]:
                    if _overlap(left, right):
                        repo.refuse((
                            f"Tasks {first['id']} and {second['id']} can change the same file "
                            f"({left}, {right}).",
                            "name separate files in Scope, add an After link, "
                            "or put the shared file in a first task that both wait for."))


def say(text: str, top: Path) -> None:
    """Print one advice line per file that three or more parts of this plan list by its exact path.
    It reads only this plan's own Scope cells and never fails or refuses: other stories are not
    looked at, and a problem anywhere means no note."""
    try:
        from forge.story import parse
        tasks = parse(text)["tasks"]  # no checkout given, so After entries of other stories are not resolved
        scopes = {task["id"]: list(dict.fromkeys(re.split(r"[`\s]", entry)[0] for entry in task["scope"]))
                  for task in tasks}  # the cut drops a trailing "(note)"
        every = {path for paths in scopes.values() for path in paths}
        owners: dict[str, list[str]] = {}
        for task, paths in scopes.items():
            for path in paths:
                # A file by its exact path. A folder is a "/" ending, an existing directory, or a path
                # that another entry lists files under (the overlap check's prefix rule). Test paths never count.
                if (not re.search(r"[*?[]|/$", path) and not {"tests", "test", "__tests__", "spec"} & set(path.split("/"))
                        and not (top / path).is_dir() and not any(other.startswith(path + "/") for other in every)):
                    owners.setdefault(path, []).append(task)
        lines = [f"Shared file: {len(ids)} parts of this plan list {path} in their Scope ({', '.join(ids)}). "
                 "Forge builds them one after another. If a script can make this file when the app is built, "
                 "make it at build time and take it out of every Scope. If the repo keeps it on purpose, "
                 "put its change in one first part that the other parts wait for."
                 for path, ids in owners.items() if len(ids) >= 3]
    except Exception:  # ponytail: this is advice, so whatever goes wrong means no note
        return
    for line in lines:
        print(line)


def no_cycle(tasks: dict[str, dict[str, Any]]) -> None:
    checked: set[str] = set()

    def visit(task: str, path: list[str]) -> None:
        if task in path:
            loop = " -> ".join(path[path.index(task):] + [task])
            raise ValueError(f"Tasks row {task}: its After list makes a cycle ({loop})")
        if task not in checked:
            for after in tasks[task]["after"]:
                # ponytail: a cycle across stories isn't caught; its tasks just wait in forge next
                if "/" not in after:
                    visit(after, path + [task])
            checked.add(task)

    for task in tasks:
        visit(task, [])
