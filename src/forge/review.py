"""One review round: Autoreview over the branch in a read-only checkout, and its committed result.

Autoreview is a third-party black box. Forge reads only the fields it uses (each finding's
priority, title, body and code_location, in findings and scope_rejected_findings, then
review_status and overall_correctness) and ignores everything else it writes.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from forge import machine, repo, spotted
from forge.task import branch_item, sections

# The helper Forge runs: the upstream commit its installer stamps in the skill's .upstream-sha.
AUTOREVIEW_PIN = "ce14dcca09b3affb922ddcca11465619e67f5114"
# Its standard installs: the Codex skills folder, then the Claude one.
HELPERS = [Path.home() / host / "skills" / "autoreview" / "scripts" / "autoreview"
           for host in (".codex", ".claude")]
PRIORITIES = ("P0", "P1", "P2", "P3")
# Untracked in the review tree, which branch mode leaves out of the diff.
STANDARDS = "forge-standards.md"
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
sys.exit(subprocess.call([{real!r}, *argv], cwd={tree!r}))
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
            (f.get("priority") in (("P0",) if result.get("blocking_level") == "P0" else SERIOUS)
             and n not in dismissed)]


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
    values = {"why": state.get("why", ""), "done_when": state.get("done_when", ""),
              "allowance": state.get("allow_large") or "No recorded allowance",
              "moving_parts": "New moving parts: none (a fix adds no new moving part)",
              "previous": _previous(previous), "rulings": _rulings(top, item, base),
              "test_run": tested,
              "proof_list": commit_paragraph(top, base, "Proof list:") or "missing"}
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


def close_test(top: Path, base: str) -> str:
    """The command close runs: forge.toml's fast_test, with {base} as the merge base with `base`,
    else its test. The pull request's tests check always runs test."""
    cfg = repo.config(top)
    command = cfg["fast_test"] or cfg["test"]
    return command.replace("{base}", repo.git("merge-base", base, "HEAD", cwd=top)) if command else ""


def test_run(top: Path, command: str, base: str, *, always: bool = False) -> tuple[int, str]:
    """Run or skip tests and record their timing; report skip reasons and a bounded output tail."""
    branch = repo.current_branch(top)
    item = (branch_item(branch, top) or (branch, {}))[0]
    start, clock = repo.now(), time.monotonic()
    outcome = "skipped"
    try:
        if not command:
            return 0, "forge.toml names no test command, so close ran none."
        if not always:
            changed = repo.git("diff", "--name-only", "-z", "--no-renames", f"{base}...HEAD",
                               cwd=top).split("\0")
            if all(path == "forge.toml" or path.startswith(DOCS) or path.endswith(".md")
                   for path in changed if path):
                said = DOCS_ONLY.format(command=command)
                print(said, flush=True)
                return 0, said
        from forge import codex  # codex imports review indirectly

        passed = None if always else passed_record(top, command)
        skipped = SKIPPED.format(command=command)
        if passed and passed.exists():
            print(skipped, flush=True)
            return 0, skipped
        entry = machine.join("test", top, item, None, None)
        try:
            if passed and passed.exists():  # the close this one waited for passed the same files
                print(skipped, flush=True)
                return 0, skipped
            workers = str(machine.half_cores())
            env = {**os.environ, "FORGE_WORKER": "1",
                   "PYTEST_XDIST_AUTO_NUM_WORKERS": workers, "FORGE_TEST_CPUS": workers,
                   "PYTEST_ADDOPTS": f"{os.environ.get('PYTEST_ADDOPTS', '')} -rs".strip()}
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
                passed.touch()
        finally:
            machine.leave(entry)
        out = [line.rstrip() for line in done.stdout.splitlines()]
        picked = sorted({i for n, line in enumerate(out) if "skip" in line.lower()
                         for i in (n - 1, n) if i >= 0} | set(range(max(0, len(out) - 30), len(out))))
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


def _rulings(top: Path, item: str, base: str) -> str:
    """Every `Ruling:` line in the branch's commit messages, then evidence-based dismissals with
    their reasons, oldest first. Git holds both; Forge copies them, never stores them."""
    commits = list(reversed(repo.commit_log(top, base)))
    found = [line.strip() for _, message, _ in commits
             for line in message.splitlines() if line.startswith("Ruling:")]
    path = repo.state_path(item)
    for sha in repo.git("rev-list", "--reverse", f"{base}..HEAD", "--", path,
                        cwd=top).split():
        result = json.loads(repo.git("show", f"{sha}:{path}", cwd=top)).get("review") or {}
        for dismissal in result.get("dismissals", []):
            if dismissal.get("accepted"):
                continue  # Human acceptance expires before a subsequent review.
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
    return commit_paragraph(top, base, "Functional check:", head)


def commit_paragraph(top: Path, base: str, label: str, head: str = "HEAD") -> str:
    """Copy a labelled paragraph from the latest worker commit, never an older round's proof."""
    for _, message, files in repo.commit_log(top, base, head):
        if files and all(f.startswith(BOOKKEEPING) for f in files):
            continue
        found = re.search(r"^" + re.escape(label) + r".*", message, re.M | re.S)
        return found[0].strip() if found else ""
    return ""


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
            page.write(string.Template(rules).substitute(standards=(
                Path(__file__).parent / "standards.md").read_text(encoding="utf-8").strip()))
        engine = "codex" if shutil.which(os.environ.get("CODEX_BIN") or "codex") else "claude"
        # ponytail: the instructions ride in argv; move them to --prompt-file inside the review
        # tree if a story's text ever nears Windows' 32K command line.
        argv = [sys.executable, str(path), "--mode", "branch", "--base", review_base,
                "--engine", engine,
                "--max-priority", "P0" if light else "P3", "--prompt", prompt,
                "--prompt-file", STANDARDS,
                "--json-output", str(out)]
        # The light prototype review runs Sol at medium on Codex; otherwise forge.toml's review kind
        # for the engine's family, and on Claude with no Claude review entry, its Claude cold-read model.
        chosen = ({"model": "gpt-6.1-sol", "effort": "medium"} if light and engine == "codex" else
                  repo.models(cfg, "review", engine)
                  or (repo.models(cfg, "grill", "claude") if engine == "claude" else {}))
        if chosen:
            argv += ["--model", f"{engine}={chosen['model']}"]
            argv += ["--thinking", f"{engine}={chosen['effort']}"] if "effort" in chosen else []
        launcher = _launcher(tmp / "bin", tree, engine)
        if launcher:
            argv += [f"--{engine}-bin", str(launcher)]
        with machine.agent_slot(top, "review", item, **chosen):
            for attempt in ((1,) if signoff_prompt else (1, 2)):
                with repo.record_run(top, item, "review", family=engine, **chosen) as ran:
                    findings, reason = _attempt(argv, tree, out, selected, top, item, ran["run_id"],
                                                strict=bool(signoff_prompt))
                    ran["outcome"] = "failed" if reason else "completed"
                if not reason:
                    break
                print(f"Autoreview run {attempt} did not finish: {reason}.", file=sys.stderr)
        if signoff_prompt:
            serious = [f for f in findings if f["priority"] in SERIOUS]
            repo.record_event(top, item, "review result", commit=head,
                review_round=round_number(top, item, state),
                outcome="failed" if reason or selected.get("model") != "gpt-6.1-sol"
                or selected.get("effort") != "high" else "blocked" if serious else "clean",
                findings=None if reason else [{key: finding[key] for key in
                    ("title", "priority", "file")} for finding in findings])
            if reason:
                repo.refuse(("The sign-off review did not finish: " + reason + ".",
                             "check Autoreview, then forge decision accept client-signoff --by \"<name>\""))
            if selected.get("model") != "gpt-6.1-sol" or selected.get("effort") != "high":
                repo.refuse(("The sign-off review did not confirm GPT-6.1 Sol at high effort: "
                             "model and effort must match.",
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
    identity = repo.record_event(top, item, "review result", commit=head,
                                 review_round=round_number(top, item, state),
                                 outcome="blocked" if any(f["priority"] in
                                 (("P0",) if light else SERIOUS) for f in findings) else "clean",
                                 findings=[{key: finding[key] for key in ("title", "priority", "file")}
                                           for finding in findings])
    return {"id": identity, "commit": head, "findings": findings,
            "dismissals": [], "blocking_level": "P0" if light else "P1",
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
    cfg = {"models": {"review": {"model": "gpt-6.1-sol", "effort": "high"}}}
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


def _finding(raw: Any) -> dict[str, Any] | None:
    """The fields Forge uses from one finding, or None when they can't be read."""
    where = raw.get("code_location") if isinstance(raw, dict) else None
    if not isinstance(where, dict) or raw.get("priority") not in PRIORITIES:
        return None
    return {"priority": raw["priority"], "title": str(raw.get("title", "")),
            "body": str(raw.get("body", "")), "file": str(where.get("file_path", "")),
            "line": where.get("line", 0)}


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
    script.write_text(LAUNCHER.format(engine=engine, tree=str(tree), real=real, quiet=quiet), encoding="utf-8")
    if os.name == "nt":
        launcher = folder / f"{engine}.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = folder / engine
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n',
                            encoding="utf-8")
        launcher.chmod(0o755)
    return launcher
