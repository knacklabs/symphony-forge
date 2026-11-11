"""Run the shared, model-free design checks on changed client files."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from forge import repo


def problems(top: Path, files: list[str]) -> list[str]:
    from forge import sync

    files = [file for file in files if Path(file).suffix.lower() in
             {".tsx", ".jsx", ".html", ".css", ".vue", ".svelte"} and (top / file).is_file()]
    if not files:
        return []
    node = shutil.which("node")
    if not node:
        print("The design checks did not run because Node is not installed.")
        return []
    checked = repo.run(node, str(sync.TEMPLATES / "design/ui-checks.js"),
                       input=json.dumps(files), cwd=top)
    if checked.returncode:
        return [f"ui-checks.js:1 design-checker: {checked.stderr.strip()}"]
    result = json.loads(checked.stdout)
    if result.get("note"):
        print(result["note"])
    return result["problems"]


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    return {f".forge/design/{name}": (sync.TEMPLATES / "design" / name).read_text(encoding="utf-8")
            for name in ("ui-checks.js", "render-check.mjs", "render-check.d.mts")}
