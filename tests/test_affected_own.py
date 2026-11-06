"""Forge's own pull requests select smoke areas and run related tests once."""
import json
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

from conftest import machine_runners
from test_close import env, run  # noqa: F401 (pytest fixture)

STORY = "FORGE-AFFECTED-1"
ROOT = Path(__file__).resolve().parents[1]
JOBS = {
    "starter_smoke", "organisation_invites_smoke", "member_removal_smoke",
    "python_starter_smoke", "python_database_kinds_smoke", "python_feature_api_smoke",
    "python_feature_history_smoke", "python_feature_permissions_smoke",
}
STARTERS = {"starter_smoke", "python_starter_smoke"}


def test_4_own_repo_selects_smoke_areas_and_runs_related_tests_once(env, monkeypatch):
    # Boundary contracts: wrong area rows waste CI or miss smoke coverage, skipped
    # dependencies lose nightly proof, and local close tests duplicate CI. Existing
    # tests own live app behavior and dispatch paths, not selection. No new seam.
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    repo = env.repo
    areas = env.tmp / "areas"
    areas.mkdir()
    repo.git("init", "-q", cwd=areas)
    repo.git("commit", "-q", "--allow-empty", "-m", "Base", cwd=areas)

    def select(*args):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/smoke_select.py"),
                                 *args], cwd=areas, text=True, encoding="utf-8",
                                capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def selected(output):
        return {job for job in JOBS if output[job] == "true"}

    full = select("--all")
    assert selected(full) == JOBS
    cases = [
        ("src/forge/templates/skills/agents/assistant-module/python/app.py", STARTERS),
        ("src/forge/templates/skill.md", set()),
        ("src/forge/templates/design/support.js", STARTERS),
        ("src/forge/templates/starter/apps/web/src/app.tsx", JOBS),
        ("src/forge/templates/unmapped/new.txt", JOBS),
        ("src/forge/feature_python.py", STARTERS | {
            "python_database_kinds_smoke",
            "python_feature_api_smoke", "python_feature_history_smoke",
            "python_feature_permissions_smoke"}),
        ("src/forge/templates/feature/example.txt", STARTERS | {
            "python_database_kinds_smoke",
            "python_feature_api_smoke", "python_feature_history_smoke",
            "python_feature_permissions_smoke"}),
    ]
    for name, expected in cases:
        base = repo.git("rev-parse", "HEAD", cwd=areas)
        file = areas / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("changed\n", encoding="utf-8")
        repo.git("add", "-A", cwd=areas)
        repo.git("commit", "-q", "-m", "Change one area", cwd=areas)
        output = select(base)
        assert selected(output) == expected, name
        for job in expected:
            args = shlex.split(output[job + "_args"])
            if "assistant-module" in name:
                assert args[0] == "tests/test_assistant_*.py"
                assert [arg for arg in args if arg.startswith("tests/")] == [args[0]]
                assert args[args.index("-k") + 1] == (
                    "python" if job.startswith("python") else "not python")
            else:
                assert output[job + "_args"] == full[job + "_args"]
    # A mixed change broadens the assistant-only selection to the full starter jobs.
    base = repo.git("rev-parse", "HEAD", cwd=areas)
    for name in (cases[0][0], cases[2][0]):
        (areas / name).write_text("changed again\n", encoding="utf-8")
    repo.git("commit", "-qam", "Change two areas", cwd=areas)
    mixed = select(base)
    assert selected(mixed) == STARTERS
    assert all(mixed[job + "_args"] == full[job + "_args"] for job in STARTERS)
    assert selected(select("HEAD")) == set()
    for event in ("schedule", "workflow_dispatch"):
        monkeypatch.setenv("GITHUB_EVENT_NAME", event)
        assert select() == full  # no diff or base needed
    monkeypatch.delenv("GITHUB_EVENT_NAME")

    workflow = (ROOT / ".github/workflows/starter-smoke.yml").read_text("utf-8")
    jobs = dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)",
                           workflow.split("jobs:\n", 1)[1], re.M | re.S))
    assert "if:" not in jobs["select"]
    assert 'python scripts/smoke_select.py' in jobs["select"]
    assert '"$GITHUB_OUTPUT"' in jobs["select"]
    assert "fetch-depth: 0" in jobs["select"]
    assert set(jobs) == {job.replace("_", "-") for job in JOBS} | {"select"}
    for job in JOBS:
        body = jobs[job.replace("_", "-")]
        assert "    needs: select\n" in body
        assert re.findall(r"^    if: (.+)$", body, re.M) == [
            f"needs.select.outputs.{job} == 'true'"]
        assert f"needs.select.outputs.{job}_args" in body
        for key in (job, job + "_args"):
            assert f"{key}: ${{{{ steps.areas.outputs.{key} }}}}" in jobs["select"]
        if job.startswith("python_"):
            assert "timeout-minutes: 45" in body
    paths = re.search(r"  pull_request:\n    paths:\n(.*?)(?=\n\S)", workflow, re.S)[1]
    assert re.findall(r"^      - (.+)$", paths, re.M) == [
        ".github/workflows/starter-smoke.yml", "src/forge/templates/**", "src/forge/feature*.py"]
    concurrency = workflow.split("concurrency:\n", 1)[1].split("\n\n", 1)[0]
    assert "github.workflow" in concurrency and "github.event.pull_request.number || github.run_id" in concurrency
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in concurrency

    # Copy Forge's real settings unchanged: close must wait for CI without pytest.
    machine_runners(repo)
    for rel in ("forge.toml", "pyproject.toml", "uv.lock"):
        repo.write(rel, (ROOT / rel).read_text("utf-8"))
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", sys.prefix)
    monkeypatch.setenv("UV_NO_SYNC", "1")
    log = env.tmp / "pytest-ran"
    repo.write("conftest.py", f'''import pathlib
import pytest
@pytest.fixture(autouse=True)
def record_run(request):
    with pathlib.Path({json.dumps(str(log))}).open("a", encoding="utf-8") as stream:
        stream.write(request.node.name + "\\n")
''')
    repo.write("tests/test_probe.py", "def test_related():\n    assert 1 + 1 == 2\n")
    for number in range(5):
        repo.write(f"tests/test_other_{number}.py", f"def test_other_{number}():\n    assert True\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Use Forge settings")
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"tests/test_probe.py":
                                "def test_related():\n    assert 2 + 2 == 4\n"})
    settings = tomllib.loads((ROOT / "forge.toml").read_text("utf-8"))
    env.checks([run(name, None, "queued") if name == "tests" else run(name)
                for name in settings["checks"]])
    waiting = env.close(item)
    assert waiting.returncode != 0, waiting.stdout + waiting.stderr
    assert "tests is still queued" in waiting.stderr, waiting.stdout + waiting.stderr
    assert not log.exists()
    monkeypatch.setenv("FORGE_GROUP", "1")
    monkeypatch.setenv("FORGE_GROUPS", "1")
    ci = repo.forge("test", "--change", cwd=where, timeout=120)
    assert ci.returncode == 0, ci.stdout + ci.stderr
    assert log.read_text("utf-8").splitlines() == ["test_related"]
    env.checks([run(name) for name in settings["checks"]])
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert log.read_text("utf-8").splitlines() == ["test_related"]
