"""The deny hook, run before every shell command on both hosts. It blocks destructive commands,
skipped git hooks and merges. Exit code 2 blocks the command and shows the refusal to the agent."""
from __future__ import annotations

import argparse
import json
import re
import sys

from forge.repo import refuse

REFUSALS = {
    "payload": ("The hook input is not a JSON object, so Forge cannot check the command.",
                "forge doctor"),
    "destructive": ('Forge blocks "{found}" because it can destroy work that cannot be recovered.',
                    "ask the human to run it in their own terminal if it is really needed"),
    "no_verify": ('Forge blocks "{found}" because the git hooks must run on every commit and push.',
                  "run it again without skipping the hooks, and fix what they report"),
    "merge": ('Forge blocks "{found}" because only a human merges a pull request.',
              "forge close <item>, then ask the human to merge"),
}

RULES = {
    # Carried over unchanged from the old hook's denylist (factory/scripts/pre_tool_use.py).
    "destructive": [r"\brm\s+-rf\b", r"\bgit\s+reset\s+--hard\b", r"\bgit\s+push\s+--force\b",
                    r"\bterraform\s+destroy\b", r"\bkubectl\s+delete\b"],
    # -n is git commit's short --no-verify.
    # ponytail: a commit message holding " -n" is blocked too; reword it.
    "no_verify": [r"--no-verify\b", r"\bgit\s+commit\b[^;&|\n]*\s-[A-Za-z]*n"],
    "merge": [r"\bgh\s+pr\s+merge\b"],
}


def hook(args: argparse.Namespace) -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError:
        payload = None
    if not isinstance(payload, dict):  # fail closed: a command Forge can't read doesn't run
        refuse(REFUSALS["payload"], code=2)
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if isinstance(command, list):  # ponytail: an argv-shaped command, should a host send one
        command = " ".join(map(str, command))
    for rule, patterns in RULES.items():
        for pattern in patterns:
            found = re.search(pattern, str(command or ""))
            if found:
                refuse(REFUSALS[rule], code=2, found=found[0])
