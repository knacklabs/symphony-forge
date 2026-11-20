"""CI reuses a completed ancestor workflow result across close-record commits."""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
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


def small_change(base: str, excludes: list[str], tests_only: bool) -> bool:
    """Count code files, keeping shared build and selection inputs on all groups."""
    diff = ("git", "diff", "--name-only", "-z", "--no-renames", f"{base}...HEAD")
    changed = run(*diff).split("\0")
    for name in filter(None, changed):
        path = Path(name)
        if (name.startswith((".github/workflows/", ".forge/"))
                or path.name in {"forge.toml", "conftest.py", "package.json", "pyproject.toml",
                                 "Pipfile", "pnpm-workspace.yaml", "nx.json", "turbo.json"}
                or re.search(r"(^|[.-])(lock|config)([.-]|$)", path.name)
                or re.fullmatch(r"requirements.*\.txt|tsconfig.*\.json", path.name)):
            return False
    code = 0
    for name in filter(None, run(*diff, "--", ".", *excludes).split("\0")):
        path = Path(name)
        if (any(part in {"tests", "test", "__tests__", "spec"} for part in path.parts)
                or path.name.startswith("test_") or path.name.endswith("_test.py")
                or re.search(r"\.(test|spec)\.", path.name)):
            continue
        code += 1
    return tests_only or 0 < code <= 5


def reuse() -> str:
    if int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")) > 1:
        return ""
    pending = [os.environ["HEAD_SHA"]]
    visited = set()
    base = os.environ.get("BASE_SHA")
    workflow = os.environ["GITHUB_WORKFLOW_REF"].split("@", 1)[0].rsplit("/", 1)[1]
    endpoint = f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{quote(workflow)}/runs"
    finished = []
    while pending:
        head = pending.pop()
        if head in visited:
            continue
        visited.add(head)
        parents = run("git", "rev-list", "--parents", "-n", "1", head).split()
        for parent in parents[1:]:
            paths = run("git", "diff", "--name-only", "--no-renames", parent, head).splitlines()
            if any(not path.startswith((".factory/", "plans/"))
                   and not re.fullmatch(r"docs/decisions/\d{4,}-[a-z0-9-]*client-signoff\.md",
                                        path)
                   for path in paths):
                continue
            # A PR parent must have tested the same base, including on both sides of
            # a record-only merge.
            if base:
                try:
                    run("git", "merge-base", "--is-ancestor", base, parent)
                except subprocess.CalledProcessError:
                    continue
            pending.append(parent)
            # Empty diffs and record-only merges keep the product code unchanged.
            # Search every such ancestor because a newer one may still be queued.
            if not shutil.which("gh"):
                runs = api_runs(endpoint, parent)
            else:
                runs = [json.loads(line) for line in run("gh", "api", "--paginate", "--jq",
                                                         ".workflow_runs[]", endpoint,
                                                         "--method", "GET", "-f",
                                                         f"head_sha={parent}", "-f",
                                                         "per_page=100").splitlines()]
            # Target-event runs check the PR but skip tests, so their success proves nothing.
            matching = [r for r in runs if r.get("head_sha") == parent
                        and (r.get("event") == "push" or r.get("event") == "pull_request"
                             and base and any(pr.get("base", {}).get("sha") == base
                                              and pr.get("head", {}).get("sha") == parent
                                              for pr in r.get("pull_requests", [])))]
            finished.extend(r for r in matching
                            if r.get("status") == "completed" and r.get("conclusion"))
    latest = max(finished, key=lambda r: r["id"], default={})
    if not latest:
        return ""
    conclusion = latest["conclusion"]
    return conclusion if conclusion in {"success", "failure"} else ""


if sys.argv[1:2] == ["status"]:
    set_status(*sys.argv[2:5])
    sys.exit()

docs_only = False
docs_tests = False
tests_only, platform_files = False, []
one_group = False
records_only = "--records-only" in sys.argv[1:]
parent_conclusion = ""
failed_parent = False
try:
    # Sync copies close's classifier and supplies its Git path exclusions.
    if not records_only and os.environ.get("BASE_SHA") and os.environ.get("DOCS_ONLY_EXCLUDES"):
        # Local test selection includes incoming merges. CI covers main separately.
        # Ask about the pull request's own branch, not Actions' merge result.
        merged = run("git", "rev-list", "--merges",
                     f"{os.environ['BASE_SHA']}..{os.environ['HEAD_SHA']}")
        tests_only, platform_files = test_files(Path.cwd(), os.environ["BASE_SHA"],
                                                json.loads(os.environ["DOCS_ONLY_EXCLUDES"]))
        one_group = small_change(os.environ["BASE_SHA"],
                                 json.loads(os.environ["DOCS_ONLY_EXCLUDES"]), tests_only)
        docs_only = only_docs(Path.cwd(), os.environ["BASE_SHA"],
                              json.loads(os.environ["DOCS_ONLY_EXCLUDES"]), allow_required=True)
        if docs_only and required_tests(Path.cwd()):
            docs_tests = True
            docs_only, tests_only = False, True
            one_group = True
        if merged:
            cfg = tomllib.loads(Path("forge.toml").read_text("utf-8"))
            place = cfg.get("test_place", "ci" if any(
                check != "forge-pr-check" for check in cfg.get("checks", [])) else "local")
            if place == "local":
                tests_only, platform_files = False, []
                one_group = False
    parent_conclusion = "" if docs_only else reuse()
    if records_only:
        allowed_event = os.environ.get("GITHUB_EVENT_NAME") in {"push", "pull_request"}
        passed = allowed_event and parent_conclusion == "success"
        failed_parent = allowed_event and parent_conclusion == "failure"
    else:
        failed_parent = parent_conclusion == "failure"
        passed = docs_only or parent_conclusion in {"success", "failure"}
except (subprocess.CalledProcessError, ValueError, KeyError, TypeError, OSError, SyntaxError):
    # Missing history, unreadable records or unavailable GitHub proof runs the full suite.
    parent_conclusion = ""
    passed = False
    failed_parent = False
with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
    output.write(f"{'records_only' if records_only else 'reuse'}={str(passed).lower()}\n")
    output.write(f"parent-conclusion={parent_conclusion}\n")
    if docs_only:
        output.write("docs-only=true\n")
    output.write(f"docs-tests={str(docs_tests).lower()}\n")
    output.write(f"test-only={str(tests_only).lower()}\n")
    output.write(f"one-group={str(one_group).lower()}\n")
    output.write(f"platform-files={json.dumps(platform_files)}\n")
    output.write(f"run-windows={str(not tests_only or bool(platform_files)).lower()}\n")
print("Earlier tests did not pass; only close records changed." if failed_parent else
      "docs only: tests skipped" if docs_only else
      "Earlier tests passed; only close records changed." if passed else "Run the test suite.")
if records_only and failed_parent:
    sys.exit(1)
