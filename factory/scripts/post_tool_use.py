#!/usr/bin/env python3
"""Fail-open adapter for successful native Plan Mode approval events."""
from __future__ import annotations

import json

from factory_lib import read_stdin_utf8, repo_root
from forge_cli.approval import ApprovalRefused, record_native_approval


def _tell_host(message: str) -> None:
    # A silent refusal left approvals unrecorded with no trace; always say which.
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": message,
    }}))


def _tell_refusal(payload: dict, exc: BaseException) -> None:
    shape = {key: sorted(value) if isinstance(value, dict) else type(value).__name__
             for key in ("tool_input", "tool_response")
             for value in [payload.get(key)]}
    _tell_host(f"Forge did NOT record this plan approval: "
               f"{type(exc).__name__}: {exc} (payload shape: {shape})")


def main() -> None:
    try:
        payload = json.loads(read_stdin_utf8())
        if not isinstance(payload, dict):
            return
        tool = payload.get("tool_name")
        if tool == "ExitPlanMode":
            recorded_in: list[str] = []
            try:
                record = record_native_approval(
                    repo_root(), payload, runtime="claude",
                    recorded_in=recorded_in,
                )
            except (ApprovalRefused, Exception, SystemExit) as exc:
                _tell_refusal(payload, exc)
                return
            _tell_host(f"Forge recorded native {record['plan_kind']} plan approval "
                       f"{record['approved_plan_sha256']} in worktree "
                       f"{recorded_in[0]}.")
        elif tool == "request_user_input":
            tool_input = payload.get("tool_input")
            questions = (
                tool_input.get("questions", [])
                if isinstance(tool_input, dict) else []
            )
            if (not isinstance(questions, list) or not any(
                    isinstance(question, dict)
                    and str(question.get("id", "")).startswith("approve_plan_")
                    for question in questions)):
                return
            recorded_in = []
            try:
                record = record_native_approval(
                    repo_root(), payload, runtime="codex",
                    recorded_in=recorded_in,
                )
            except (ApprovalRefused, Exception, SystemExit) as exc:
                _tell_refusal(payload, exc)
            else:
                _tell_host(
                    f"Forge recorded native {record['plan_kind']} plan approval "
                    f"{record['approved_plan_sha256']} in worktree "
                    f"{recorded_in[0]}."
                )
    except (ApprovalRefused, Exception, SystemExit):
        return


if __name__ == "__main__":
    main()
