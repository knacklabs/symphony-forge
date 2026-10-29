"""CI may reuse a successful parent workflow for a commit changing only close records."""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


# <docs-only-rule>


def run(*args: str) -> str:
    # Resolve PATH first, including the .cmd shims used on Windows.
    return subprocess.run([shutil.which(args[0]) or args[0], *args[1:]], check=True,
                          capture_output=True, text=True).stdout.strip()


def test_files(top: Path, base: str, excludes: list[str], *, head: str = "HEAD") -> tuple[bool, list[str]]:
    """Narrow CI only for existing Python test files, never shared test inputs."""
    paths = subprocess.run([shutil.which("git") or "git", "diff", "--name-only", "-z",
                            "--no-renames", f"{base}...{head}", "--", ".", *excludes],
                           cwd=top, check=True, capture_output=True, text=True).stdout
    changed = list(filter(None, paths.split("\0")))
    if not changed or any(not (Path(name).name.startswith("test_") or name.endswith("_test.py"))
                          or not name.endswith(".py") or not (top / name).is_file()
                          for name in changed):
        return False, []
    tests = [top / name for name in run("git", "ls-files", "-z").split("\0")
             if name.endswith(".py") and (Path(name).name.startswith("test_")
                                          or name.endswith("_test.py"))
             and (top / name).is_file()]
    changed_tests = {top / name for name in changed}
    if any(sources & changed_tests for sources in test_dependencies(tests).values()):
        return False, []
    platform = []
    for name in changed:
        tree = ast.parse((top / name).read_text("utf-8-sig"))
        if any(isinstance(node, ast.Attribute) and ast.unparse(node) == "pytest.mark.platform"
               for node in ast.walk(tree)):
            platform.append(name)
    return True, platform


def reuse() -> bool:
    parents = run("git", "rev-list", "--parents", "-n", "1", os.environ["HEAD_SHA"]).split()
    if len(parents) != 2:
        return False
    head, parent = parents
    base = os.environ.get("BASE_SHA")
    # A push tests the branch itself. Reuse it for a PR only if its parent already
    # incorporates the current base; otherwise the merge result needs its own suite.
    if base:
        run("git", "merge-base", "--is-ancestor", base, parent)
    paths = run("git", "diff", "--name-only", "--no-renames", parent, head).splitlines()
    if not paths:
        return False
    for path in paths:
        if not re.fullmatch(r"\.factory/(fixes/[^/]+|stories/[^/]+/tasks/[^/]+)\.json", path):
            return False
        before, after = (json.loads(run("git", "show", f"{rev}:{path}"))
                         for rev in (parent, head))
        if not isinstance(before, dict) or not isinstance(after, dict):
            return False
        review_changed = before.get("review") != after.get("review")
        if (review_changed and not isinstance(after.get("review"), dict)
                or not review_changed and before.get("tests") == after.get("tests")):
            return False
        # Close saves these alongside its review. The change's contract and all other state
        # must remain identical; a .factory path alone is not enough to skip testing.
        bookkeeping = {"review", "tests", "status", "steps", "flagged", "stop"}
        if ({k: v for k, v in before.items() if k not in bookkeeping}
                != {k: v for k, v in after.items() if k not in bookkeeping}):
            return False
    workflow = os.environ["GITHUB_WORKFLOW_REF"].split("@", 1)[0].rsplit("/", 1)[1]
    endpoint = f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{quote(workflow)}/runs"
    runs = [json.loads(line) for line in run("gh", "api", "--paginate", "--jq",
                                           ".workflow_runs[]", endpoint, "--method", "GET",
                                           "-f", f"head_sha={parent}", "-f", "per_page=100").splitlines()]
    # Target-event runs check the PR but skip tests, so their success proves nothing here.
    matching = [r for r in runs if r.get("head_sha") == parent
                and (r.get("event") == "push" or r.get("event") == "pull_request"
                     and base and any(pr.get("base", {}).get("sha") == base
                                      and pr.get("head", {}).get("sha") == parent
                                      for pr in r.get("pull_requests", [])))]
    latest = max(matching, key=lambda r: r["id"], default={})
    return latest.get("status") == "completed" and latest.get("conclusion") == "success"


docs_only = False
tests_only, platform_files = False, []
records_only = "--records-only" in sys.argv[1:]
try:
    # Sync copies close's classifier and supplies its Git path exclusions.
    if not records_only and os.environ.get("BASE_SHA") and os.environ.get("DOCS_ONLY_EXCLUDES"):
        tests_only, platform_files = test_files(Path.cwd(), os.environ["BASE_SHA"],
                                                json.loads(os.environ["DOCS_ONLY_EXCLUDES"]))
        docs_only = only_docs(Path.cwd(), os.environ["BASE_SHA"],
                              json.loads(os.environ["DOCS_ONLY_EXCLUDES"]))
    if records_only:
        passed = os.environ.get("GITHUB_EVENT_NAME") in {"push", "pull_request"} and reuse()
    else:
        passed = docs_only or reuse()
except (subprocess.CalledProcessError, ValueError, KeyError, TypeError, OSError, SyntaxError):
    # Missing history, unreadable records or unavailable GitHub proof runs the full suite.
    passed = False
with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
    output.write(f"{'records_only' if records_only else 'reuse'}={str(passed).lower()}\n")
    if docs_only:
        output.write("docs-only=true\n")
    output.write(f"test-only={str(tests_only).lower()}\n")
    output.write(f"platform-files={json.dumps(platform_files)}\n")
    output.write(f"run-windows={str(not tests_only or bool(platform_files)).lower()}\n")
print("docs only: tests skipped" if docs_only else
      "Parent tests passed; only the close record changed." if passed else "Run the test suite.")
