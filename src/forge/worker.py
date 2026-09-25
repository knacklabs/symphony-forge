"""forge work: build the worker's brief and run the worker on a task or fix in its own checkout."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from string import Template
from typing import Any

from forge import repo, task
from forge.repo import git, refuse

HERE = Path(__file__).parent
SERIOUS = ("P0", "P1")
# The worker edits files in its checkout and may run only these commands, plus the repo's test.
COMMANDS = ["git add", "git commit", "git status", "git diff", "git log"]

REFUSALS = {
    "codex": ("Codex workers come with the warm-threads story; v1 runs its workers on Claude Code.",
              'set workers = "claude" in forge.toml, then forge work {item}'),
    "no_checkout": ("{item} has no checkout here, so it hasn't been started.", "forge next"),
    "failed": ("The worker stopped with exit code {status}; its log is {log}.", "forge work {item}"),
}


def work(args: argparse.Namespace) -> None:
    item = args.item
    match = repo.ITEM.fullmatch(item)
    if not match or not (match["task"] or match["fix"]):
        refuse(repo.REFUSALS["bad_item"], item=item)
    config = repo.config()
    if config["workers"] == "codex":
        refuse(REFUSALS["codex"], item=item)
    top = _checkout(item, [f"task/{match['key']}-{match['task']}"] if match["task"]
                    else [f"fix/{item}", f"forge/{item}"])
    state = repo.read_state(item, top) or {}
    findings, failing = _fix_round(state)
    brief = _brief(match, top, state, findings, failing)
    state["status"] = "fixing" if findings or failing else "working"
    repo.commit_state(f"{item} is {state['status']}", repo.write_state(item, state, top), top=top)
    _run(item, top, config, brief)


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
           findings: list[dict[str, Any]], failing: list[tuple[str, str]]) -> str:
    """The brief from templates/brief.md: `<!-- if NAME -->` blocks stay only when NAME is on."""
    on: set[str] = set()
    values: dict[str, str] = {}
    if match["task"]:
        doc = task.sections((top / "plans" / f"{match['key']}.md").read_text(encoding="utf-8"))
        row = task.rows(doc).get(match["task"], {})
        moving = re.search(r"^New moving parts:.*", doc.get("Tasks", ""), re.M | re.S)
        on |= {"task"} | ({"user-facing"} if row.get("User-facing", "").lower() in ("yes", "true")
                          else set())
        values.update(
            title=doc["#"], what=doc.get("What changes for you", ""), why=doc.get("Why", ""),
            done=doc.get("Done when", ""), risks=doc.get("Risks", ""), notes=doc.get("Notes", ""),
            moving=moving[0].strip() if moving else "New moving parts: none",
            row="\n".join(f"| {' | '.join(cells)} |" for cells in (
                list(row), ["---"] * len(row), list(row.values()))),
            covers=row.get("Covers", ""), scope=row.get("Scope", ""), tests=row.get("Tests", ""))
    else:
        on.add("fix")
        values.update(why=state.get("why", ""), done=state.get("done_when", ""))
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
    text = (HERE / "templates" / "brief.md").read_text(encoding="utf-8")
    text = re.sub(r"<!-- if ([\w-]+) -->\n(.*?)<!-- end -->\n",
                  lambda block: block[2] if block[1] in on else "", text, flags=re.S)
    return Template(text).safe_substitute(values)


def _run(item: str, top: Path, config: dict[str, Any], brief: str) -> None:
    """Run Claude Code headless in the checkout; its output goes to the terminal and the log."""
    exe = shutil.which("claude")
    if exe is None:
        refuse(repo.REFUSALS["missing_tool"], tool="claude")
    log = repo.forge_dir(top) / f"work-{item.replace('/', '-')}.log"
    allowed = [f"Bash({command}:*)" for command in [*COMMANDS, config["test"]] if command]
    command = [exe, "-p", "--model", config["model"], "--permission-mode", "acceptEdits",
               "--allowedTools", *allowed]
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
