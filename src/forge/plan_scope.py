"""Task dependencies and file ownership in story plans."""
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
