"""Reuse proof for identical trees in Forge's own merge and release workflows."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def run(*args):
    return subprocess.run([shutil.which(args[0]) or args[0], *args[1:]], check=True,
                          capture_output=True, text=True, timeout=60).stdout.strip()


def github(endpoint, selector, **fields):
    return [json.loads(line) for line in run(
        "gh", "api", "--paginate", "--jq", selector,
        f"repos/{os.environ['GITHUB_REPOSITORY']}/{endpoint}", "--method", "GET",
        "-f", "per_page=100", *[arg for key, value in fields.items()
                                for arg in ("-f", f"{key}={value}")]).splitlines()]


def commit(sha):
    # API values are Git object names, never options or revision expressions.
    if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise ValueError("Invalid commit")
    try:
        run("git", "cat-file", "-e", f"{sha}^{{commit}}")
    except subprocess.CalledProcessError:
        run("git", "fetch", "--no-tags", "origin", sha)
    return sha


def successful(proof):
    return proof.get("status") == "completed" and proof.get("conclusion") == "success"


def reused_run():
    if os.environ.get("GITHUB_EVENT_NAME") != "push":
        return None
    ref, sha = os.environ["GITHUB_REF"], os.environ["GITHUB_SHA"]
    tree = run("git", "rev-parse", f"{sha}^{{tree}}")
    if ref == "refs/heads/main":
        for pr in github(f"commits/{sha}/pulls", ".[]"):
            if (not pr.get("merged_at") or pr.get("merge_commit_sha") != sha
                    or pr.get("base", {}).get("ref") != "main"):
                continue
            head = commit(pr["head"]["sha"])
            if run("git", "merge-tree", "--write-tree", f"{sha}^1", head) != tree:
                continue
            runs = github(f"actions/workflows/{os.environ['PR_WORKFLOW']}/runs",
                          ".workflow_runs[]", head_sha=head, event="pull_request")
            latest = max((r for r in runs if r.get("head_sha") == head
                          and r.get("event") == "pull_request"),
                         key=lambda r: r["id"], default={})
            if successful(latest):
                return latest
    elif ref.startswith("refs/tags/"):
        for proof in github("actions/workflows/forge-next.yml/runs", ".workflow_runs[]",
                            branch="main", event="push", status="success"):
            if (successful(proof) and proof.get("event") == "push"
                    and proof.get("head_branch") == "main"
                    and run("git", "rev-parse", f"{commit(proof['head_sha'])}^{{tree}}") == tree):
                return proof
    return None


try:
    proof = reused_run()
    link = proof["html_url"] if proof is not None else None
except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
    # Missing history, conflicting merges or unavailable GitHub proof must run the tests.
    proof = None
with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
    output.write(f"reuse={str(proof is not None).lower()}\n")
if proof is not None:
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
        summary.write(f"Tests skipped: reused successful proof from {link}.\n")
