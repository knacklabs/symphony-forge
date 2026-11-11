"""Run the shared, model-free design checks on changed client files."""
from __future__ import annotations

import json
import re
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


APP_THEME, APPROVED_THEME = "apps/web/src/index.css", "docs/design/tokens.json"
NOT_SCREEN = {"tests", "test", "__tests__"}
THEME_RULES = {":root", ".dark", "@theme", "@theme inline"}


def _screen(file: str) -> bool:
    path = Path(file)
    return (path.parts[0] in {"apps", "libs"} and path.suffix.lower() in {".tsx", ".jsx", ".html", ".css", ".vue", ".svelte"}
            and not NOT_SCREEN & set(path.parts) and path.parts[-3:-1] != ("components", "ui")
            and ".test." not in path.name and ".spec." not in path.name)


def theme(top: Path, files: list[str]) -> list[str]:
    """Report each theme value of the app that differs from the approved copy."""
    # Close publishes the committed head, so both files are read from it, not from the worktree.
    text, copy = (repo.read_blob(top, f"HEAD:{path}") for path in (APP_THEME, APPROVED_THEME))
    if text is None or copy is None:
        return []
    if not {APP_THEME, APPROVED_THEME}.intersection(files) and not any(file and _screen(file) for file in files):
        return []
    try:
        tokens = json.loads(copy)
        wanted = [(t["name"], theme, t["value"][theme]) for t in tokens["color"]["tokens"]
                  for theme in ("light", "dark")]
        wanted += [(f"font-{key}", "", stack) for key, stack in tokens["type"]["families"].items()]
        wanted += [(s["name"], "", s["fontSize"]) for g in tokens["type"]["groups"] for s in g["styles"]]
        wanted += [(t["name"], "", t["value"]) for kind in ("radius", "spacing", "shadow") for t in tokens[kind]["tokens"]]
    except (ValueError, KeyError, TypeError):
        return [f"{APPROVED_THEME}:1 theme-drift: the approved copy is not valid JSON or has no color section."]
    waived = {" ".join(m.split()) for m in re.findall(r"/\*\s*forge-ui-ignore\s+theme-drift\s+(.+?):\s*(?!\*/)\S[\s\S]*?\*/", text)}
    text = re.sub(r"/\*[\s\S]*?\*/", lambda m: re.sub(r"[^\n]", " ", m[0]), text)
    found: dict[tuple[str, str], tuple[int, str]] = {}
    rules, head = [], 0  # The open rules' selectors; a declaration belongs to the innermost one.
    for mark in re.finditer(r"[{};]", text):
        if mark[0] == "{":
            rules.append(" ".join(text[head:mark.start()].split()))
        else:
            decl = re.match(r"\s*--([\w-]+):\s*(\S[\s\S]*)", text[head:mark.start()])
            if decl and rules and rules[-1] in THEME_RULES:
                line = text.count("\n", 0, head + decl.start(1)) + 1
                found[(decl[1], "dark" if rules[-1] == ".dark" else "light")] = (line, decl[2])
            if mark[0] == "}" and rules:
                rules.pop()
        head = mark.end()
    same = lambda a, b: " ".join(a.lower().split()) == " ".join(b.lower().split())
    out = []
    for name, which, value in wanted:
        line, app = found.get((name, which or "light"), (1, None))
        label = f"--{name} ({which})" if which else f"--{name}"
        # A value with no light or dark form takes the guide's comment, with or without a theme.
        if waived & {label, f"{label} (light)", f"{label} (dark)"} or (app is not None and same(app, value)):
            continue
        said = f"is missing in the app; {APPROVED_THEME} has {value}" if app is None else (
            f"is {' '.join(app.split())} in the app and {value} in {APPROVED_THEME}")
        out.append(f"{APP_THEME}:{line} theme-drift: {label} {said}.\n"
                   f"  /* forge-ui-ignore theme-drift {label}: <reason> */")
    return out
