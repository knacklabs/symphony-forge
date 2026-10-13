"""One review round: Autoreview over the branch in a read-only checkout, and its committed result.

Autoreview is a third-party black box. Forge reads only the fields it uses (each finding's
priority, title, body and code_location, in findings and scope_rejected_findings, then
review_status and overall_correctness) and ignores everything else it writes. The body's first
line carries the reviewer's Gain, Work and Harm scores (see score.py).
"""
from __future__ import annotations

import ast
import collections
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import string
import subprocess
import sys
import tempfile
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from forge import machine, repo, score, spotted
from forge.task import branch_item, sections

# The helper Forge runs: the upstream commit its installer stamps in the skill's .upstream-sha.
AUTOREVIEW_PIN = "ce14dcca09b3affb922ddcca11465619e67f5114"
# Its standard installs: the Codex skills folder, then the Claude one.
HELPERS = [Path.home() / host / "skills" / "autoreview" / "scripts" / "autoreview"
           for host in (".codex", ".claude")]
PRIORITIES = ("P0", "P1", "P2", "P3")
# Untracked in the review tree, which branch mode leaves out of the diff.
STANDARDS = "forge-standards.md"
SPENT = "spent.jsonl"  # beside the review tree: the engine's chat and token use
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
SERIOUS = ("P0", "P1")
# Bookkeeping, not product: state and unrelated planning files never make a review stale.
BOOKKEEPING = (".factory/", "plans/")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


# A file path with an optional line (with the "at" or "in" before it) or a commit hash, for plain().
PATHLIKE = re.compile(r"(?:\s(?:at|in|on|from|see))?\s*\(?(?:(?:[\w.-]+/)+[\w.-]*\.\w+|\b[\w-]+\.[A-Za-z]{1,5}"
                      r"(?=:\d))(?::[\d,-]+)?\)?|\s*\(?\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b\)?")


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

# Ported from the old tree's review launcher: the helper starts the reviewer in an empty folder,
# where it can't open the code a finding depends on. Each launcher starts the real one in the
# reviewed checkout instead. The `codex` one swaps that one folder; the read-only sandbox the
# helper asks for stays as it is. The helper gives Claude only web search and refuses Read as a
# tool option, so the `claude` one adds the read-only file tools; --restricted keeps them inside
# the checkout and leaves out every tool that runs commands.
LAUNCHER = '''\
import subprocess, sys
argv = sys.argv[1:]
if {engine!r} == "codex":
    for i in range(len(argv) - 1):
        if argv[i] in ("-C", "--cd"):
            argv[i + 1] = {tree!r}
    if "exec" in argv:
        i = argv.index("exec")
        argv[i:i] = {quiet!r}
elif "--tools" in argv:
    i = argv.index("--tools") + 1
    argv[i] = ",".join(filter(None, ["Read", "Grep", "Glob", argv[i]]))
    argv.append("--restricted")
# The engine's chat and token use go to a side file, as the helper keeps no copy.
with open({spent!r}, "ab") as spent, subprocess.Popen(
        [{real!r}, *argv], cwd={tree!r}, stdout=subprocess.PIPE) as engine:
    for line in engine.stdout:
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
        if any(kind in line for kind in (b"thread.started", b"turn.completed", b"session_id")):
            spent.write(line)
sys.exit(engine.returncode)
'''


# --- the story doc ---------------------------------------------------------------------
# ponytail: STORY's story.py owns full doc parsing; these read only what review and close need.


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
    from forge import story  # story imports review indirectly
    key, _, name = item.partition("/")
    path = top / "plans" / f"{key}.md"
    # Like forge task start: the story branch's copy while it exists, so a plan edit made there
    # after approval reaches the review; else this checkout's, which close merged from the default.
    text = story.show(top, f"story/{key}", f"plans/{key}.md")
    if text is None:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    doc = sections(text)
    row = next((r for r in rows(doc.get("Tasks", "")) if r.get("id", "").strip("`") == name), None)
    if row is None:
        repo.refuse(REFUSALS["bad_doc"], key=key, task=name, item=item)
    story._parsed(text, f"plans/{key}.md")  # pyright: ignore[reportPrivateUsage]
    return text, doc, row


# --- what a review covers --------------------------------------------------------------


def fingerprint(commit: str, item: str, top: Path, state: dict[str, Any], base: str,
                reviewed_level: str | None = None, findings: list[Any] | None = None, *,
                branch_diff: bool = False) -> str:
    """What a clean review covers: changed product files, every file the review's findings cite
    (the recorded review's unless findings is given), the item's story doc and roadmap entry, its
    fix contract when applicable, and the worker's functional check. Read through git so a pull
    request's head is only ever data."""
    ancestor = repo.git("merge-base", base, commit, cwd=top)
    changed = repo.git("diff", "--name-only", "-z", "--no-renames", ancestor, commit,
                       cwd=top).split("\0")
    named = str(state.get("done_when", ""))  # a file the Done-when names is never bookkeeping
    changed = {path for path in changed
               if path and (not path.startswith(BOOKKEEPING) or path in named)}
    if findings is None:
        findings = (state.get("review") or {}).get("findings", [])
    changed |= {str(f["file"]) for f in findings if isinstance(f, dict) and f.get("file")}
    # Close writes the spotted list after the review, so it never makes that review stale.
    changed.discard(spotted.PATH)
    if branch_diff:
        # Close alone uses both sides of the diff to reuse a review after a base-only merge.
        # Sort header/path pairs: diff.orderFile can reorder even raw Git output.
        raw = (repo.git("--literal-pathspecs", "diff", "--raw", "--no-abbrev", "--no-renames",
                        "--no-ext-diff", "--no-color", "-z", ancestor, commit, "--",
                        *sorted(changed), cwd=top) if changed else "").split("\0")
        entries = sorted(zip(raw[::2], raw[1::2]), key=lambda entry: entry[1])
        digest = hashlib.sha256("\0".join(
            f"{path}\0{entry}" for entry, path in entries).encode("utf-8"))
    else:
        # review.changed must retain the fingerprint used by the PR base's installed checker.
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
        if branch_diff:
            # Close's reuse key covers the same live story document as the review prompt.
            parts.append(task(top, item)[0])
    else:
        parts = [str(state.get("why", "")), str(state.get("done_when", ""))]
    parts.append(functional_check(top, base, commit))
    if branch_diff and (proof := commit_paragraph(top, base, "Proof list:", commit)):
        parts.append(proof)
    current_level = blocking_level(top, item, state, base, commit)
    saved_level = reviewed_level or (state.get("review") or {}).get("blocking_level", "P1")
    if saved_level == "P0":
        parts.append("P0-only prototype review")
    if saved_level != current_level:
        parts.append("The recorded review level is no longer allowed")
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
            (score.holds(f, result.get("blocking_level")) and n not in dismissed)]


def area(top: Path, commit: str, file: str, line: Any) -> str:
    """A finding's area: the qualified name of the innermost Python def holding its line at the
    commit, else (another language, no parse, a line outside every def) the file."""
    text = repo.run("git", "show", f"{commit}:{file}", cwd=top).stdout if file.endswith(".py") else ""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return file
    line = int(line) if str(line).isdigit() else 0
    found, todo = file, [(tree, "")]
    while todo:  # a parent comes before its children, so the innermost def holding the line wins
        node, prefix = todo.pop()
        for child in ast.iter_child_nodes(node):
            name = prefix + child.name + "." if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else prefix
            if not isinstance(child, ast.ClassDef) and name != prefix and child.lineno <= line <= (child.end_lineno or child.lineno):
                found = f"{name[:-1]}() in {file}"
            todo.append((child, name))
    return found


def plain(title: str, body: str = "") -> str:
    """A note or finding in plain words: its title and up to two sentences of its body, without
    markdown, labels, file paths or hashes."""
    def sentences(text: str, keep: int) -> str:
        text = " ".join(text.replace("**", "").replace("`", "").split())
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # a markdown link keeps its words
        text = re.sub(r"^(?:(?:Blocking|Raise|Advisory):\s*|(?:Not done|Gate|Standard|Functional|Test|"
                      r"Security|Scale|Data loss|Later|Follow-up)\s*[.:\u2014\u2013-]+\s*)+", "", text, flags=re.I)
        text = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\(\s*\)", "", PATHLIKE.sub("", text)))
        first, *rest = re.split(r"(?<=[.!?])\s", text.strip())
        # ponytail: a lead-in under five words ("The owner's setting.") takes the next sentence too.
        if keep == 1 and rest and len(first.split()) < 5:
            return f"{first.rstrip('.!?:')}: " + (rest[0] if rest[0][1:2].isupper() else
                                                 rest[0][:1].lower() + rest[0][1:])
        return " ".join([first, *rest][:keep])  # a second sentence often says who is affected
    title, body = sentences(title, 1), sentences(score.strip(body), 2)
    if not body:
        return title
    return f"{title.rstrip('.!?:')}: " + (body if body[1:2].isupper() else body[:1].lower() + body[1:])


def question(name: str, delivers: str, flagged: list[str], who: str, accept: str,
                  parts: str = "Done when") -> str:
    """Who decides a stopped read or review loop, then its question, ready to ask as written."""
    return "\n".join([who, f"{name}: {delivers}" if delivers else name,
                      *(["It still has these problems:", *flagged] if flagged else []),
                      "Accept, narrow or split?",
                      f"- Accept: {accept}",
                      f"- Narrow: drop these cases from its {parts}; they become follow-ups.",
                      "- Split: move these cases into a new story or fix of their own; this one goes on "
                      "without them."])


def stop_question(top: Path, item: str, state: dict[str, Any]) -> str:
    """A stopped item's question for the human: what it is, its open serious findings, the choices."""
    from forge import story as story_  # story imports review

    name, delivers = plain(state.get("why") or item), plain(state.get("done_when", ""))
    if "/" in item:  # a task: its row in the story's plan, which its worktree holds
        key, task = item.split("/")
        doc = top / "plans" / f"{key}.md"
        text = doc.read_text(encoding="utf-8") if doc.is_file() else ""
        try:
            row = next((row for row in story_.parse(text)["tasks"] if row["id"] == task), {})
        except ValueError:
            row = {}
        title = re.search(r"^# (.+)$", text, re.M)
        name = plain(row.get("Name") or item) + (f" (part of {plain(title[1])})" if title else "")
        delivers = plain(row.get("What it delivers", ""))
    result = state.get("review") or {}
    # The table lists every open finding, the ones Accept dismisses, below the bar included.
    opened = [id(finding) for finding in score.open_findings(result)]
    rows = [(n, plain(finding["title"], finding.get("body", "")), score.of(finding))
            for n, finding in enumerate(result.get("findings", []), 1) if id(finding) in opened]
    stop = state.get("stop") or {}
    said = question(name, delivers, score.table(rows), score.who(rows, (
                        "Ask the human to narrow the part, split it, or accept the remaining findings, "
                        "in these words:")),
                               f"every finding in this review, the {len(rows)} listed, is dismissed with "
                               "your reason and recorded; close then goes on to the checks, and merging "
                               "is still a separate step.")
    return said if not stop.get("area") else said.replace("It still has these problems:", (
        f"Findings keep coming in {stop['area']}; proposed: {stop['proposed']}. It still has these problems:"), 1)


# --- the instructions ------------------------------------------------------------------


def instructions(top: Path, item: str, state: dict[str, Any], cfg: dict[str, Any],
                 base: str, previous: dict[str, Any], tested: str) -> str:
    """The plain review instructions for this task or fix, from templates/review.md."""
    from forge import story  # story imports review indirectly
    text = (Path(__file__).parent / "templates" / "review.md").read_text(encoding="utf-8")
    parts = re.split(r"^<!-- ([a-z-]+) -->\r?\n", text, flags=re.M)
    blocks = {parts[i]: string.Template(parts[i + 1].strip()) for i in range(1, len(parts), 2)}
    changed = repo.git("diff", "--name-only", f"{base}...HEAD", cwd=top).splitlines()
    changed = [path for path in changed if not path.startswith(BOOKKEEPING)]
    history = _history(top, item, base, previous)
    settled = _settled(history)
    values = {"why": state.get("why", ""), "done_when": state.get("done_when", ""),
              "allowance": state.get("allow_large") or "No recorded allowance",
              "moving_parts": "New moving parts: none (a fix adds no new moving part)",
              "previous": ("\n\n".join(_previous(result) for result in history) or "- none")
                          + "\n\nSettled findings:\n" + _bullets(
                              f"{title} ({file}): {reason}" for (file, title), reason in settled.items()),
              "rulings": _rulings(top, base, history),
              "accepted": _accepted(top, item, history),
              "test_run": tested,
              "proof_list": proof_list(top, base) or "missing"}
    if "/" in item:
        doc_text, doc, row = task(top, item)
        parsed = story.parse(doc_text)
        covers = {int(n) for n in re.findall(r"\d+", row.get("covers", ""))}
        scope, tests = cells(row.get("scope", "")), cells(row.get("tests", ""))
        values.update(
            name=row.get("name", ""), delivers=row.get("what it delivers", ""),
            scope=_bullets(scope), tests=_bullets(tests),
            outside=_bullets(p for p in changed if not any(_within(p, s) for s in scope + tests)),
            covered=_bullets(story.item(parsed, n, True) for n in parsed["done"] if n in covers),
            context=_bullets(story.item(parsed, n, False) for n in parsed["done"] if n not in covers),
            risks=doc.get("Risks", "Risks: none"), notes=doc.get("Notes", "none"),
            moving_parts=moving_parts(doc_text))
        chosen = ["task", "proof-list", "rules"]
        if row.get("user-facing", "").lower() in ("yes", "true"):
            chosen.insert(1, "functional-check")
            values["functional_check"] = functional_check(top, base) or (
                "None: the worker's last commit message has no `Functional check:` paragraph.")
    else:
        chosen = ["fix", "proof-list", "rules"]
        if not cfg["interfaces"] and not state.get("allow_large"):
            chosen.insert(1, "promote")
    return "\n\n".join(blocks[name].substitute(values) for name in chosen)


def close_test(top: Path, base: str, *, closing: bool = True) -> str:
    """The command close runs: forge.toml's fast_test, with {base} as the merge base with `base`,
    else supported runner selection when CI runs test. Workers still run test."""
    cfg = repo.config(top)
    command = cfg["fast_test"] or cfg["test"]
    if closing and command and not cfg["fast_test"] and "tests" in cfg["checks"]:
        merge_base = repo.git("merge-base", base, "HEAD", cwd=top)
        code = (f"import sys; sys.path.insert(0, {str(Path(__file__).parents[1])!r}); "
                f"from forge.fasttest import close_tests; sys.exit(close_tests({merge_base!r}))")
        words = [sys.executable, "-c", code]
        return subprocess.list2cmdline(words) if os.name == "nt" else shlex.join(words)
    return command.replace("{base}", repo.git("merge-base", base, "HEAD", cwd=top)) if command else ""


def few_tests(top: Path, command: str, base: str) -> bool:
    """Forge's pytest picker narrowed to a few related test files ends in moments."""
    if not re.fullmatch(r"(?:uv run(?: --frozen| --python [\w.-]+)* )?"
                        r"forge test --pytest [0-9a-f]+", command.strip()):
        return False
    from forge import fasttest  # fasttest imports review in forge test

    test = repo.config(top)["test"]
    # Only Python tests are bounded by the picker's file count.
    if re.search(r"[;&|<>\r\n`$]", test):
        return False
    test = re.sub(r"^uv run(?: --frozen| --python [\w.-]+)* ", "", test.strip())
    try:
        words = shlex.split(test, posix=os.name != "nt")
    except ValueError:
        return False
    runner = Path(words[0].strip('"').replace("\\", "/")).name if words else ""
    if runner not in {"pytest", "pytest.exe"} and not (
            re.fullmatch(r"python[\d.]*(?:\.exe)?", runner) and words[1:3] == ["-m", "pytest"]):
        return False
    with contextlib.chdir(top):
        # Doctests collect from every module, not only the picked test files.
        if "doctest" in test or "doctest" in fasttest.pytest_options(words):
            return False
        picked = fasttest.related(repo.git("merge-base", base, "HEAD", cwd=top))
    # ponytail: a fixed count of files, not a time estimate; tune it if small runs crowd the cores.
    return not picked[2] and len(picked[0]) <= 5


# Close shows these fasttest lines, which a later runner's output can push out of the tail.
GAP = "No local test names "


def test_run(top: Path, command: str, base: str, *, always: bool = False,
             closing: bool = True) -> tuple[int, str]:
    """Run or skip tests and record their timing; report skip reasons and a bounded output tail."""
    branch = repo.current_branch(top)
    item = (branch_item(branch, top) or (branch, {}))[0]
    start, clock = repo.now(), time.monotonic()
    outcome = "skipped"
    results = results_path(top)
    # Close empties the results once, before the command; each pytest in it only appends.
    results.unlink(missing_ok=True)
    try:
        if not command:
            return 0, "forge.toml names no test command, so close ran none."
        # forge.toml's always_test runs on every change, settings and docs included.
        if not always and docs_only(top, base):
            said = DOCS_ONLY.format(command=command)
            return 0, said
        from forge import codex  # imports review indirectly

        passed = None if always else passed_record(top, command)
        skipped = SKIPPED.format(command=command)
        if passed and passed.exists():
            return 0, skipped
        entry = machine.join("test", top, item, None, None, small=few_tests(top, command, base))
        try:
            if passed and passed.exists():  # the close this one waited for passed the same files
                return 0, skipped
            from forge import fasttest

            workers = machine.test_cpus()
            # A worker's budget also caps a fixed xdist count; the option wins over the command's -n.
            cap = (f" --maxprocesses={workers}" if os.environ.get("FORGE_TEST_CPUS")
                   and fasttest.XDIST.search(command) else "")
            env = {**os.environ, "FORGE_WORKER": "1",
                   "PYTEST_XDIST_AUTO_NUM_WORKERS": workers, "FORGE_TEST_CPUS": workers,
                   "PYTEST_ADDOPTS": f"{os.environ.get('PYTEST_ADDOPTS', '')} -rs{cap}".strip()}
            # Every pytest the command starts, the client's own or Forge's picker, loads Forge's
            # results hook, which no command option can turn off.
            hook = repo.forge_dir(top) / "pytest"
            hook.mkdir(exist_ok=True)
            (hook / "_forge_test_results.py").write_text(fasttest.RESULTS, "utf-8")
            env.update(FORGE_TEST_RESULTS=str(results),
                       PYTHONPATH=os.pathsep.join([str(hook), os.environ.get("PYTHONPATH", "")]),
                       PYTEST_PLUGINS=",".join(filter(None, [os.environ.get("PYTEST_PLUGINS"),
                                                             "_forge_test_results"])))
            env.pop("FORGE_CLOSE_TESTS", None)
            if closing and "tests" in repo.config(top)["checks"]:
                env["FORGE_CLOSE_TESTS"] = "1"
            with repo.record_run(top, item, "test") as ran:
                log = repo.forge_dir(top) / f"test-{ran['run_id']}.log"
                entry.update(output_path=log.as_posix())
                with log.open("w", encoding="utf-8") as sink, subprocess.Popen(
                                      command, shell=True, cwd=top, env=env, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                      encoding="utf-8", errors="replace", **codex.GROUP) as process:
                    try:
                        machine.started(entry, process.pid)
                        output, total, completed, finished = [], None, 0, set()
                        for line in process.stdout:
                            sink.write(line)
                            sink.flush()
                            output.append(line)
                            found = re.search(r"collected (\d+) items?(.*)|\[(\d+) items?\]", line)
                            if found:
                                selected = re.search(r" / (\d+) selected", found[2] or "")
                                total = int(selected[1] if selected else found[1] or found[3])
                                completed = 0
                                finished.clear()
                            marks = re.search(r"(?:^|\s)([.FsxXE]+)\s+\[\s*\d+%\]", line)
                            result = re.search(r"(\S+::.*?)\s+(?:PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)\b.*\[\s*\d+%\]", line)
                            if not result and re.search(r"\[\s*\d+%\]", line):
                                result = re.search(r"\b(?:PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)\s+(\S+::.*?)\s*$", line)
                            tap = re.match(r"(?:ok|not ok) (\d+)\b|1\.\.(\d+)", line)
                            if tap and tap[2]:
                                total = int(tap[2])
                            if result:
                                finished.add(result[1])  # teardown errors repeat the same test's id
                                completed = len(finished)
                            elif tap and tap[1]:
                                completed = int(tap[1])
                            elif marks:
                                # A quiet error can be setup or a second report for teardown.
                                # Keep done unknown until a percentage gives an exact count.
                                completed = completed + len(marks[1]) if completed is not None and "E" not in marks[1] else None
                                if completed is None and total is not None:
                                    percent = int(re.search(r"(\d+)%", line)[1])
                                    lower, upper = (percent * total + 99) // 100, min(total, ((percent + 1) * total + 99) // 100 - 1)
                                    completed = lower if lower == upper else None
                            if found or marks or result or tap:
                                repo.record_progress(top, item, ran["run_id"], done=completed, total=total)
                                with machine._queue() as runs:
                                    for run in runs:
                                        if run["id"] == entry["id"]:
                                            run["progress"] = {"done": completed, "total": total}
                        done = subprocess.CompletedProcess(command, process.wait(), "".join(output))
                    except BaseException:
                        if process.poll() is None:
                            codex._stop(codex.identity(process.pid) or {"pid": process.pid}, True)
                            process.wait()
                        raise
                outcome = ran["outcome"] = "passed" if done.returncode == 0 else "failed"
            if done.returncode == 0 and passed:
                passed.parent.mkdir(exist_ok=True)
                # The run's per-test results, so a close that skips this run still lists them.
                passed.write_text(results.read_text("utf-8") if results.is_file() else "", "utf-8")
        finally:
            machine.leave(entry)
        out = [line.rstrip() for line in done.stdout.splitlines()]
        picked = sorted({i for n, line in enumerate(out) if "skip" in line.lower()
                         for i in (n - 1, n) if i >= 0} | set(range(max(0, len(out) - 30), len(out)))
                        | {n for n, line in enumerate(out) if line.startswith(GAP)})
        lines = [out[i] for i in picked]
        if len(lines) > 80:  # the tail is the last 30 picked; the earliest skip lines fill the rest
            lines = [*lines[:50], f"({len(lines) - 80} skip lines cut here)", *lines[-30:]]
        return done.returncode, "\n".join([f"`{command}` exited with status {done.returncode} on this machine.", *lines])
    except BaseException:
        outcome = "failed"
        raise
    finally:
        repo.record_timing(top, item, "test run", start, clock, outcome)


DOCS = ("docs/", "plans/", ".factory/")
def docs_only(top: Path, base: str) -> bool:
    """Close runs no tests for a change to settings, docs or Markdown alone, unless forge.toml
    names an always_test."""
    changed = repo.git("diff", "--name-only", "-z", "--no-renames", f"{base}...HEAD",
                       cwd=top).split("\0")
    return not repo.config(top)["always_test"] and all(
        path == "forge.toml" or path.startswith(DOCS) or path.endswith(".md") for path in changed if path)


DOCS_ONLY = ("This change touches only forge.toml, docs, plans, Markdown or Forge's records, so close "
             "did not run `{command}`.")
SKIPPED = ("`{command}` already passed on this machine on these same committed files, so close did "
           "not run it again.")


def passed_record(top: Path, command: str) -> Path | None:
    """Where this machine records that `command` passed on HEAD's committed files, Forge's own
    records aside (a review commit changes nothing the tests read). None when an uncommitted edit or
    untracked file could change the result, so such a run is never recorded or skipped."""
    if repo.git("status", "--porcelain", cwd=top):
        return None
    listing = repo.git("ls-tree", "-r", "-z", "--full-tree", "HEAD", cwd=top).split("\0")
    files = [entry for entry in listing if not entry.partition("\t")[2].startswith(".factory/")]
    key = hashlib.sha256("\0".join([command, *files]).encode("utf-8")).hexdigest()
    return machine._repos_file().parent / "passed-tests" / key


def _previous(result: dict[str, Any]) -> str:
    findings = result.get("findings", [])
    dismissals = {d["finding"]: d["because"] for d in result.get("dismissals", [])
                  if not d.get("accepted")}
    return "\n".join(
        f"{n}. {finding['priority']} {finding['title']} ({finding['file']}:{finding['line']}): "
        f"{finding['body']}" + (f"; dismissed because {dismissals[n]}" if n in dismissals else "")
        for n, finding in enumerate(findings, 1)) or "- none"


def _accepted(top: Path, item: str, history: list[dict[str, Any]]) -> str:
    """A task's kept or deferred plan read notes, then this item's below-bar and accepted findings."""
    from forge import story  # story imports review indirectly

    found = []
    if "/" in item:
        key = item.partition("/")[0]
        notes = story.show(top, f"story/{key}", f"plans/{key}.read.md") or story._text(top / "plans" / f"{key}.read.md")  # pyright: ignore[reportPrivateUsage]
        for number, block in story._findings(story._record(notes)[1]).items():  # pyright: ignore[reportPrivateUsage]
            kept = story.DISPOSITION.search(block)
            if kept and kept[1].lower() in ("keep", "defer"):
                found.append(f"Plan read note {number}: {' '.join(block.split(None, 1)[1].split())}")
    for (file, title), reason in _settled(history).items():  # every settled finding, whatever settled it
        scores = next((f"; {line[0].strip()}" for result in history for f in result.get("findings", [])
                       if (f["file"], f["title"]) == (file, title) and (line := score.LINE.search(f["body"]))), "")
        found.append(f"{title} ({file}): {reason}{scores}")
    return _bullets(found)


def _rulings(top: Path, base: str, history: list[dict[str, Any]]) -> str:
    """Every `Ruling:` line in the branch's commit messages, then evidence-based dismissals with
    their reasons, oldest first. Git holds both; Forge copies them, never stores them."""
    commits = list(reversed(repo.commit_log(top, base)))
    found = [line.strip() for _, message, _ in commits
             for line in message.splitlines() if line.startswith("Ruling:")]
    found += [part.strip() for _, message, _ in commits
              for part in re.findall(r"^Coordinator note:.*\Z", message, re.M | re.S)]
    for result in history:
        for dismissal in result.get("dismissals", []):
            if dismissal.get("accepted"):
                continue  # Human acceptance expires before a subsequent review.
            finding = result["findings"][dismissal["finding"] - 1]
            line = (f"{finding['title']} ({finding['file']}): dismissed because "
                    f"{dismissal['because']}")
            if line not in found:
                found.append(line)
    return _bullets(found)


def _history(top: Path, item: str, base: str, previous: dict[str, Any]) -> list[dict[str, Any]]:
    """Git owns earlier reviews; later dismissals replace that round's original result."""
    path = repo.state_path(item)
    rounds = {}
    for sha in repo.git("rev-list", "--reverse", "--first-parent", f"{base}..HEAD", "--", path,
                        cwd=top).split():
        result = json.loads(repo.git("show", f"{sha}:{path}", cwd=top)).get("review") or {}
        if result.get("commit"):  # one per round: two rounds at one commit differ in their findings
            rounds[result["commit"], str(result.get("findings"))] = result
    if previous.get("commit"):
        rounds[previous["commit"], str(previous.get("findings"))] = previous
    return list(rounds.values())


def _settled(history: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    """Earlier rounds' settled findings, one per identity under its first spelling."""
    settled, earlier, names = {}, set(), {}
    for result in history:
        current = {score.identity(f["file"], f["title"]) for f in result.get("findings", [])}
        names = {**{score.identity(f["file"], f["title"]): (f["file"], f["title"]) for f in result.get("findings", [])}, **names}
        for key in earlier - current:
            settled.setdefault(key, "fixed: absent from a later review")
        for finding in score.open_findings(result):
            if (outcome := score.bar(score.of(finding))) in ("follow-up", "live with"):
                settled.setdefault(score.identity(finding["file"], finding["title"]), f"known: below the bar ({outcome})")
        accepted = set()
        for dismissal in result.get("dismissals", []):
            finding = result["findings"][dismissal["finding"] - 1]
            key = score.identity(finding["file"], finding["title"])
            if dismissal.get("accepted"):
                accepted.add(key)
                settled[key] = "accepted by the owner: " + dismissal["because"]
            else:  # a repeat dismissed as known or accepted keeps that reason
                settled[key] = (dismissal["because"] if dismissal["because"].startswith(
                    ("known:", "accepted by the owner:")) else "dismissed because " + dismissal["because"])
        earlier = (earlier | current) - accepted
    return {names[key]: reason for key, reason in settled.items()}


def _cited_changed(top: Path, history: list[dict[str, Any]], key: tuple[str, str], head: str) -> bool:
    """Whether git's diff from the commit of the newest own (not carried) dismissal to head touches
    the line its `file:line` cites; a line only shifted by edits elsewhere counts as unchanged."""
    cited = None
    for result in history:
        for dismissal in result.get("dismissals", []):
            finding = result["findings"][dismissal["finding"] - 1]
            where = re.fullmatch(r"(.+):(\d+)", (dismissal["because"].split() or [""])[0])
            if (where and score.identity(finding["file"], finding["title"]) == key
                    and not dismissal.get("accepted") and not dismissal.get("carried")):
                cited = (result["commit"], where[1], int(where[2]))
    if not cited:
        return False  # no cited line to compare: the dismissal stands, as before
    commit, path, number = cited
    diff = repo.run("git", "diff", "-U0", "-M", commit, head, cwd=top)
    if diff.returncode:
        return True  # the dismissal's commit is gone: nothing proves the line unchanged
    old, header = "", False
    for line in diff.stdout.splitlines():
        if line.startswith("diff --git "):
            old, header = "", True
        elif header and line.startswith("--- "):
            old = line[6:] if line.startswith("--- a/") else ""
        elif header and line == "+++ /dev/null" and old == path:
            return True  # the cited file was deleted
        elif header and line.startswith("@@"):
            header = False
        if not header and old == path and (hunk := re.match(r"@@ -(\d+)(?:,(\d+))? ", line)):
            first, count = int(hunk[1]), int(hunk[2] or 1)
            if first <= number < first + count:
                return True
    return False


def functional_check(top: Path, base: str, head: str = "HEAD") -> str:
    """The worker's functional check: the `Functional check:` paragraph of its last commit message,
    to the end. That's the branch's newest commit that isn't a merge or only Forge's records (an
    empty commit counts); an older commit's check never counts. Git holds it; Forge copies it,
    never stores it."""
    return commit_paragraph(top, base, "Functional check:", head)


def commit_paragraph(top: Path, base: str, label: str, head: str = "HEAD") -> str:
    """Copy a labelled paragraph from the latest worker commit, never an older round's proof."""
    for _, message, files in repo.commit_log(top, base, head):
        if files and all(f.startswith(BOOKKEEPING) for f in files):
            continue
        # Any words between the label and its colon on that line still name the paragraph.
        found = re.search(r"^" + re.escape(label.removesuffix(":")) + r"\b[^\n]*?:.*",
                          message, re.M | re.S)
        return found[0].strip() if found else ""
    return ""


# A test file a proof list names, with an optional pytest node after it.
# A parameter id runs to its closing bracket, commas and all.
TEST_NAME = re.compile(r"(?<![\w/.-])(?:[\w.-]+/)*(?:test_[\w-]*|[\w-]+_test)\.py"
                       r"(?:::(?:[^\s,;`\[]+|\[[^\]]*\])+)?")


RESULT_WORDS = ("passed", "failed", "error", "skipped", "xfail", "xpass")


def results_path(top: Path) -> Path:
    """Where Forge's pytest hook writes this branch's last test run's per-test results."""
    branch = repo.current_branch(top)
    item = (branch_item(branch, top) or (branch, {}))[0]
    return repo.forge_dir(top) / f"test-results-{item.replace('/', '-')}.txt"


def _ran(name: str, node: str) -> bool:
    """A reported pytest node is the named test, or inside the named file or class. A name with a
    parameter id matches only that case. Node IDs can be relative to a test folder, so a name may
    end with the node."""
    parts = (node if "[" in name else re.sub(r"\[.*", "", node)).split("::")
    return any(name == part or name.endswith("/" + part)
               for part in ("::".join(parts[:i]) for i in range(1, len(parts) + 1)))


def proof_list(top: Path, base: str, report: str | None = None) -> str:
    """The proof list close writes from the worker's mapping of Done-when items to tests. It keeps
    the worker's words and puts each named test's result from close's run (`report`) next to it;
    a test the run did not run becomes `not run`. Before the run it names only the tests the
    branch has. A line or test close cannot match to its run's pytest results is `not checked`."""
    from forge import fasttest  # fasttest imports review in forge test

    command = close_test(top, base)
    passed, results = passed_record(top, command) if command else None, results_path(top)
    if passed and passed.is_file():  # a cached passing run's per-test results, if pytest ran
        report = passed.read_text("utf-8")
    elif report is not None:
        report = results.read_text("utf-8") if results.is_file() else ""
    worst = {}  # one result per test: the worst of its phases, so a failed teardown is an error
    for outcome, node in re.findall(r"^(\w+) (.+)$", report or "", re.M):
        worst[node] = max(worst.get(node, outcome), outcome,
                          key=lambda word: {"error": 2, "failed": 1}.get(word, 0))
    ran = [(outcome, node) for node, outcome in worst.items()]

    ran_none = not command or docs_only(top, base)  # close runs no tests for this change

    def result(found: re.Match) -> str:  # the worker's words stay; a name gains its result
        name = found[0].rstrip(".:)")
        path, _, test = name.partition("::")
        case = re.sub(r"\[.*", "", test.rsplit("::", 1)[-1])
        source = (top / path).read_text("utf-8", "replace") if (top / path).is_file() else ""
        matches = [(outcome, node) for outcome, node in ran if _ran(name, node)]
        if not source or case and not re.search(rf"\b{re.escape(case)}\b", source):
            said = "not run"
        elif ran_none and fasttest.RESULTS_HEADER not in (report or ""):
            said = "not run (close ran no tests for this change)"
        elif report is None:
            said = f"{name} (in the branch; close's test run gives its result)"
        elif fasttest.RESULTS_HEADER not in report:  # another runner, or no run
            said = f"{name} (not checked)"
        elif len(matches) == 1 and matches[0][1].rsplit("::", 1)[-1] == name.rsplit("::", 1)[-1]:
            # the named test itself; a name without its parameter id counts its cases
            said = f"{name} ({matches[0][0]} in close's run)"
        elif matches:  # a file, class or parametrized test: count the cases that ran
            counts = collections.Counter(outcome for outcome, _ in matches)
            said = f"{name} ({', '.join(f'{counts[word]} {word}' for word in RESULT_WORDS if counts[word])}" \
                   " in close's run)"
        else:
            said = "not run"  # a list never names a test close did not run
        return said + found[0][len(name):]

    lines = []
    for number, line in enumerate(commit_paragraph(top, base, "Proof list:").splitlines()):
        if not TEST_NAME.search(line):  # close cannot match a line without pytest names to its run
            lines.append(line if number == 0 or not line.strip() else f"{line} (not checked)")
            continue
        lines.append(TEST_NAME.sub(result, line))
    return "\n".join(lines)


def _bullets(items: Any) -> str:
    return "\n".join(f"- {item}" for item in items) or "- none"


def _within(path: str, entry: str) -> bool:
    """A changed path is inside a Scope entry: the same file, under the folder, or a glob match."""
    return path == entry or path.startswith(entry.rstrip("/") + "/") or fnmatch(path, entry)


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


def _sweep() -> None:
    """Delete the forge-review-* folders in the system temp folder last changed over a day ago:
    a review never runs that long, so they are what killed reviews and failed removals left."""
    day_ago = time.time() - 24 * 3600
    for folder in Path(tempfile.gettempdir()).glob("forge-review-*"):
        with contextlib.suppress(OSError):
            if folder.is_dir() and folder.stat().st_mtime < day_ago:
                shutil.rmtree(folder, ignore_errors=True)


def round_number(top: Path, item: str, state: dict[str, Any]) -> int | None:
    """Review attempts advance even when another review runs without a worker turn."""
    from forge import time_records

    steps = state.get("steps")
    finished = sum(step.get("step") == "review" for step in steps or [])
    events = [event for event in time_records.read(top, "events")
              if event.get("item") == item and event.get("event") == "review result"]
    recorded = [event["review_round"] for event in events
                if isinstance(event.get("review_round"), int)]
    timed = sum(timing.get("item") == item and timing.get("step") == "review"
                for timing in time_records.read(top, "timings"))
    if timed > len(events):
        return None  # An earlier timing-only attempt cannot establish an absolute ordinal.
    if not recorded and (finished or events or not isinstance(steps, list) and state.get("round") != 1):
        return None
    return max([finished, *recorded]) + 1


def run(top: Path, item: str, state: dict[str, Any], cfg: dict[str, Any],
        base: str, selected: dict[str, str], previous: dict[str, Any],
        signoff_prompt: str = "", light: bool = False, tested: str = "") -> dict[str, Any]:
    """Review the branch head once, retrying once when a run doesn't finish. Returns the result."""
    prompt = signoff_prompt or instructions(top, item, state, cfg, base, previous, tested)
    from forge import story  # story imports review indirectly
    block = (Path(__file__).parent / "templates" / "review.md").read_text(encoding="utf-8")
    if rules := story.agents_section(top, "Review rules"):
        own = block.split("<!-- review-rules -->\n", 1)[1].split("\n<!-- ", 1)[0]
        prompt += "\n\n" + string.Template(own.strip()).substitute(review_rules=rules)
    path = helper()
    head = repo.git("rev-parse", "HEAD", cwd=top)
    product = (sorted({name for command in (("ls-files", "-z"),
                                            ("ls-tree", "-r", "-z", "--name-only", head))
                       for name in repo.git(*command, cwd=top).split("\0")
                       if name and not name.startswith((*BOOKKEEPING, "docs/decisions/"))})
               if signoff_prompt else [])
    _sweep()
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
            prompt += _hide_generated(tree, repo.git("merge-base", review_base, head, cwd=tree), head)
        # The worker brief's standards page, as rules; a prompt file keeps it out of argv.
        rules = block.split("<!-- standards -->\n", 1)[1].split("\n<!-- ", 1)[0]
        # The branch may track this path, even as a link out of the tree: drop it unfollowed,
        # then create the file afresh ("x" refuses anything still there).
        repo.git("rm", "-r", "-f", "-q", "--ignore-unmatch", "--", STANDARDS, cwd=tree)
        with (tree / STANDARDS).open("x", encoding="utf-8") as page:
            page.write(prompt + "\n\n" + string.Template(rules).substitute(standards=(
                Path(__file__).parent / "standards.md").read_text(encoding="utf-8").strip()))
        engine = cfg["tools"]
        if engine == "both":
            engine = "codex" if shutil.which(os.environ.get("CODEX_BIN") or "codex") else "claude"
        argv = [sys.executable, str(path), "--mode", "branch", "--base", review_base,
                "--engine", engine,
                "--max-priority", "P3",  # the P0-only level applies after scoring
                "--prompt-file", STANDARDS,
                "--json-output", str(out)]
        launcher = _launcher(tmp / "bin", tree, engine)
        if launcher:
            argv += [f"--{engine}-bin", str(launcher)]
        with machine.agent_slot(top, "review", item):
            for attempt in ((1,) if signoff_prompt else (1, 2)):
                with repo.record_run(top, item, "review", family=engine) as ran:
                    findings, reason = _attempt(argv, tree, out, selected, top, item, ran["run_id"],
                                                strict=bool(signoff_prompt))
                    ran["outcome"] = "failed" if reason else "completed"
                    ran.update(selected, **_spent(tmp / SPENT))
                if not reason:
                    break
                print(f"Autoreview run {attempt} did not finish: {reason}.", file=sys.stderr)
        if signoff_prompt:
            serious = [f for f in findings if score.holds(f)]
            repo.record_event(top, item, "review result", commit=head,
                review_round=round_number(top, item, state),
                outcome="failed" if reason else "blocked" if serious else "clean",
                findings=None if reason else [{key: finding[key] for key in
                    ("title", "priority", "file")} for finding in findings])
            if reason:
                repo.refuse(("The sign-off review did not finish: " + reason + ".",
                             "check Autoreview, then forge decision accept client-signoff --by \"<name>\""))
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
    history = _history(top, item, base, previous)
    settled = {score.identity(*key): reason for key, reason in _settled(history).items()}
    findings = [finding for finding in findings if not settled.get(
        score.identity(finding["file"], finding["title"]), "").startswith("fixed:")]
    dismissals = [{"finding": number, "because": reason.removeprefix("dismissed because "), "carried": True}
                  for number, finding in enumerate(findings, 1)
                  if (reason := settled.get(key := score.identity(finding["file"], finding["title"]), ""))
                  and not (reason.startswith("dismissed because ") and _cited_changed(top, history, key, head))]
    result = {"findings": findings, "dismissals": dismissals,
              "blocking_level": "P0" if light else "P1"}
    identity = repo.record_event(top, item, "review result", commit=head,
                                 review_round=round_number(top, item, state),
                                 outcome="blocked" if blocking(result) else "clean",
                                 findings=[{key: finding[key] for key in ("title", "priority", "file")}
                                           for finding in findings])
    return {"id": identity, "commit": head, **result,
            **{key: fingerprint(head, item, top, state, base, "P0" if light else "P1", findings,
                                branch_diff=key == "branch_diff") for key in ("changed", "branch_diff")}}


def _hide_generated(tree: Path, start: str, head: str) -> str:
    """Check out, in the review tree, head with each changed file .gitattributes marks
    linguist-generated put back as it was at start, so its contents stay out of the reviewed diff.
    Returns the lines naming those files with their changed-line counts, or "" when there are none."""
    counts = {}
    for record in repo.git("diff", "--numstat", "-z", "--no-renames", start, head,
                           cwd=tree).split("\0"):
        added, _, rest = record.partition("\t")
        removed, _, path = rest.partition("\t")
        if path:
            counts[path] = (added, removed)
    attrs = repo.run("git", "check-attr", "--stdin", "-z", "linguist-generated", cwd=tree,
                     input="\0".join(counts)).stdout.split("\0")
    generated = [path for path, value in zip(attrs[::3], attrs[2::3]) if value in ("set", "true")]
    if not generated:
        return ""
    repo.git("restore", f"--source={start}", "--staged", "--", *generated, cwd=tree)
    snapshot = repo.git("commit-tree", repo.git("write-tree", cwd=tree), "-p", head,
                        "-m", "Branch head without generated files' contents", cwd=tree)
    repo.git("checkout", "-q", "-f", "--detach", snapshot, cwd=tree)
    return ("\n\n## Generated files\n\nThese files are marked linguist-generated in .gitattributes, "
            "so their contents are left out of the diff:\n"
            + _bullets(f"{path}: {counts[path][0]} added, {counts[path][1]} removed"
                       for path in generated))


def signoff(top: Path, answers: str) -> str:
    """Review every tracked product file once, against an empty root, before client acceptance."""
    skill = (Path(__file__).parent / "templates" / "skill.md").read_text(encoding="utf-8")
    table = re.search(r"^\| Topic \|.*?(?=\n\n)", skill, re.M | re.S)
    block = (Path(__file__).parent / "templates" / "review.md").read_text(encoding="utf-8")
    prompt = string.Template(block.split("<!-- signoff -->\n", 1)[1]).substitute(
        answers=answers, topics=table[0] if table else "")
    cfg = repo.config(top)
    return run(top, "client-signoff", {}, cfg, "", {}, {}, signoff_prompt=prompt)["commit"]


def _attempt(argv: list[str], cwd: Path, out: Path,
             selected: dict[str, str], top: Path, item: str, run_id: str,
             strict: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Run Autoreview once: its findings, or the reason the run doesn't count."""
    from forge import codex  # importing it here avoids sync's hook-import cycle
    out.unlink(missing_ok=True)
    proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env={**os.environ, "FORGE_WORKER": "1"},
                            **codex.GROUP)
    with proc, machine.agent_process(proc):
        last = ""
        for line in proc.stdout or []:  # streamed as bytes: its progress is how a person watches it
            line = line.replace(b"\0", b"")
            sys.stderr.buffer.write(line)
            sys.stderr.flush()
            last = line.decode("utf-8", "replace").strip() or last
            if last.startswith("model: "):
                selected["model"] = last.removeprefix("model: ")
            elif last.startswith("thinking: "):
                selected["effort"] = last.removeprefix("thinking: ")
            elif match := re.fullmatch(
                    r"codex model \S+ is unavailable for this account; retrying with (\S+)", last):
                selected["model"] = match[1]
            if line.strip():
                repo.record_progress(top, item, run_id, step=" ".join(last.split()), **selected)
        code = proc.wait()
    try:
        # Decode first: JSON represents null characters as escaped text.
        report = json.loads(out.read_text(encoding="utf-8"), object_hook=lambda fields: {
            key: value.replace("\0", "") if isinstance(value, str) else value
            for key, value in fields.items()})
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


def _spent(path: Path) -> dict[str, Any]:
    """The review engine's token use summed over its runs (a chunked review has one per pass,
    a retry one more) and its first chat, read once: Codex's `exec --json` events or Claude's
    results."""
    runs: list[dict[str, Any]] = []
    with contextlib.suppress(OSError):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            usage = event.get("usage")
            if event.get("type") == "thread.started":
                runs.append({"chat": event.get("thread_id")})
            elif event.get("type") == "turn.completed" and isinstance(usage, dict) and runs:
                # Codex reports the thread's running total, so its last turn holds the run's use.
                runs[-1].update({key: usage.get(key) for key in TOKENS})
            elif event.get("type") == "result" and isinstance(usage, dict):
                runs.append({"chat": event.get("session_id"), **repo.claude_tokens(usage)})
        path.unlink()
    if not runs:
        return {}
    return {"chat": runs[0]["chat"], **{key: sum(counts) if (counts := [
        run[key] for run in runs if isinstance(run.get(key), int)]) else None for key in TOKENS}}


def _finding(raw: Any) -> dict[str, Any] | None:
    """The fields Forge uses from one finding, or None when they can't be read."""
    where = raw.get("code_location") if isinstance(raw, dict) else None
    if not isinstance(where, dict) or raw.get("priority") not in PRIORITIES:
        return None
    title = str(raw.get("title", ""))
    scores, body = score.normalise(title, str(raw.get("body", "")))
    if not scores:  # a new finding must carry its score line
        return None
    return {"priority": raw["priority"], "title": title, "body": body,
            "gain": scores[0], "work": scores[1], "harm": scores[2],
            "file": str(where.get("file_path", "")), "line": where.get("line", 0)}


def _launcher(folder: Path, tree: Path, engine: str) -> Path | None:
    """A `codex` or `claude` for the helper that runs the real one inside the reviewed checkout."""
    real = shutil.which(os.environ.get(f"{engine.upper()}_BIN") or engine)
    if not real:
        return None  # the helper then finds no such engine itself and says so
    # ponytail: the old launcher also carried the Windows elevated-sandbox setting through the
    # helper's --ignore-user-config; port it when a Windows review can't run its read-only shell.
    folder.mkdir()
    script = folder / f"{engine}_in_tree.py"
    from forge.codex import QUIET
    quiet = [arg for key, value in QUIET.items() for arg in ("-c", f"{key}={json.dumps(value)}")]
    script.write_text(LAUNCHER.format(engine=engine, tree=str(tree), real=real, quiet=quiet,
                                      spent=str(folder.parent / SPENT)), encoding="utf-8")
    if os.name == "nt":
        launcher = folder / f"{engine}.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = folder / engine
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n',
                            encoding="utf-8")
        launcher.chmod(0o755)
    return launcher
