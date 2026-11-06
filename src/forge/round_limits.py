"""The configurable limits for cold reads and task reviews."""

KEYS = {"cold_read_rounds": int, "task_review_rounds": int}
DEFAULTS = {"cold_read_rounds": 2, "task_review_rounds": 2}


def problem(key: str, value: object) -> str:
    if key in KEYS and (type(value) is not int or value not in (1, 2)):
        return f"{key} must be 1 or 2"
    return ""
