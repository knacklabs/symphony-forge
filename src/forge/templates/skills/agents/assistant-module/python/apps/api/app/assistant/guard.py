import re

SECRET_MESSAGE = "Please remove passwords, card numbers and one-time codes before you send this message."

_LABELLED_SECRET = re.compile(
    r"\b(?:password|passwd|pwd|api[_ -]?key|secret|one[ -]?time[ -]?(?:code|password)|otp)"
    r"[\"']?\s*(?:[:=]|\bis\b|\s)\s*[\"']?\S+",
    re.IGNORECASE,
)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def contains_secret(text: str) -> bool:
    # ponytail: unlabelled passwords cannot be recognized; use a secure form.
    if _LABELLED_SECRET.search(text):
        return True
    for candidate in _CARD.finditer(text):
        digits = [int(char) for char in candidate.group() if char.isdigit()]
        doubled = [digit * 2 for digit in digits[-2::-2]]
        total = sum(digits[-1::-2]) + sum(
            value - 9 if value > 9 else value for value in doubled
        )
        if total % 10 == 0:
            return True
    return False
