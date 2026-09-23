#!/usr/bin/env python3
"""Fail-open adapter for successful native Plan Mode approval events."""
from __future__ import annotations

import json

from factory_lib import read_stdin_utf8, repo_root
from forge_cli.approval import ApprovalRefused, record_native_approval


def _tell_claude(message: str) -> None:
    # A silent refusal left approvals unrecorded with no trace; always say which.
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": message,
    }}))


def main() -> None:
    try:
        payload = json.loads(read_stdin_utf8())
        if not isinstance(payload, dict):
            return
        tool = payload.get("tool_name")
        if tool == "ExitPlanMode":
            try:
                record = record_native_approval(repo_root(), payload, runtime="claude")
            except (ApprovalRefused, Exception, SystemExit) as exc:
                shape = {key: sorted(value) if isinstance(value, dict) else type(value).__name__
                         for key in ("tool_input", "tool_response")
                         for value in [payload.get(key)]}
                _tell_claude(f"Forge did NOT record this plan approval: "
                             f"{type(exc).__name__}: {exc} (payload shape: {shape})")
                return
            _tell_claude(f"Forge recorded native {record['plan_kind']} plan approval "
                         f"{record['approved_plan_sha256']}.")
        elif tool == "request_user_input":
            record_native_approval(repo_root(), payload, runtime="codex")
    except (ApprovalRefused, Exception, SystemExit):
        return


if __name__ == "__main__":
    main()
