"""Autoreview's process output and finding schema at the external tool boundary."""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from forge import machine, repo, score

PRIORITIES = ("P0", "P1", "P2", "P3")
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def hide_generated(tree: Path, start: str, head: str) -> str:
    """Summarize deletions and generated files in the temporary review tree, without content."""
    deleted = repo.git("diff", "--name-only", "--diff-filter=D", "-z", "--no-renames",
                       start, head, cwd=tree).split("\0")
    deleted = [path for path in deleted if path]
    counts = {row[2]: row[:2] for record in repo.git(
        "diff", "--numstat", "--diff-filter=d", "-z", "--no-renames", start, head,
        cwd=tree).split("\0") if len(row := record.split("\t", 2)) == 3}
    attrs = repo.run("git", "check-attr", "--stdin", "-z", "linguist-generated", cwd=tree,
                     input="\0".join(counts)).stdout.split("\0")
    marked = {path for path, value in zip(attrs[::3], attrs[2::3]) if value in ("set", "true")}
    generated = []
    for path, count in counts.items():
        if path in marked or "-" in count or path.lower().endswith((".map", ".min.js", ".min.css")):
            generated.append(path)
            continue
        # Either side can contain the old minified bundle, even when the new file is readable.
        for ref in (start, head):
            blob = repo.run("git", "cat-file", "blob", f"{ref}:{path}", cwd=tree)
            lines = blob.stdout.splitlines() if blob.returncode == 0 else []
            if sum(len(line) > 1000 for line in lines) > len(lines) / 2:
                generated.append(path)
                break
    omitted = deleted + generated
    if not omitted:
        return ""
    sizes = {}
    for ref in (start, head):
        sizes[ref] = {path: fields[3] for record in repo.git(
            "ls-tree", "-r", "-l", "-z", ref, cwd=tree).split("\0")
            if (path := record.partition("\t")[2])
            and len(fields := record.partition("\t")[0].split()) == 4}
    # Feed paths on stdin: large folder removals must not exceed Windows' argv limit.
    repo.run("git", "--literal-pathspecs", "restore", f"--source={start}", "--staged",
             "--pathspec-from-file=-", "--pathspec-file-nul", cwd=tree,
             input="\0".join(omitted) + "\0").check_returncode()
    snapshot = repo.git("commit-tree", repo.git("write-tree", cwd=tree), "-p", head,
                        "-m", "Branch head without deleted and generated files' contents", cwd=tree)
    repo.git("checkout", "-q", "-f", "--detach", snapshot, cwd=tree)
    summaries = [f"deleted: {path} ({sizes[start][path]} bytes)" for path in deleted]
    summaries += [f"generated: {path} ({sizes[head][path]} bytes)\n"
                  f"  {path}: {counts[path][0]} added, {counts[path][1]} removed"
                  for path in generated]
    return ("\n\n## Generated files\n\nEach listed change is committed at the real branch head with the listed line counts. "
            "The review tree only restores each file to the branch start to keep its contents out of "
            "the diff. A missing or untracked copy in the review tree is not a finding. "
            "Review these files by path and size only; do not read their content:\n"
            + "\n".join(f"- {line}" for line in summaries))


def spent(folder: Path) -> dict[str, Any]:
    """Sum the engine processes' separate streams and keep the first chat."""
    runs: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.jsonl")):
        with contextlib.suppress(OSError):
            calls: list[dict[str, Any]] = []
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                usage = event.get("usage")
                if event.get("type") == "thread.started":
                    calls.append({"chat": event.get("thread_id")})
                elif event.get("type") == "turn.completed" and isinstance(usage, dict) and calls:
                    # Codex's last turn holds this process's running token total.
                    calls[-1].update({key: usage.get(key) for key in TOKENS})
                elif event.get("type") == "result" and isinstance(usage, dict):
                    calls.append({"chat": event.get("session_id"), **repo.claude_tokens(usage)})
            runs.extend(calls)
            path.unlink()
    if not runs:
        return {}
    return {"chat": runs[0]["chat"], **{key: sum(counts) if (counts := [
        run[key] for run in runs if isinstance(run.get(key), int)]) else None for key in TOKENS}}


def attempt(argv: list[str], cwd: Path, out: Path,
            selected: dict[str, str], top: Path, item: str, run_id: str,
            strict: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Run Autoreview once: its findings, or the reason the run doesn't count."""
    from forge import codex  # importing it here avoids sync's hook-import cycle
    out.unlink(missing_ok=True)
    proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env={**os.environ, "FORGE_WORKER": "1"},
                            **codex.GROUP)
    # The run's output file: what a person sees when they open the run from the pane.
    log = repo.forge_dir(top) / f"review-{run_id}.log"
    with proc, log.open("wb") as saved, machine.agent_process(proc, log):
        last = ""
        pending = b""
        for line in proc.stdout or []:  # streamed as bytes: its progress is how a person watches it
            line = line.replace(b"\0", b"")
            # Claude's failure trailer contains its result JSON. Hold it until we
            # can name a sign-in failure without printing the raw result first.
            if "claude" in argv and (pending or line.lstrip().startswith(b"{")
                                      or b"claude engine failed" in line):
                pending += line
                last = line.decode("utf-8", "replace").strip() or last
                continue
            sys.stderr.buffer.write(line)
            sys.stderr.flush()
            saved.write(line)
            saved.flush()
            last = line.decode("utf-8", "replace").strip() or last
            if match := re.fullmatch(r"(model|thinking): (.*)", last):
                selected[{"model": "model", "thinking": "effort"}[match[1]]] = match[2]
            elif match := re.fullmatch(
                    r"codex model \S+ is unavailable for this account; retrying with (\S+)", last):
                selected["model"] = match[1]
            if line.strip():
                repo.record_progress(top, item, run_id, step=" ".join(last.split()), **selected)
        code = proc.wait()
    trailer = pending.decode("utf-8", "replace")
    for match in re.finditer(r"(?m)^\s*\{", trailer):
        try:
            result, _ = json.JSONDecoder().raw_decode(trailer[match.end() - 1:])
        except ValueError:
            continue
        if (result.get("is_error") is True and isinstance(result.get("result"), str)
                and result["result"].startswith("Not logged in")):
            raise repo.Refused("Claude is not signed in. Next: run claude and sign in, "
                               f"then forge close {item}.", "")
    if pending:
        sys.stderr.buffer.write(pending)
        sys.stderr.flush()
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
    title = str(raw.get("title", ""))
    body = str(raw.get("body", ""))
    category = str(raw.get("category", "")).strip().casefold().replace("_", " ").replace("-", " ")
    if category in ("security", "data loss") and not any(
            name == category and pattern.search(body) for pattern, name in score.FLOORS[:2]):
        body += f"\nRaise: {category.capitalize()}"
    scores, body = score.normalise(title, body)
    return {"priority": raw["priority"], "title": title, "body": body,
            **(dict(zip(("gain", "work", "harm"), scores)) if scores else {}),
            "file": str(where.get("file_path", "")), "line": where.get("line", 0)}
