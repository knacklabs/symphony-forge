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


"""The docs-only rule, also copied into the self-contained client CI script."""
import ast
import posixpath
import re
import shutil
import subprocess
from pathlib import Path

PATH_LITERALS = r'''(["'`])((?:\\.|(?!\1)[^\\\r\n])*)\1'''


def required_tests(top: Path) -> list[str]:
    """The repository-owned pytest list is shared by selection and CI's docs rule."""
    listing = top / ".forge" / "always-tests.txt"
    return [line.strip() for line in listing.read_text("utf-8").splitlines() if line.strip()] if listing.is_file() else []


def reads_file_relative(source: str, paths: set[str]) -> bool:
    """Match literals in file-relative paths, not unrelated content assertions."""
    if not paths or not re.search(r"\b__file__\b", source):
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Embedded Python and newer syntax still get the conservative check.
        basenames = {posixpath.basename(path) for path in paths}
        return any(posixpath.basename(literal[2].replace("\\", "/")) in basenames
                   for literal in re.finditer(PATH_LITERALS, source))
    roots = {"__file__": []}

    def components(node: ast.AST) -> list[str]:
        if isinstance(node, ast.Name):
            return roots.get(node.id, [])
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value.replace("\\", "/")]
        return [part for child in ast.iter_child_nodes(node) for part in components(child)]

    def rooted(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in roots
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            return rooted(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
            return rooted(node.left) or rooted(node.right)
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            return name in {"Path", "join", "dirname", "abspath", "realpath", "normpath",
                            "resolve", "absolute", "joinpath", "with_name", "with_suffix"} and (
                rooted(node.func) or any(rooted(arg) for arg in node.args))
        return False

    assignments = [node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign))]
    while True:
        before = len(roots)
        for node in assignments:
            if rooted(node.value):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in roots:
                        roots[target.id] = components(node.value)
        if len(roots) == before:
            break
    def suffix_of(node: ast.AST) -> str:
        parts = components(node)
        return posixpath.normpath("/" + posixpath.join(*parts)).lstrip("/") if parts else ""

    folders = set()  # Folders the test lists itself: path.iterdir(), glob, os.listdir(path) and the like.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            listed = (node.func.value if name in {"iterdir", "glob", "rglob"}
                      and isinstance(node.func, ast.Attribute)
                      else node.args[0] if name in {"listdir", "scandir", "walk", "iglob", "glob"}
                      and node.args else None)
            if listed is not None and rooted(listed) and (suffix := suffix_of(listed)):
                folders.add(suffix)
    for node in ast.walk(tree):
        if isinstance(node, (ast.BinOp, ast.Call)) and rooted(node):
            suffix = suffix_of(node)
            if suffix and any(path == suffix or path.endswith("/" + suffix) for path in paths):
                return True
    return any(("/" + posixpath.dirname(path)).endswith("/" + folder)
               for folder in folders for path in paths)


def test_readers(files: list[Path], picked: set[Path], root=None) -> set[Path]:
    """Keep every text reference, including plugin strings and scoped conftest users. With a
    `root` function, a name counts only in files under the folder it gives for the file that has
    it; without one, a name counts in every file."""
    texts = {path: path.read_text("utf-8-sig") for path in files}
    while True:
        names = {(path.stem, root(path) if root else None) for path in picked}
        fixtures = [path.parent for path in picked if path.name == "conftest.py"]
        expanded = picked | {path for path, text in texts.items()
                             if any(name in text for name, folder in names
                                    if folder is None or path.is_relative_to(folder))
                             or any(path.is_relative_to(folder) for folder in fixtures)}
        if expanded == picked:
            return picked
        picked = expanded


def only_docs(top: Path, base: str, excludes: list[str], *, allow_settings: bool = False,
              head: str = "HEAD", allow_required: bool = False) -> bool:
    """Generated files and inputs read by code always need the full checks."""
    if not allow_required and required_tests(top):
        return False
    def git(*args: str, input: str | None = None) -> str:
        return subprocess.run([shutil.which("git") or "git", *args], cwd=top, input=input,
                              check=True, capture_output=True, text=True,
                              encoding="utf-8").stdout

    diff = ("diff", "--name-only", "-z", "--no-renames", f"{base}...{head}")
    remaining = git(*diff, "--", ".", *excludes).strip("\0")
    if remaining and not (allow_settings and remaining == "forge.toml"):
        return False
    paths = git(*diff)
    if paths:
        attributes = git("check-attr", "-z", "--stdin", "linguist-generated", input=paths)
        values = attributes.strip("\0").split("\0")[2::3]
        if any(value.lower() not in {"unspecified", "unset", "false"} for value in values):
            return False
        tests = [":(glob)**/test*/**", ":(glob)**/*.test.*", ":(glob)**/*.spec.*",
                 ":(glob)**/test_*.py", ":(glob)**/*_test.py",
                 ":(glob)**/__tests__/**", ":(glob)**/conftest.py"]
        if git(*diff, "--", *tests):
            return False
        # Check both sides: deleting an input still needs its consumer's tests.
        changed = paths.strip("\0").split("\0")
        patterns = sorted({posixpath.basename(path) for path in changed})
        found = subprocess.run([shutil.which("git") or "git", "grep", "-I", "-l", "-z", "-F",
                                *[arg for name in patterns for arg in ("-e", name)],
                                base, head, "--", ".", *excludes,
                                ":(exclude,glob)**/.gitattributes"], cwd=top, capture_output=True,
                                text=True, encoding="utf-8")
        if found.returncode not in (0, 1):
            return False
        targets = {posixpath.normpath(posixpath.join(top.as_posix(), path)) for path in changed}
        quoted = r'''(?:'[^'\r\n]*'|"[^"\r\n]*"|`[^`\r\n]*`)'''
        joined = re.compile(rf"\b(?:Path|join)\(\s*(?:__dirname\s*,\s*)?{quoted}"
                            rf"(?:\s*,\s*{quoted})*\s*\)(?:\s*/\s*{quoted})*")
        for consumer in filter(None, found.stdout.split("\0")):
            folder = posixpath.dirname(consumer.partition(":")[2])
            roots = ("", top.as_posix(), posixpath.join(top.as_posix(), folder))
            source = git("show", consumer)
            # File-relative expressions cannot always be resolved from literals alone.
            # Prefer extra tests when a quoted basename could read the changed input.
            if reads_file_relative(source, set(changed)):
                return False
            # A basename finds candidates, not consumers: resolve whole path literals.
            # Fold literal path joins so their components cannot match unrelated root files.
            source = joined.sub(lambda call: repr(posixpath.join(*(
                value[2] for value in re.finditer(PATH_LITERALS, call[0])))), source)
            for literal in re.finditer(PATH_LITERALS, source):
                name = literal[2].replace("\\", "/")
                if any(posixpath.normpath(posixpath.join(root, name)) in targets for root in roots):
                    return False
    return True



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
