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


"""The docs-only rule, also copied into the self-contained client CI script."""
import posixpath
import re
import shutil
import subprocess
from pathlib import Path


def test_readers(files: list[Path], picked: set[Path]) -> set[Path]:
    """Keep every text reference, including plugin strings and scoped conftest users."""
    texts = {path: path.read_text("utf-8-sig") for path in files}
    while True:
        names = {path.stem for path in picked}
        fixtures = [path.parent for path in picked if path.name == "conftest.py"]
        expanded = picked | {path for path, text in texts.items()
                             if any(name in text for name in names)
                             or any(path.is_relative_to(folder) for folder in fixtures)}
        if expanded == picked:
            return picked
        picked = expanded


def only_docs(top: Path, base: str, excludes: list[str], *, allow_settings: bool = False,
              head: str = "HEAD") -> bool:
    """Generated files and inputs read by code always need the full checks."""
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
        strings = r'''(["'`])((?:\\.|(?!\1)[^\\\r\n])*)\1'''
        quoted = r'''(?:'[^'\r\n]*'|"[^"\r\n]*"|`[^`\r\n]*`)'''
        joined = re.compile(rf"\b(?:Path|join)\(\s*(?:__dirname\s*,\s*)?{quoted}"
                            rf"(?:\s*,\s*{quoted})*\s*\)(?:\s*/\s*{quoted})*")
        for consumer in filter(None, found.stdout.split("\0")):
            folder = posixpath.dirname(consumer.partition(":")[2])
            roots = ("", top.as_posix(), posixpath.join(top.as_posix(), folder))
            # A basename finds candidates, not consumers: resolve whole path literals.
            # Fold literal path joins so their components cannot match unrelated root files.
            source = joined.sub(lambda call: repr(posixpath.join(*(
                value[2] for value in re.finditer(strings, call[0])))), git("show", consumer))
            for literal in re.finditer(strings, source):
                name = literal[2].replace("\\", "/")
                if any(posixpath.normpath(posixpath.join(root, name)) in targets for root in roots):
                    return False
    return True



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
