#!/usr/bin/env python3
"""Fail-open adapter for successful native Plan Mode approval events."""
from __future__ import annotations

import json

from factory_lib import read_stdin_utf8, repo_root
from forge_cli.approval import ApprovalRefused, record_native_approval


def main() -> None:
    try:
        payload = json.loads(read_stdin_utf8())
        if not isinstance(payload, dict):
            return
        tool = payload.get("tool_name")
        if tool == "ExitPlanMode":
            record_native_approval(repo_root(), payload, runtime="claude")
        elif tool == "request_user_input":
            record_native_approval(repo_root(), payload, runtime="codex")
    except (ApprovalRefused, Exception, SystemExit):
        return


if __name__ == "__main__":
    main()
