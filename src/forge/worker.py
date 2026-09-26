"""forge work: build the worker's brief and run the worker on a task or fix in its own checkout."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from string import Template
from typing import Any

from forge import codex, doctor, repo, task
from forge.repo import git, refuse

HERE = Path(__file__).parent
# The shipped how-to per concern of the client stack; the brief names it and the worker may read it.
CONVENTIONS = (HERE / "templates" / "conventions").resolve()
# Where a repo keeps its tests: a test folder anywhere, or a test file next to its code.
TEST_PATHS = [":(glob)**/test*/**", ":(glob)**/*.test.*", ":(glob)**/*.spec.*",
              ":(glob)**/test_*.py", ":(glob)**/*_test.py"]
SERIOUS = ("P0", "P1")
# The worker edits files in its checkout and may run only these commands, plus the repo's test.
COMMANDS = ["git add", "git commit", "git status", "git diff", "git log"]

REFUSALS = {
    "no_checkout": ("{item} has no checkout here, so it hasn't been started.", "forge next"),
    "failed": ("The worker stopped with exit code {status}; its log is {log}.", "forge work {item}"),
    "sdk": ("{problem}", "forge doctor --fix"),
    "untrusted": ("Codex doesn't trust this project, so it would skip Forge's hooks; Forge starts "
                  "no Codex worker here.", "forge doctor"),
    "turn": ("The Codex turn didn't complete: {why}; its log is {log}.", "forge work {item}"),
}


def work(args: argparse.Namespace) -> None:
    item = args.item
    match = repo.ITEM.fullmatch(item)
    if not match or not (match["task"] or match["fix"]):
        refuse(repo.REFUSALS["bad_item"], item=item)
    top = _checkout(item, [f"task/{match['key']}-{match['task']}"] if match["task"]
                    else [f"fix/{item}", f"forge/{item}"])
    config = repo.config(top)  # the item's own forge.toml, not the caller's
    on_codex = config["workers"] == "codex"
    kind = "Build" if match["task"] else "Lite"
    # Every check refuses before the status commit, so a refused call changes nothing.
    if on_codex:
        problem = codex.sdk_problem()  # includes the declining handler's place in the SDK
        if problem:
            refuse(REFUSALS["sdk"], problem=problem)
        codex.settings(config, kind)
        codex_config = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
        if not doctor._codex_trusts(top, codex_config):
            refuse(REFUSALS["untrusted"])
    else:
        claude = _claude_models(config, kind.lower())
    state = repo.read_state(item, top) or {}
    findings, failing = _fix_round(state)
    brief, subject = _brief(match, top, state, findings, failing)
    state["status"] = "fixing" if findings or failing else "working"
    repo.commit_state(f"{item} is {state['status']}", repo.write_state(item, state, top), top=top)
    if not on_codex:
        _run(item, top, config, brief, claude)
        return
    result = codex.run(top, item, kind, f"{kind} · {item} · {subject}", brief, "full-access")
    if result["status"] != "completed":
        why = (f"Codex reported it {result['status']}" if result["status"]
               else "Codex never reported its end")
        refuse(REFUSALS["turn"], why=why, log=repo.work_log(top, item), item=item)


def _claude_models(config: dict[str, Any], kind: str) -> list[str]:
    """claude's --model and --effort for this kind of work; the single `model` without a table."""
    if not config["models"]:
        return ["--model", config["model"]]
    chosen = repo.models(config, kind)
    if "subagents" in chosen:
        refuse(repo.REFUSALS["models"], problem=f"Claude workers take model and effort, so "
                                                 f"[models.{kind}] can't set subagents")
    return ["--model", chosen["model"], "--effort", chosen["effort"]]


def _checkout(item: str, branches: list[str]) -> Path:
    """The worktree where the item's branch is checked out."""
    for block in git("worktree", "list", "--porcelain").split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines())
        if fields.get("branch", "").removeprefix("refs/heads/") in branches:
            return Path(fields["worktree"])
    refuse(REFUSALS["no_checkout"], item=item)


def _fix_round(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """The open serious findings and the failing checks, once close has reviewed the item."""
    review = state.get("review")
    if not review:  # no close yet: a first build, with no pull request to read checks from
        return [], []
    dismissed = {entry.get("finding") for entry in review.get("dismissals") or []}
    findings = [finding for n, finding in enumerate(review.get("findings") or [], 1)
                if finding.get("priority") in SERIOUS and n not in dismissed]
    return findings, _failing(state.get("branch", ""))


def _failing(branch: str) -> list[tuple[str, str]]:
    """Each failing check on the branch's pull request, with the tail of its log."""
    try:  # gh exits non-zero when a check fails, so read what it printed either way
        checks = json.loads(repo.run("gh", "pr", "checks", branch, "--json", "name,bucket,link").stdout)
    except ValueError:  # no pull request yet
        return []
    failing = []
    for check in checks if isinstance(checks, list) else []:
        if check.get("bucket") == "fail":
            job = re.search(r"/job/(\d+)", check.get("link") or "")
            log = repo.run("gh", "run", "view", "--job", job[1], "--log-failed").stdout if job else ""
            failing.append((check.get("name", "a check"), "\n".join(log.splitlines()[-30:])))
    return failing


def _brief(match: re.Match[str], top: Path, state: dict[str, Any],
           findings: list[dict[str, Any]], failing: list[tuple[str, str]]) -> tuple[str, str]:
    """The brief from templates/brief.md, where `<!-- if NAME -->` blocks stay only when NAME is
    on, and its subject: the task's name, or the fix's why."""
    on: set[str] = set()
    values: dict[str, str] = {}
    if match["task"]:
        doc = task.sections((top / "plans" / f"{match['key']}.md").read_text(encoding="utf-8"))
        row = task.rows(doc).get(match["task"], {})
        subject = row.get("Name", "")
        moving = re.search(r"^New moving parts:.*", doc.get("Tasks", ""), re.M | re.S)
        on |= {"task"} | ({"user-facing"} if row.get("User-facing", "").lower() in ("yes", "true")
                          else set())
        values.update(
            title=doc["#"], what=doc.get("What changes for you", ""), why=doc.get("Why", ""),
            done=doc.get("Done when", ""), risks=doc.get("Risks", ""), notes=doc.get("Notes", ""),
            moving=moving[0].strip() if moving else "New moving parts: none",
            row="\n".join(f"| {' | '.join(cells)} |" for cells in (
                list(row), ["---"] * len(row), list(row.values()))),
            covers=row.get("Covers", ""), scope=row.get("Scope", ""), tests=row.get("Tests", ""),
            existing_tests=_existing_tests(top, task.cell_list(row.get("Scope", ""))))
    else:
        on.add("fix")
        subject = state.get("why", "")
        values.update(why=subject, done=state.get("done_when", ""))
    if findings or failing:
        on.add("fix-round")
        values["findings"] = "\n".join(
            f"- {f.get('priority')} {f.get('title', '')} "
            f"({':'.join(str(p) for p in (f.get('file'), f.get('line')) if p) or 'no file'}): "
            f"{f.get('body', '')}"
            for f in findings) or "None."
        values["checks"] = "\n\n".join(
            f"### {name}\n\n```\n{tail}\n```" for name, tail in failing) or "None."
    standards = HERE / "standards.md"
    if standards.is_file():  # ponytail: DOCS-STANDARDS ships the standards page
        on.add("standards")
        values["standards"] = standards.read_text(encoding="utf-8").strip()
    values["conventions"] = str(CONVENTIONS)
    text = (HERE / "templates" / "brief.md").read_text(encoding="utf-8")
    text = re.sub(r"<!-- if ([\w-]+) -->\n(.*?)<!-- end -->\n",
                  lambda block: block[2] if block[1] in on else "", text, flags=re.S)
    return Template(text).safe_substitute(values), subject


def _existing_tests(top: Path, scope: list[str]) -> str:
    """The checkout's test files that name a Scope file or folder, listed for the brief."""
    # ponytail: a whole-word match on each entry's last plain name (`board` for `web/board.py`), so
    # a common name such as `index` lists more tests than it should; match imports if that's noisy.
    names = sorted({Path(plain[-1]).stem for entry in scope
                    if (plain := [p for p in Path(entry).parts if not set(p) & set("*?[")])})
    patterns = [arg for name in names for arg in ("-e", name)]
    found = repo.run("git", "grep", "-l", "-w", "-F", *patterns, "--", *TEST_PATHS,
                     cwd=top).stdout.splitlines() if names else []
    return ", ".join(f"`{path}`" for path in found) or "none found"


def _run(item: str, top: Path, config: dict[str, Any], brief: str, models: list[str]) -> None:
    """Run Claude Code headless in the checkout; its output goes to the terminal and the log."""
    exe = shutil.which("claude")
    if exe is None:
        refuse(repo.REFUSALS["missing_tool"], tool="claude")
    log = repo.work_log(top, item)
    allowed = [f"Bash({command}:*)" for command in [*COMMANDS, config["test"]] if command]
    command = [exe, "-p", *models, "--permission-mode", "acceptEdits",
               "--add-dir", str(CONVENTIONS), "--allowedTools", *allowed]
    with log.open("a", encoding="utf-8") as out, subprocess.Popen(
            command, cwd=top, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as worker:
        out.write(f"--- forge work {item} at {repo.now()}\n")
        worker.stdin.write(brief)
        worker.stdin.close()
        for line in worker.stdout:
            print(line, end="", flush=True)
            out.write(line)
    if worker.returncode:
        refuse(REFUSALS["failed"], status=worker.returncode, log=log, item=item)
