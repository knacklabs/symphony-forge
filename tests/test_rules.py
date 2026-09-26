"""The rules that keep Forge itself honest: one test per rule, small, pinned and fast.

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "specs" / "lean-forge-v1.md"
WORKFLOW = ROOT / ".github" / "workflows" / "forge-next.yml"

# Every criterion in the spec must have its test (on since ADOPT).
EVERY_CRITERION_TESTED = True
# The spec's own story: a test file without a STORY constant cites the spec's criteria too.
SPEC_STORY = "FORGE-NEXT-1"


def test_4_one_test_per_rule():
    cited: dict[tuple[str, int], str] = {}
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # A story's own test file sets STORY = "<key>"; its numbers cite that story's Done when.
        story = next((node.value.value for node in tree.body if isinstance(node, ast.Assign)
                      and isinstance(node.value, ast.Constant)
                      and [getattr(target, "id", "") for target in node.targets] == ["STORY"]),
                     SPEC_STORY)
        for node in ast.walk(tree):
            # ponytail: tests may not import forge, so they can only see command output,
            # git, files and stub calls. A direct JSON read of a state file is left to review.
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            assert not any(name == "forge" or name.startswith("forge.") for name in names), (
                f"{path.name}:{node.lineno} imports forge; run the forge command instead")
        for node in tree.body:
            assert not (isinstance(node, ast.ClassDef) and node.name.startswith("Test")), (
                f"{path.name}: {node.name} hides tests in a class; use test functions")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                match = re.fullmatch(r"test_(\d+)_\w+", node.name)
                assert match, f"{path.name}: {node.name} cites no criterion; name it test_<n>_<rule>"
                number = (story, int(match[1]))
                assert number not in cited, (
                    f"criterion {number[1]} {story} has two tests: {cited[number]} and "
                    f"{path.name}::{node.name}")
                cited[number] = f"{path.name}::{node.name}"
    if EVERY_CRITERION_TESTED:
        criteria = SPEC.read_text(encoding="utf-8").split("## Acceptance criteria")[1]
        numbers = {int(n) for n in re.findall(r"^(\d+)\. \*\*", criteria, re.M)}
        spec = {n for story, n in cited if story == SPEC_STORY}
        assert not numbers - spec, f"criteria with no test: {sorted(numbers - spec)}"
        assert not spec - numbers, f"tests citing no criterion: {sorted(spec - numbers)}"


def test_5_forge_stays_small(repo):
    ceiling = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["forge"][
        "line_ceiling"]
    files = [p for p in (ROOT / "src" / "forge").rglob("*")
             if p.is_file() and "__pycache__" not in p.parts]
    lines = {p.relative_to(ROOT).as_posix(): p.read_bytes().count(b"\n") for p in files}
    too_long = {path: n for path, n in lines.items() if path.endswith(".py") and n > 1200}
    assert not too_long, f"modules over 1,200 lines: {too_long}"
    assert sum(lines.values()) <= ceiling, (
        f"src/forge/ has {sum(lines.values())} lines, over the {ceiling} ceiling in pyproject.toml")

    help_text = repo.forge("--help").stdout
    commands = re.search(r"\{([^}]+)\}", help_text)[1].split(",")
    assert len(commands) <= 20, f"{len(commands)} commands: {commands}"

    assert "git diff --numstat" in WORKFLOW.read_text(encoding="utf-8"), "CI prints no net lines"


def test_10_version_pin(repo, tmp_path):
    version = repo.forge("--version").stdout.split()[-1]
    assert re.fullmatch(r"v\d+\.\d+\.\d+\S*", version), version

    repo.write("forge.toml", 'version = "v0.0.1"\n')
    refused = repo.forge("sync")
    assert refused.returncode != 0
    assert refused.stderr == (
        f"Forge {version} is installed, but this repo pins v0.0.1.\n"
        "Next: uv tool install git+https://github.com/knacklabs/symphony-forge@v0.0.1\n")
    for read_only in (["--version"], ["doctor"], ["next"]):
        assert "uv tool install" not in repo.forge(*read_only).stderr

    repo.write("forge.toml", f'version = "{version}"\n')
    assert "uv tool install" not in repo.forge("sync").stderr

    # Installing from a tag prints that tag's version.
    uv = shutil.which("uv")
    assert uv, "the version pin rule needs uv, which Forge installs with"
    source = tmp_path / "release"
    shutil.copytree(ROOT / "src" / "forge", source / "src" / "forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "pyproject.toml", source)
    repo.git("init", "-q", str(source))
    repo.git("add", "-A", cwd=source)
    repo.git("commit", "-q", "-m", "Release", cwd=source)
    repo.git("tag", version, cwd=source)
    env = {**os.environ, "UV_TOOL_DIR": str(tmp_path / "tools"),
           "UV_TOOL_BIN_DIR": str(tmp_path / "tool-bin")}
    subprocess.run([uv, "tool", "install", "-q", f"git+{source.as_uri()}@{version}"], env=env,
                   check=True, capture_output=True, timeout=120)
    # Not shutil.which: on Windows it searches the current folder first and finds the old forge.cmd.
    installed = next(p for p in (tmp_path / "tool-bin").iterdir() if p.stem.lower() == "forge")
    shown = subprocess.run([installed, "--version"], capture_output=True, text=True, check=True)
    assert shown.stdout.split()[-1] == version


def test_31_speed():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for runner in ("ubuntu-latest", "macos-latest", "windows-latest"):
        assert runner in workflow, f"the suite doesn't run on {runner}"
    assert "pytest tests" in workflow
    timeouts = [int(n) for n in re.findall(r"timeout-minutes: (\d+)", workflow)]
    assert timeouts and max(timeouts) <= 5, f"job timeouts over five minutes: {timeouts}"
    windows = re.findall(r"os: windows-latest, group: (\d), groups: (\d)", workflow)
    assert sorted(windows) == [("1", "3"), ("2", "3"), ("3", "3")], f"Windows isn't in groups 1-3 of 3: {windows}"
