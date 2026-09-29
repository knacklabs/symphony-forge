"""`forge spec payback`: whether a build pays back, from rounded numbers, the same every time.

Months are the build's cost over the weighted monthly value, in exact fractions, so the edges
at three and twelve months never drift. It changes nothing, so it runs anywhere.
"""
from __future__ import annotations

import argparse
import math
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from forge import repo

REFUSALS = {
    "missing": ("A payback needs {missing}.", "forge spec payback --help"),
    "not_number": ("{flag} is {value!r}, and it needs a number of zero or more.",
                   "forge spec payback --help"),
    "chance": ("--incident-chance is {value}, and it needs a chance from 0 to 1.",
               "forge spec payback --help"),
}

# The value groups add up: people's time saved, revenue, and incidents avoided.
VALUE_GROUPS = (("hours_per_month", "people", "hourly_rate"), ("revenue_per_month",),
                ("incident_cost", "incident_chance"))
BUILD = ("build_days", "day_rate")
WEIGHTS = {"measured": Fraction(1), "estimated": Fraction(1, 2), "guessed": Fraction(1, 5)}


def _flag(name: str) -> str:
    return "--" + name.replace("_", "-")


def _number(args: argparse.Namespace, name: str) -> Fraction:
    value = getattr(args, name)
    try:
        number = Decimal(value)
    except InvalidOperation:
        number = Decimal("NaN")
    if not number.is_finite() or number < 0:
        repo.refuse(REFUSALS["not_number"], flag=_flag(name), value=value)
    return Fraction(number)


def _group(args: argparse.Namespace, names: tuple[str, ...]) -> list[Fraction] | None:
    """The group's numbers, None when none of it is given; refuses a partly given group."""
    missing = [name for name in names if getattr(args, name) is None]
    if len(missing) == len(names):
        return None
    if missing:
        repo.refuse(REFUSALS["missing"], missing=" and ".join(map(_flag, missing)))
    return [_number(args, name) for name in names]


def _months(months: Fraction) -> str:
    """Months to one decimal, halves to even."""
    return f"{float(round(months, 1)):.1f}"


def answer(args: argparse.Namespace) -> str:
    groups = [group for names in VALUE_GROUPS if (group := _group(args, names)) is not None]
    build = _group(args, BUILD)
    if not groups:
        return "find out first"
    if build is None:
        repo.refuse(REFUSALS["missing"], missing=" and ".join(map(_flag, BUILD)))
    if args.incident_chance is not None and _number(args, "incident_chance") > 1:
        repo.refuse(REFUSALS["chance"], value=args.incident_chance)
    value = sum(map(math.prod, groups)) * WEIGHTS[args.confidence]
    if value == 0:
        return "don't build: no monthly value"
    months = math.prod(build) / value
    verdict = ("build" if months <= 3 else "smallest slice first" if months <= 12
               else "don't build")
    return f"{verdict}: {_months(months)} months"


def payback(args: argparse.Namespace) -> None:
    print(answer(args))


COMMANDS = [{
    "words": "spec payback", "run": "payback", "changes_state": False,
    "help": "Say whether a build pays back: build, smallest slice first, don't build or find out first",
    "args": [(('--build-days',), {"metavar": "DAYS"}),
             (('--day-rate',), {"metavar": "AMOUNT"}),
             (('--hours-per-month',), {"metavar": "HOURS", "help": "hours saved per person each month"}),
             (('--people',), {"metavar": "COUNT"}),
             (('--hourly-rate',), {"metavar": "AMOUNT"}),
             (('--revenue-per-month',), {"metavar": "AMOUNT"}),
             (('--incident-cost',), {"metavar": "AMOUNT"}),
             (('--incident-chance',), {"metavar": "CHANCE", "help": "the chance each month, from 0 to 1"}),
             (('--confidence',), {"choices": ("measured", "estimated", "guessed"),
                                   "default": "guessed", "help": "weighs the value by 1, 1/2 or 1/5 (default: guessed)"})],
    "position": 200,
    "listing": "| `forge spec payback --build-days <n> --day-rate <n> <value>` | Says whether a build pays back: build (three months or less), smallest slice first (up to twelve), don't build, or find out first when no value can be estimated. The value is any of `--hours-per-month`, `--people` and `--hourly-rate`; `--revenue-per-month`; `--incident-cost` and `--incident-chance`, weighed by `--confidence measured`, `estimated` or `guessed` (the default). Use rounded rates, never real salaries. It changes nothing |",
}]
