"""One review round: Autoreview over the branch in a read-only checkout, and its committed result.

Autoreview is a third-party black box. Forge reads only the fields it uses (each finding's
priority, title, body and code_location, in findings and scope_rejected_findings, then
review_status and overall_correctness) and ignores everything else it writes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from forge import repo

# The helper Forge runs: the upstream commit its installer stamps in the skill's .upstream-sha.
AUTOREVIEW_PIN = "ce14dcca09b3affb922ddcca11465619e67f5114"
HELPER = Path.home() / ".codex" / "skills" / "autoreview" / "scripts" / "autoreview"
PRIORITIES = ("P0", "P1", "P2", "P3")
SERIOUS = ("P0", "P1")
# Bookkeeping, not product: state and unrelated planning files never make a review stale.
BOOKKEEPING = (".factory/", "plans/")


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    return {f"{host}/skills/test-audit/{name}":
            sync._synced_text(f".codex/skills/test-audit/{name}",
                              f"skills/test-audit/{name}")
            for host in (".claude", ".codex")
            for name in ("NOTICE.md", "SKILL.md")}

REFUSALS = {
    "helper": ("The Autoreview helper at {path} is not the pinned version {pin} (found: {found}).",
               "forge doctor"),
    "failed": ("Autoreview did not finish a review twice in a row: {reason}.",
               "forge doctor, then forge close {item}"),
    "bad_doc": ("plans/{key}.md has no usable Tasks row for {task}.",
                "fix that row in plans/{key}.md, then forge close {item}"),
}

# Ported from the old tree's review launcher: the helper starts Codex in an empty folder, where
# the reviewer can't open the code a finding depends on. This `codex` swaps that one folder for
# the reviewed checkout; the read-only sandbox the helper asks for stays as it is.
LAUNCHER = '''\
import subprocess, sys
argv = sys.argv[1:]
for i in range(len(argv) - 1):
    if argv[i] in ("-C", "--cd"):
        argv[i + 1] = {tree!r}
sys.exit(subprocess.call([{real!r}, *argv]))
'''


# --- the story doc ---------------------------------------------------------------------
# ponytail: STORY's story.py owns full doc parsing; these read only what review and close need.


def sections(text: str) -> dict[str, str]:
    """A story doc's `## ` sections, by heading."""
    parts = re.split(r"^## +(.+?) *$", text, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


def rows(tasks: str) -> list[dict[str, str]]:
    """The Tasks table's rows, keyed by lower-case header."""
    table = [[cell.strip() for cell in line.strip().strip("|").split("|")]
             for line in tasks.splitlines() if line.lstrip().startswith("|")]
    header = [cell.lower() for cell in table[0]] if table else []
    return [dict(zip(header, cells)) for cells in table[2:]]  # [1] is the |---| line


def cells(value: str) -> list[str]:
    """The paths in one table cell, such as "`a.py`, `b/`"; "—" is none."""
    return [part.strip(" `") for part in value.split(",") if part.strip(" `—-")]


def moving_parts(text: str) -> str:
    found = re.search(r"^New moving parts:.*$", text, re.M)
    return found[0].strip() if found else "New moving parts: (the story doc has no such line)"


def task(top: Path, item: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """A task's story doc text, its sections and the task's row; refused when the row is missing."""
    key, _, name = item.partition("/")
    path = top / "plans" / f"{key}.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    doc = sections(text)
    row = next((r for r in rows(doc.get("Tasks", "")) if r.get("id", "").strip("`") == name), None)
    if row is None:
        repo.refuse(REFUSALS["bad_doc"], key=key, task=name, item=item)
    return text, doc, row


# --- what a review covers --------------------------------------------------------------


def fingerprint(commit: str, item: str, top: Path, state: dict[str, Any], base: str) -> str:
    """What a clean review covers: changed product files, the item's story doc and roadmap entry, its
    fix contract when applicable, and the worker's functional check. Read through git so a pull
    request's head is only ever data."""
    ancestor = repo.git("merge-base", base, commit, cwd=top)
    changed = repo.git("diff", "--name-only", "-z", "--no-renames", ancestor, commit,
                       cwd=top).split("\0")
    changed = {path for path in changed if path and not path.startswith(BOOKKEEPING)}
    listing = repo.git("ls-tree", "-r", "-z", "--full-tree", commit, cwd=top).split("\0")
    blobs = {path: entry.partition("\t")[0].split()[-1] for entry in listing
             if (path := entry.partition("\t")[2]) in changed}
    digest = hashlib.sha256("\0".join(
        f"{path}\0{blobs.get(path, '')}" for path in sorted(changed)).encode("utf-8"))
    key, _, name = item.partition("/")
    if name:
        text = repo.run("git", "show", f"{commit}:plans/{key}.md", cwd=top).stdout
        roadmap = repo.run("git", "show", f"{commit}:plans/roadmap.json", cwd=top)
        items = json.loads(roadmap.stdout).get("items", []) if roadmap.returncode == 0 else []
        entry = next((value for value in items if value.get("key") == key), {})
        parts = [text, json.dumps(entry, sort_keys=True)]
    else:
        parts = [str(state.get("why", "")), str(state.get("done_when", ""))]
    parts.append(functional_check(top, base, commit))
    for part in parts:
        digest.update(b"\0" + part.encode("utf-8"))
    return digest.hexdigest()


def blocking(result: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    """The numbered P0 and P1 findings of a review result that no one dismissed."""
    dismissed = {d.get("finding") for d in result.get("dismissals", []) if isinstance(d, dict)}
    return [(n, f) for n, f in enumerate(result.get("findings", []), 1)
            if not isinstance(f, dict) or f.get("priority") in SERIOUS and n not in dismissed]


# --- the instructions ------------------------------------------------------------------


def instructions(top: Path, item: str, state: dict[str, Any], cfg: dict[str, Any],
                 base: str, previous: dict[str, Any]) -> str:
    """The plain review instructions for this task or fix, from templates/review.md."""
    text = (Path(__file__).parent / "templates" / "review.md").read_text(encoding="utf-8")
    parts = re.split(r"^<!-- ([a-z-]+) -->\r?\n", text, flags=re.M)
    blocks = {parts[i]: string.Template(parts[i + 1].strip()) for i in range(1, len(parts), 2)}
    changed = repo.git("diff", "--name-only", f"{base}...HEAD", cwd=top).splitlines()
    changed = [path for path in changed if not path.startswith(BOOKKEEPING)]
    values = {"why": state.get("why", ""), "done_when": state.get("done_when", ""),
              "moving_parts": "New moving parts: none (a fix adds no new moving part)",
              "previous": _previous(previous)}
    if "/" in item:
        doc_text, doc, row = task(top, item)
        items = re.split(r"^(\d+)\.\s+", doc.get("Done when", ""), flags=re.M)
        items = {items[i]: " ".join(items[i + 1].split()) for i in range(1, len(items), 2)}
        covers = set(re.findall(r"\d+", row.get("covers", "")))
        scope, tests = cells(row.get("scope", "")), cells(row.get("tests", ""))
        existing_tests = set(repo.git("ls-tree", "-r", "--name-only", base,
                                      cwd=top).splitlines())
        values.update(
            name=row.get("name", ""), delivers=row.get("what it delivers", ""),
            scope=_bullets(scope), tests=_bullets(tests),
            outside=_bullets(p for p in changed if not any(_within(p, s) for s in scope + tests)
                             and not (p in existing_tests and _test_file(p))),
            covered=_bullets(f"{n}. {t}" for n, t in items.items() if n in covers),
            context=_bullets(f"{n}. {t}" for n, t in items.items() if n not in covers),
            risks=doc.get("Risks", "Risks: none"), notes=doc.get("Notes", "none"),
            moving_parts=moving_parts(doc_text))
        chosen = ["task", "rules"]
        if row.get("user-facing", "").lower() in ("yes", "true"):
            chosen.insert(1, "functional-check")
            values["functional_check"] = functional_check(top, base) or (
                "None: the worker's last commit message has no `Functional check:` paragraph.")
    else:
        chosen = ["fix", "rules"]
        if not cfg["interfaces"] and not state.get("allow_large"):
            chosen.insert(1, "promote")
    return "\n\n".join(blocks[name].substitute(values) for name in chosen)


def _previous(result: dict[str, Any]) -> str:
    findings = result.get("findings", [])
    dismissals = {d["finding"]: d["because"] for d in result.get("dismissals", [])}
    return "\n".join(
        f"{n}. {finding['priority']} {finding['title']} ({finding['file']}:{finding['line']}): "
        f"{finding['body']}" + (f"; dismissed because {dismissals[n]}" if n in dismissals else "")
        for n, finding in enumerate(findings, 1)) or "- none"


def functional_check(top: Path, base: str, head: str = "HEAD") -> str:
    """The worker's functional check: the `Functional check:` paragraph of its last commit message,
    to the end. That's the branch's newest commit that isn't a merge or only Forge's records (an
    empty commit counts); an older commit's check never counts. Git holds it; Forge copies it,
    never stores it."""
    for sha in repo.git("rev-list", "--no-merges", f"{base}..{head}", cwd=top).split():
        files = repo.git("diff-tree", "--no-commit-id", "--name-only", "-r", sha, cwd=top).split()
        if files and all(f.startswith(BOOKKEEPING) for f in files):
            continue
        found = re.search(r"^Functional check:.*", repo.git("show", "-s", "--format=%B", sha,
                                                            cwd=top), re.M | re.S)
        return found[0].strip() if found else ""
    return ""


def _bullets(items: Any) -> str:
    return "\n".join(f"- {item}" for item in items) or "- none"


def _within(path: str, entry: str) -> bool:
    """A changed path is inside a Scope entry: the same file, under the folder, or a glob match."""
    return path == entry or path.startswith(entry.rstrip("/") + "/") or fnmatch(path, entry)


def _test_file(path: str) -> bool:
    """Test files named as tests or kept in a test folder, including colocated tests."""
    parts = Path(path).parts
    name = parts[-1]
    return (any(fnmatch(name, pattern) for pattern in ("test_*.py", "*_test.py",
                                                        "*.test.*", "*.spec.*"))
            or (any(part.startswith("test") for part in parts[:-1])
                and "fixtures" not in parts[:-1]))


# --- the round -------------------------------------------------------------------------


def helper() -> Path:
    """The Autoreview helper ($AUTOREVIEW, else the standard install), refused unless pinned."""
    path = Path(os.environ.get("AUTOREVIEW") or HELPER)
    stamp = path.parent.parent / ".upstream-sha"
    found = stamp.read_text(encoding="utf-8").strip() if path.is_file() and stamp.is_file() else ""
    if found != AUTOREVIEW_PIN:
        repo.refuse(REFUSALS["helper"], path=path, pin=AUTOREVIEW_PIN, found=found or "nothing")
    return path


def run(top: Path, item: str, state: dict[str, Any], cfg: dict[str, Any],
        base: str, selected: dict[str, str], previous: dict[str, Any]) -> dict[str, Any]:
    """Review the branch head once, retrying once when a run doesn't finish. Returns the result."""
    prompt = instructions(top, item, state, cfg, base, previous)
    path = helper()
    head = repo.git("rev-parse", "HEAD", cwd=top)
    tmp = Path(tempfile.mkdtemp(prefix="forge-review-"))
    tree, out = tmp / "tree", tmp / "review.json"
    try:
        # A local clone keeps Git history inside the reviewer's read-only sandbox.
        repo.git("clone", "-q", "--no-hardlinks", "--no-checkout", str(top), str(tree), cwd=top)
        repo.git("checkout", "-q", "--detach", head, cwd=tree)
        repo.git("fetch", "-q", str(top),
                 f"+refs/remotes/{base}:refs/remotes/{base}", cwd=tree)
        review_base = repo.git("rev-parse", base, cwd=tree)
        # ponytail: the instructions ride in argv; move them to --prompt-file inside the review
        # tree if a story's text ever nears Windows' 32K command line.
        argv = [sys.executable, str(path), "--mode", "branch", "--base", review_base,
                "--engine", "codex",
                "--max-priority", "P3", "--prompt", prompt, "--json-output", str(out)]
        chosen = cfg["models"].get("review")
        if chosen:  # forge.toml's review kind: its model, and its effort when it sets one
            argv += ["--model", f"codex={chosen['model']}"]
            argv += ["--thinking", f"codex={chosen['effort']}"] if "effort" in chosen else []
        launcher = _launcher(tmp / "bin", tree)
        if launcher:
            argv += ["--codex-bin", str(launcher)]
        for attempt in (1, 2):
            findings, reason = _attempt(argv, tree, out, selected)
            if not reason:
                break
            print(f"Autoreview run {attempt} did not finish: {reason}.", file=sys.stderr)
        else:
            repo.refuse(REFUSALS["failed"], reason=reason, item=item)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"commit": head, "tree": fingerprint(head, item, top, state, base), "findings": findings,
            "dismissals": []}


def _attempt(argv: list[str], cwd: Path, out: Path,
             selected: dict[str, str]) -> tuple[list[dict[str, Any]], str]:
    """Run Autoreview once: its findings, or the reason the run doesn't count."""
    out.unlink(missing_ok=True)
    proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    last = ""
    for line in proc.stdout or []:  # streamed as bytes: its progress is how a person watches it
        sys.stderr.buffer.write(line)
        sys.stderr.flush()
        last = line.decode("utf-8", "replace").strip() or last
        if last.startswith("model: ") and "model" not in selected:
            selected["model"] = last.removeprefix("model: ")
        elif last.startswith("thinking: ") and "effort" not in selected:
            selected["effort"] = last.removeprefix("thinking: ")
        elif match := re.fullmatch(
                r"codex model \S+ is unavailable for this account; retrying with (\S+)", last):
            selected["model"] = match[1]
    code = proc.wait()
    try:
        report = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    if code not in (0, 1, 2) or not isinstance(report, dict):
        return [], last or f"it exited with code {code}"
    # The helper moves a finding pinned outside the changed files to scope_rejected_findings and
    # calls the review incomplete for it. Forge keeps those findings like any other, so none is
    # lost. ponytail: the helper doesn't say whether the engine also stopped early in that run,
    # so a run with rejected findings always counts as finished; its findings still block.
    rejected = report.get("scope_rejected_findings") or []
    if not rejected and (code == 2 or report.get("review_status") == "incomplete"):
        return [], "it reported the review as incomplete"
    raw = report.get("findings")
    findings = ([_finding(f) for f in [*raw, *rejected]]
                if isinstance(raw, list) and isinstance(rejected, list) else [None])
    if None in findings:
        return [], "it wrote findings Forge cannot read"
    if not findings and report.get("overall_correctness") == "patch is incorrect":
        return [], "it called the patch incorrect without naming a finding"
    return findings, ""  # type: ignore[return-value]


def _finding(raw: Any) -> dict[str, Any] | None:
    """The fields Forge uses from one finding, or None when they can't be read."""
    where = raw.get("code_location") if isinstance(raw, dict) else None
    if not isinstance(where, dict) or raw.get("priority") not in PRIORITIES:
        return None
    return {"priority": raw["priority"], "title": str(raw.get("title", "")),
            "body": str(raw.get("body", "")), "file": str(where.get("file_path", "")),
            "line": where.get("line", 0)}


def _launcher(folder: Path, tree: Path) -> Path | None:
    """A `codex` for the helper that runs the real one inside the reviewed checkout."""
    real = shutil.which(os.environ.get("CODEX_BIN") or "codex")
    if not real:
        return None  # the helper then finds no Codex itself and says so
    # ponytail: the old launcher also carried the Windows elevated-sandbox setting through the
    # helper's --ignore-user-config; port it when a Windows review can't run its read-only shell.
    folder.mkdir()
    script = folder / "codex_in_tree.py"
    script.write_text(LAUNCHER.format(tree=str(tree), real=real), encoding="utf-8")
    if os.name == "nt":
        launcher = folder / "codex.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = folder / "codex"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n',
                            encoding="utf-8")
        launcher.chmod(0o755)
    return launcher
