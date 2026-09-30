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
# Its standard installs: the Codex skills folder, then the Claude one.
HELPERS = [Path.home() / host / "skills" / "autoreview" / "scripts" / "autoreview"
           for host in (".codex", ".claude")]
PRIORITIES = ("P0", "P1", "P2", "P3")
SERIOUS = ("P0", "P1")
# Bookkeeping, not product: state and unrelated planning files never make a review stale.
BOOKKEEPING = (".factory/", "plans/")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


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
    from forge import story  # story imports review indirectly
    story._parsed(path, f"plans/{key}.md")  # pyright: ignore[reportPrivateUsage]
    return text, doc, row


# --- what a review covers --------------------------------------------------------------


def fingerprint(commit: str, item: str, top: Path, state: dict[str, Any], base: str,
                reviewed_level: str | None = None) -> str:
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
    current_level = blocking_level(top, item, state, base, commit)
    saved_level = reviewed_level or (state.get("review") or {}).get("blocking_level", "P1")
    if saved_level == "P0":
        parts.append("P0-only prototype review")
    if saved_level != current_level:
        parts.append("The recorded review level is no longer allowed")
    for part in parts:
        digest.update(b"\0" + part.encode("utf-8"))
    return digest.hexdigest()


def whole_tree(commit: str, item: str, top: Path, state: dict[str, Any], base: str) -> str:
    """The v1.1.0 release's fingerprint, kept under the record's `tree` key so that release's
    forge-pr-check passes an upgrade pull request this version reviewed: the whole product tree
    at commit, what the change must do and the worker's functional check.
    ponytail: one release only; delete it, and close's refresh of `tree`, after v1.2.0."""
    listing = repo.git("ls-tree", "-r", "-z", "--full-tree", commit, cwd=top).split("\0")
    product = [entry for entry in listing if not entry.partition("\t")[2].startswith(BOOKKEEPING)]
    digest = hashlib.sha256("\0".join(product).encode("utf-8"))
    key, _, name = item.partition("/")
    if name:
        text = repo.run("git", "show", f"{commit}:plans/{key}.md", cwd=top).stdout
        doc = sections(text)
        parts = [doc.get("Done when", ""), doc.get("Tasks", ""), doc.get("Risks", ""),
                 moving_parts(text)]
    else:
        parts = [str(state.get("why", "")), str(state.get("done_when", ""))]
    parts.append(functional_check(top, base, commit))
    for part in parts:
        digest.update(b"\0" + part.encode("utf-8"))
    return digest.hexdigest()


def blocking_level(top: Path, item: str, state: dict[str, Any], base: str,
                   commit: str = "HEAD") -> str:
    """P0 for an unsigned client prototype fix, P1 for every other review."""
    if ("/" in item or state.get("kind") != "fix" or
            state.get("allow_large") != "Prototype before sign-off"):
        return "P1"
    return "P0" if repo.is_prototype(top, refs=(base, commit)) else "P1"


def blocking(result: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    """The numbered blocking findings of a review result that no one dismissed."""
    dismissed = {d.get("finding") for d in result.get("dismissals", []) if isinstance(d, dict)}
    return [(n, f) for n, f in enumerate(result.get("findings", []), 1)
            if not isinstance(f, dict) or
            (f.get("priority") in (("P0",) if result.get("blocking_level") == "P0" else SERIOUS)
             and n not in dismissed)]


# --- the instructions ------------------------------------------------------------------


def instructions(top: Path, item: str, state: dict[str, Any], cfg: dict[str, Any],
                 base: str, previous: dict[str, Any]) -> str:
    """The plain review instructions for this task or fix, from templates/review.md."""
    from forge import story  # story imports review indirectly
    text = (Path(__file__).parent / "templates" / "review.md").read_text(encoding="utf-8")
    parts = re.split(r"^<!-- ([a-z-]+) -->\r?\n", text, flags=re.M)
    blocks = {parts[i]: string.Template(parts[i + 1].strip()) for i in range(1, len(parts), 2)}
    changed = repo.git("diff", "--name-only", f"{base}...HEAD", cwd=top).splitlines()
    changed = [path for path in changed if not path.startswith(BOOKKEEPING)]
    values = {"why": state.get("why", ""), "done_when": state.get("done_when", ""),
              "moving_parts": "New moving parts: none (a fix adds no new moving part)",
              "previous": _previous(previous), "rulings": _rulings(top, item, base),
              # read after close merged the default branch, which may change the command
              "test_run": _test_run(top, repo.config(top)["test"])}
    if "/" in item:
        doc_text, doc, row = task(top, item)
        parsed = story.parse(doc_text)
        covers = {int(n) for n in re.findall(r"\d+", row.get("covers", ""))}
        scope, tests = cells(row.get("scope", "")), cells(row.get("tests", ""))
        existing_tests = set(repo.git("ls-tree", "-r", "--name-only", base,
                                      cwd=top).splitlines())
        values.update(
            name=row.get("name", ""), delivers=row.get("what it delivers", ""),
            scope=_bullets(scope), tests=_bullets(tests),
            outside=_bullets(p for p in changed if not any(_within(p, s) for s in scope + tests)
                             and not (p in existing_tests and _test_file(p))),
            covered=_bullets(story.item(parsed, n, True) for n in parsed["done"] if n in covers),
            context=_bullets(story.item(parsed, n, False) for n in parsed["done"] if n not in covers),
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
    values["review_rules"] = story.agents_section(top, "Review rules")
    if values["review_rules"]:
        chosen.append("review-rules")
    return "\n\n".join(blocks[name].substitute(values) for name in chosen)


def _test_run(top: Path, command: str) -> str:
    """Run forge.toml's test command here, so the reviewer sees tests its sandbox can't run: the
    exit status, every line that mentions a skip with the line before it (where Go's -v prints the
    reason), and the last 30 lines, at most 80 in all. pytest also lists each skip's reason (-rs)."""
    if not command:
        return "forge.toml names no test command, so close ran none."
    env = {**os.environ, "PYTEST_ADDOPTS": f"{os.environ.get('PYTEST_ADDOPTS', '')} -rs".strip()}
    done = subprocess.run(command, shell=True, cwd=top, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace")
    out = [line.rstrip() for line in done.stdout.splitlines()]
    picked = sorted({i for n, line in enumerate(out) if "skip" in line.lower()
                     for i in (n - 1, n) if i >= 0} | set(range(max(0, len(out) - 30), len(out))))
    lines = [out[i] for i in picked]
    if len(lines) > 80:  # the tail is the last 30 picked; the earliest skip lines fill the rest
        lines = [*lines[:50], f"({len(lines) - 80} skip lines cut here)", *lines[-30:]]
    return "\n".join([f"`{command}` exited with status {done.returncode} on the machine running "
                      "forge close.", *lines])


def _previous(result: dict[str, Any]) -> str:
    findings = result.get("findings", [])
    dismissals = {d["finding"]: d["because"] for d in result.get("dismissals", [])}
    return "\n".join(
        f"{n}. {finding['priority']} {finding['title']} ({finding['file']}:{finding['line']}): "
        f"{finding['body']}" + (f"; dismissed because {dismissals[n]}" if n in dismissals else "")
        for n, finding in enumerate(findings, 1)) or "- none"


def _rulings(top: Path, item: str, base: str) -> str:
    """Every `Ruling:` line in the branch's commit messages, then every dismissal Forge committed on
    the branch with its reason, oldest first. Git holds both; Forge copies them, never stores them."""
    log = repo.git("log", "--reverse", "--no-merges", "--format=%B", f"{base}..HEAD", cwd=top)
    found = [line.strip() for line in log.splitlines() if line.startswith("Ruling:")]
    path = repo.state_path(item)
    for sha in repo.git("log", "--reverse", "--format=%H", f"{base}..HEAD", "--", path,
                        cwd=top).split():
        result = json.loads(repo.git("show", f"{sha}:{path}", cwd=top)).get("review") or {}
        for dismissal in result.get("dismissals", []):
            finding = result["findings"][dismissal["finding"] - 1]
            line = (f"{finding['title']} ({finding['file']}): dismissed because "
                    f"{dismissal['because']}")
            if line not in found:
                found.append(line)
    return _bullets(found)


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
    """The Autoreview helper ($AUTOREVIEW, else the first standard install), refused unless pinned."""
    path = Path(os.environ.get("AUTOREVIEW")
                or next((found for found in HELPERS if found.is_file()), HELPERS[0]))
    stamp = path.parent.parent / ".upstream-sha"
    found = stamp.read_text(encoding="utf-8").strip() if path.is_file() and stamp.is_file() else ""
    if found != AUTOREVIEW_PIN:
        repo.refuse(REFUSALS["helper"], path=path, pin=AUTOREVIEW_PIN, found=found or "nothing")
    return path


def run(top: Path, item: str, state: dict[str, Any], cfg: dict[str, Any],
        base: str, selected: dict[str, str], previous: dict[str, Any],
        signoff_prompt: str = "", light: bool = False) -> dict[str, Any]:
    """Review the branch head once, retrying once when a run doesn't finish. Returns the result."""
    prompt = signoff_prompt or instructions(top, item, state, cfg, base, previous)
    path = helper()
    head = repo.git("rev-parse", "HEAD", cwd=top)
    product = (sorted({name for command in (("ls-files", "-z"),
                                            ("ls-tree", "-r", "-z", "--name-only", head))
                       for name in repo.git(*command, cwd=top).split("\0")
                       if name and not name.startswith((*BOOKKEEPING, "docs/decisions/"))})
               if signoff_prompt else [])
    with tempfile.TemporaryDirectory(prefix="forge-review-", ignore_cleanup_errors=True) as folder:
        tmp = Path(folder)
        tree, out = tmp / "tree", tmp / "review.json"
        # A local clone keeps Git history inside the reviewer's read-only sandbox.
        repo.git("clone", "-q", "--no-hardlinks", "--no-checkout", str(top), str(tree), cwd=top)
        repo.git("checkout", "-q", "--detach", head, cwd=tree)
        if signoff_prompt:
            repo.git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--",
                     ".factory", "plans", "docs/decisions", cwd=tree)
            product_tree = repo.git("write-tree", cwd=tree)
            review_base = repo.git("commit-tree", EMPTY_TREE, "-m", "Empty product review base",
                                   cwd=tree)
            snapshot = repo.git("commit-tree", product_tree, "-p", review_base,
                                "-m", "Product snapshot for sign-off", cwd=tree)
            repo.git("checkout", "-q", "-f", "--detach", snapshot, cwd=tree)
        else:
            repo.git("fetch", "-q", str(top),
                     f"+refs/remotes/{base}:refs/remotes/{base}", cwd=tree)
            review_base = repo.git("rev-parse", base, cwd=tree)
        engine = "codex" if shutil.which(os.environ.get("CODEX_BIN") or "codex") else "claude"
        # ponytail: the instructions ride in argv; move them to --prompt-file inside the review
        # tree if a story's text ever nears Windows' 32K command line.
        argv = [sys.executable, str(path), "--mode", "branch", "--base", review_base,
                "--engine", engine,
                "--max-priority", "P0" if light else "P3", "--prompt", prompt,
                "--json-output", str(out)]
        # The light prototype review runs Sol at medium on Codex; otherwise forge.toml's review kind
        # on Codex, or its Claude cold-read model when only Claude is installed.
        chosen = (repo.models(cfg, "grill", "claude") if engine == "claude" else
                  {"model": "gpt-6-sol", "effort": "medium"} if light else cfg["models"].get("review"))
        if chosen:
            argv += ["--model", f"{engine}={chosen['model']}"]
            argv += ["--thinking", f"{engine}={chosen['effort']}"] if "effort" in chosen else []
        launcher = _launcher(tmp / "bin", tree)
        if launcher:
            argv += ["--codex-bin", str(launcher)]
        for attempt in ((1,) if signoff_prompt else (1, 2)):
            findings, reason = _attempt(argv, tree, out, selected, strict=bool(signoff_prompt))
            if not reason:
                break
            print(f"Autoreview run {attempt} did not finish: {reason}.", file=sys.stderr)
        if signoff_prompt:
            if reason:
                repo.refuse(("The sign-off review did not finish: " + reason + ".",
                             "check Autoreview, then forge decision accept client-signoff --by \"<name>\""))
            if selected.get("model") != "gpt-6-sol" or selected.get("effort") != "high":
                repo.refuse(("The sign-off review did not confirm GPT-6 Sol at high effort: "
                             "model and effort must match.",
                             "check Autoreview, then forge decision accept client-signoff --by \"<name>\""))
            serious = [f for f in findings if f["priority"] in SERIOUS]
            if serious:
                repo.refuse(("Customer sign-off review found a blocking issue: "
                             + "; ".join(f["title"] for f in serious) + ".",
                             "fix the prototype, then forge decision accept client-signoff --by \"<name>\""))
            if repo.git("rev-parse", "HEAD", cwd=top) != head or repo.git(
                    "status", "--porcelain", "--", "docs/product/BRIEF.md", *product, cwd=top):
                repo.refuse(("The prototype differs from the reviewed commit.",
                             "commit the changes, then forge decision accept client-signoff --by \"<name>\""))
            return {"commit": head}
        if reason:
            repo.refuse(REFUSALS["failed"], reason=reason, item=item)
    return {"commit": head, "changed": fingerprint(head, item, top, state, base,
                                                     "P0" if light else "P1"),
            "tree": whole_tree(head, item, top, state, base), "findings": findings,
            "dismissals": [], "blocking_level": "P0" if light else "P1"}


def signoff(top: Path, answers: str) -> str:
    """Review every tracked product file once, against an empty root, before client acceptance."""
    skill = (Path(__file__).parent / "templates" / "skill.md").read_text(encoding="utf-8")
    table = re.search(r"^\| Topic \|.*?(?=\n\n)", skill, re.M | re.S)
    block = (Path(__file__).parent / "templates" / "review.md").read_text(encoding="utf-8")
    prompt = string.Template(block.split("<!-- signoff -->\n", 1)[1]).substitute(
        answers=answers, topics=table[0] if table else "")
    cfg = {"models": {"review": {"model": "gpt-6-sol", "effort": "high"}}}
    return run(top, "client-signoff", {}, cfg, "", {}, {}, signoff_prompt=prompt)["commit"]


def _attempt(argv: list[str], cwd: Path, out: Path,
             selected: dict[str, str], strict: bool = False) -> tuple[list[dict[str, Any]], str]:
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
    # calls the review incomplete for it. Ordinary reviews keep those findings; sign-off requires
    # a complete run even when rejected findings are present.
    rejected = report.get("scope_rejected_findings") or []
    if (strict or not rejected) and (code == 2 or report.get("review_status") == "incomplete"):
        return [], "it reported the review as incomplete"
    if strict and report.get("review_status") not in (
            "scoped-clean", "findings", "filtered", "incorrect"):
        return [], "it did not report a completed review"
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
