"""forge fix — launch a bounded write companion inside an open lite window."""
from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path

from factory_lib import ledger_dir, load_json, load_review_artifacts, repo_root

from .common import fail
from .delegate import brief_path, launch_companion, mode_run_config
from .quickfix import (
    LITE, _lite_dirty_product_files, _lite_manifest, _lite_product_files,
    cmd_mode_done, ledger_path, load_active, profile_of, record_files,
)
from .stages import task_digest


def _brief(window: dict, description: str,
           refactor_files: list[str] | None = None) -> str:
    text = (
        f"# Lite fix — {window['id']}\n\n"
        f"Fix: {description}\n\n"
        "Work only on this bounded fix inside the open lite window. "
        "Do not create a git commit. Run the smallest relevant checks, "
        "then report the files changed and results.\n"
    )
    if refactor_files:
        text += "\n" + "\n".join(
            f"Refactor {file}: replace the approach with one simpler rule."
            for file in refactor_files
        ) + "\n"
    return text


def cmd_fix(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    description = args.description.strip()
    if not description:
        fail("forge fix needs a description")
    window = load_active(base)
    if not window or profile_of(window) != LITE:
        fail("forge fix requires an open lite window — run `./forge mode lite` first")
    if getattr(args, "resume_close", False):
        if not getattr(args, "close", False):
            fail("--resume-close requires --close")
        finish_fix_close(
            base, description,
            window_id=getattr(args, "window_id", None) or window["id"],
        )
        return
    if getattr(args, "window_id", None):
        fail("--window-id is only valid with --resume-close")

    model, effort, bound = mode_run_config(base, LITE)
    if window.get("max_files") != bound:
        fail(f"the open lite window does not match modes.lite bound {bound}")
    from . import findings
    choice = getattr(args, "choice", None)
    repeated_files = findings.repeated_finding_files(
        base, "", str(window.get("id") or ""), lite=True,
    )
    refusal = findings.choice_error(repeated_files, choice)
    if refusal:
        fail(refusal)
    from .codex_runtime import coordinator_runtime
    native = coordinator_runtime() == "codex"
    contract = {
        "acceptance_criteria": [description],
        "required_tests": [],
        "verify_commands": [],
        "write_scope": [],
    }
    result = None
    try:
        result = launch_companion(
            base,
            task_id=window["id"],
            text=_brief(window, description,
                        repeated_files if choice == "refactor" else None),
            path=brief_path(base, window["id"]),
            task_sha256_value=task_digest(contract),
            model=model,
            effort=effort,
            write=True,
            write_scope=[] if native else None,
            mode=LITE,
            choice=choice,
        )
    finally:
        # Record what terra just touched — its writes are uncommitted, so this
        # is the working-tree manifest. `mode done` re-measures the committed
        # base_sha..HEAD diff for the budget and the final ledger record.
        if not (isinstance(result, dict)
                and result.get("transport") == "host-native"):
            record_files(base, _lite_dirty_product_files(base))
    if isinstance(result, dict) and result.get("action") == "spawn_agent":
        close_step = (
            " After it succeeds, run `./forge fix "
            f"{shlex.quote(description)} --close --resume-close "
            f"--window-id {shlex.quote(window['id'])}` to continue."
            if getattr(args, "close", False) else
            " After the subagent finishes, inspect its changes and run `./forge mode done`."
        )
        print(
            "NEXT: dispatch the printed descriptor with the host's spawn_agent "
            "tool (or followup_task when that task name is already live)." + close_step
        )
        return
    if getattr(args, "close", False):
        finish_fix_close(base, description, window_id=window["id"], record=False)


def finish_fix_close(
        base: Path, description: str, *, window_id: str | None = None,
        record: bool = True) -> None:
    """Commit, review and close a Lite fix after its worker has completed.

    Native Codex workers run under the host, so the host calls this only after
    receiving their completion. Synchronous companion launches call it here.
    """
    window = load_active(base)
    if not window or profile_of(window) != LITE:
        fail("forge fix --close requires the Lite window to remain open")
    if window_id is not None and window.get("id") != window_id:
        fail("the open Lite window changed while the fix worker was running")
    window_id = str(window["id"])
    if record:
        record_files(base, _lite_dirty_product_files(base))

    from .tasks import _require_git

    dirty = _lite_dirty_product_files(base)
    products = [
        path for path in _lite_product_files(
            base, dirty, harness_source=window.get("harness_source"),
        )
        if Path(path).parts[0] not in {".factory", "plans"}
    ]
    if products:
        subject = description.splitlines()[0]
        sentence_end = re.search(r"[.!?](?=\s|$)", subject)
        if sentence_end:
            subject = subject[:sentence_end.end()]
        if len(subject) > 72:
            subject = subject[:69] + "..."
        _require_git(base, "staging Lite product changes", "add", "--", *products)
        _require_git(
            base, "committing Lite product changes", "commit", "-q", "--only",
            "-m", subject, "-m", description, "-m", f"Ticket: {window_id}",
            "--", *products,
        )
    elif not _lite_manifest(
        base,
        window["base_sha"],
        harness_source=window.get("harness_source"),
    ):
        print(f"No product changes to commit; Lite window {window_id} remains open.")
        return

    from .review import review_lite

    review_lite(base)
    reviews, review_problems = load_review_artifacts(
        base, require_head=True, blockers_only=True,
    )
    blocking = [
        (aspect, finding)
        for aspect, artifact in reviews.items()
        for finding in artifact.get("blocking_findings") or []
    ]
    if blocking:
        print(f"Blocking Lite findings; window {window_id} remains open:")
        for aspect, finding in blocking:
            print(f"- {aspect}: {_finding_text(finding)}")
        return
    if review_problems:
        fail("Lite review needs current complete artifacts:\n- "
             + "\n- ".join(review_problems))

    for aspect, artifact in reviews.items():
        for finding in artifact.get("non_blocking_findings") or []:
            print(
                f"{aspect}: {_finding_text(finding)} — accepted; log with "
                "`forge defer add` if they matter"
            )

    cmd_mode_done(argparse.Namespace(repo=str(base)))
    records = []
    for path in ledger_dir(ledger_path(base)).glob("*.json"):
        if not path.is_file() or path.is_symlink():
            continue
        event = load_json(path, default={})
        if isinstance(event, dict) and event.get("id") == window_id:
            records.append(path)
    records.sort()
    relative = [path.relative_to(base).as_posix() for path in records]
    if relative:
        _require_git(base, "staging Lite window records", "add", "--", *relative)
        _require_git(
            base, "committing Lite window records", "commit", "-q", "--only",
            "-m", f"Lite window {window_id} done", "-m", f"Ticket: {window_id}",
            "--", *relative,
        )


def _finding_text(finding: object) -> str:
    if isinstance(finding, dict):
        summary = finding.get("summary")
        if isinstance(summary, str) and summary:
            path = finding.get("file_path")
            line = finding.get("line")
            if isinstance(path, str) and path:
                return f"{path}:{line}: {summary}" if line else f"{path}: {summary}"
            return summary
        return json.dumps(finding, sort_keys=True)
    return str(finding)
