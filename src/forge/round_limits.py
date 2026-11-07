"""Validate a configured cold-read or task-review limit."""


def problem(key: str, value: object) -> str:
    if type(value) is not int or value not in (1, 2):
        return f"{key} must be 1 or 2"
    return ""
