"""CI may reuse a successful ancestor workflow across close-record commits."""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


# <docs-only-rule>


def run(*args: str) -> str:
    # Resolve PATH first, including the .cmd shims used on Windows.
    return subprocess.run([shutil.which(args[0]) or args[0], *args[1:]], check=True,
                          capture_output=True, text=True).stdout.strip()


def api(path: str, body: dict | None = None) -> dict:
    """One GitHub API call without gh: a GET, or a POST with a body. The token is read here,
    so it is never in a command line."""
    request = Request(f"{os.environ.get('GITHUB_API_URL', 'https://api.github.com')}/{path}",
                      data=json.dumps(body).encode() if body else None,
                      headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                               "Accept": "application/vnd.github+json",
                               "Content-Type": "application/json"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def api_runs(endpoint: str, sha: str) -> list[dict]:
    """The same workflow-run list as `gh api --paginate`, for a runner without gh."""
    runs, page = [], 1
    while True:
        found = api(f"{endpoint}?head_sha={sha}&per_page=100&page={page}")["workflow_runs"]
        runs += found
        if len(found) < 100:
            return runs
        page += 1


def set_status(context: str, state: str, job_name: str) -> None:
    """The workflow's status step on a runner without gh: link the commit status to the job."""
    repo, run_id = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_RUN_ID"]
    jobs = api(f"repos/{repo}/actions/runs/{run_id}/jobs")["jobs"]
    api(f"repos/{repo}/statuses/{os.environ['HEAD_SHA']}",
        {"context": context, "state": state,
         "target_url": next(job["html_url"] for job in jobs if job["name"] == job_name)})


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
                                          or name.endswith("_test.py")
                                          or Path(name).name == "conftest.py")
             and (top / name).is_file()]
    changed_tests = {top / name for name in changed}
    if any(test_readers(tests, {path}) != {path} for path in changed_tests):
        return False, []
    platform = []
    for name in changed:
        tree = ast.parse((top / name).read_text("utf-8-sig"))
        if any(isinstance(node, ast.Attribute) and ast.unparse(node) == "pytest.mark.platform"
               for node in ast.walk(tree)):
            platform.append(name)
    return True, platform


def reuse() -> bool:
    head = os.environ["HEAD_SHA"]
    base = os.environ.get("BASE_SHA")
    workflow = os.environ["GITHUB_WORKFLOW_REF"].split("@", 1)[0].rsplit("/", 1)[1]
    endpoint = f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{quote(workflow)}/runs"
    while True:
        parents = run("git", "rev-list", "--parents", "-n", "1", head).split()
        if len(parents) != 2:
            return False
        head, parent = parents
        # A push tests the branch itself. A PR also needs its current base covered.
        if base:
            run("git", "merge-base", "--is-ancestor", base, parent)
        paths = run("git", "diff", "--name-only", "--no-renames", parent, head).splitlines()
        if not paths:
            return False
        for path in paths:
            if re.fullmatch(r"plans/spotted/[^/]+\.json", path):
                continue
            if not re.fullmatch(r"\.factory/(fixes/[^/]+|stories/[^/]+/tasks/[^/]+)\.json", path):
                return False
            before, after = (json.loads(run("git", "show", f"{rev}:{path}"))
                             for rev in (parent, head))
            if not isinstance(before, dict) or not isinstance(after, dict):
                return False
            if before.get("review") != after.get("review") and not isinstance(after.get("review"), dict):
                return False
            # Acceptance also updates known findings and can save several commits before
            # one push. Contracts and all other state must stay identical at every step.
            bookkeeping = {"review", "tests", "status", "steps", "flagged", "stop", "known"}
            if ({k: v for k, v in before.items() if k not in bookkeeping}
                    != {k: v for k, v in after.items() if k not in bookkeeping}):
                return False
        runs = ([json.loads(line) for line in run("gh", "api", "--paginate", "--jq",
                                                ".workflow_runs[]", endpoint, "--method", "GET",
                                                "-f", f"head_sha={parent}", "-f", "per_page=100").splitlines()]
                if shutil.which("gh") else api_runs(endpoint, parent))
        # Target-event runs check the PR but skip tests, so their success proves nothing here.
        matching = [r for r in runs if r.get("head_sha") == parent
                    and (r.get("event") == "push" or r.get("event") == "pull_request"
                         and base and any(pr.get("base", {}).get("sha") == base
                                          and pr.get("head", {}).get("sha") == parent
                                          for pr in r.get("pull_requests", [])))]
        latest = max(matching, key=lambda r: r["id"], default={})
        if latest:
            return latest.get("status") == "completed" and latest.get("conclusion") == "success"
        head = parent


if sys.argv[1:2] == ["status"]:
    set_status(*sys.argv[2:5])
    sys.exit()

docs_only = False
tests_only, platform_files = False, []
records_only = "--records-only" in sys.argv[1:]
try:
    # Sync copies close's classifier and supplies its Git path exclusions.
    if not records_only and os.environ.get("BASE_SHA") and os.environ.get("DOCS_ONLY_EXCLUDES"):
        # `forge test --change` widens to what a merged-in default branch brought, which one
        # group cannot finish. Ask about the pull request's own branch, not Actions' merge result.
        merged = run("git", "rev-list", "--merges",
                     f"{os.environ['BASE_SHA']}..{os.environ['HEAD_SHA']}")
        tests_only, platform_files = test_files(Path.cwd(), os.environ["BASE_SHA"],
                                                json.loads(os.environ["DOCS_ONLY_EXCLUDES"]))
        docs_only = only_docs(Path.cwd(), os.environ["BASE_SHA"],
                              json.loads(os.environ["DOCS_ONLY_EXCLUDES"]), allow_required=True)
        if docs_only and required_tests(Path.cwd()):
            docs_only, tests_only = False, True
        if merged:
            tests_only, platform_files = False, []
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
      "Earlier tests passed; only close records changed." if passed else "Run the test suite.")
