"""forge fix — launch a bounded write companion inside an open lite window."""
from __future__ import annotations

import argparse
from pathlib import Path

from factory_lib import repo_root

from .common import fail
from .delegate import brief_path, launch_companion, mode_run_config
from .quickfix import LITE, _lite_manifest, load_active, profile_of, record_files
from .stages import task_digest


def _brief(window: dict, description: str) -> str:
    return (
        f"# Lite fix — {window['id']}\n\n"
        f"Fix: {description}\n\n"
        "Work only on this bounded fix inside the open lite window. "
        "Do not create a git commit. Run the smallest relevant checks, "
        "then report the files changed and results.\n"
    )


def cmd_fix(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    description = args.description.strip()
    if not description:
        fail("forge fix needs a description")
    window = load_active(base)
    if not window or profile_of(window) != LITE:
        fail("forge fix requires an open lite window — run `./forge mode lite` first")

    model, effort, bound = mode_run_config(base, LITE)
    if window.get("max_files") != bound:
        fail(f"the open lite window does not match modes.lite bound {bound}")
    contract = {
        "acceptance_criteria": [description],
        "required_tests": [],
        "verify_commands": [],
        "write_scope": [],
    }
    try:
        launch_companion(
            base,
            task_id=window["id"],
            text=_brief(window, description),
            path=brief_path(base, window["id"]),
            task_sha256_value=task_digest(contract),
            model=model,
            effort=effort,
            write=True,
            mode=LITE,
        )
    finally:
        record_files(base, _lite_manifest(base, window["base_sha"]))
