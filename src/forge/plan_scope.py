"""Task dependencies and file ownership in story plans."""
import re
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


def shared_files(tasks: list[dict[str, Any]]) -> list[str]:
    """One advice line per file that three or more parts list by its exact path. Folders, globs
    and test paths are not counted; other stories are not looked at."""
    owners: dict[str, list[str]] = {}
    for task in tasks:
        for path in dict.fromkeys(re.split(r"[`\s]", entry)[0] for entry in task["scope"]):  # drop "(note)"
            if not re.search(r"[*?[]|/$", path) and not {"tests", "test", "__tests__", "spec"} & set(path.split("/")):
                owners.setdefault(path, []).append(task["id"])
    return [f"Shared file: {len(ids)} parts of this plan list {path} in their Scope ({', '.join(ids)}). "
            "Forge builds them one after another. If a script can make this file when the app is built, "
            "make it at build time and take it out of every Scope. If the repo keeps it on purpose, "
            "put its change in one first part that the other parts wait for."
            for path, ids in owners.items() if len(ids) >= 3]


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
