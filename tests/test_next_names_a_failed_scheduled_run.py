"""forge next names each failed latest scheduled run of the default branch and offers its fix.

Rule: for each workflow whose latest scheduled run on the default branch failed, next names its
failed jobs (which carry the platform) and every failing test as pytest printed it, and prints the
fix start command, or that started fix's own lines, here or on another machine. GitHub is asked
per workflow at most once a minute, and an unreadable GitHub prints nothing. Only gh is faked.
"""
STORY = "nightly-red-shows-in-next"

import json
import shlex
import shutil
import subprocess

import pytest

from conftest import ROOT
from test_fix_plans_roadmap_json_conflicts_on_almost_e import _git
from test_setup import _fresh_client, _version

WORKFLOWS = ("workflow", "list")
NIGHTLY = ("run", "list", "--workflow", "1", "--branch", "main", "--event", "schedule")
SMOKE = ("run", "list", "--workflow", "2", "--branch", "main", "--event", "schedule")
LOG = "\n".join([
    "full suite on windows-latest, group 2 of 3\tRun tests\t2030-01-01T03:40:00Z "
    "FAILED tests/test_a.py::test_one - AssertionError",
    "full suite on macos-latest, group 1 of 3\tRun tests\t2030-01-01T03:41:00Z "
    "FAILED tests/test_b.py::test_two[previous release] - assert 1 == 2",
    "full suite on macos-latest, group 1 of 3\tRun tests\t2030-01-01T03:41:01Z "
    "ERROR tests/test_d.py::test_setup - fixture failed",
    "full suite on macos-latest, group 1 of 3\tRun tests\t2030-01-01T03:41:01Z 1 failed, 1 error",
])
WHY = "The scheduled forge-next run fails on main"
DONE = ("full suite on macos-latest, group 1 of 3; full suite on windows-latest, group 2 of 3 of the "
        "scheduled forge-next workflow pass again on the next scheduled run on main")
COMMAND = f'Next: forge fix start "{WHY}" --done "{DONE}"'


@pytest.mark.parametrize("adoption", ["new", "previous release"])
def test_1_next_names_a_failed_scheduled_run_and_offers_its_fix(repo, gh, tmp_path, monkeypatch,
                                                              adoption):
    if adoption == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("switch", "-q", "-c", "fix/upgrade-client")
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        client, made = repo.path, repo.forge("sync")
        assert made.returncode == 0, made.stdout + made.stderr
        # The upgrade lands on main, as its merged pull request would.
        repo.git("add", "-A")
        assert _git(repo, "commit", "-q", "-m", "Upgrade Forge").returncode == 0
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade-client")
        assert _git(repo, "push", "-q", "origin", "main").returncode == 0
    assert made.returncode == 0, made.stdout + made.stderr
    monkeypatch.setenv("FORGE_NOW", "2030-01-01T10:00:00+00:00")

    gh.respond(*WORKFLOWS, exit=1, stderr="network unavailable")
    offline = repo.forge("next", cwd=client)
    assert offline.returncode == 0, offline.stderr
    assert "The latest scheduled" not in offline.stdout

    # Each workflow's own latest scheduled run counts: a frequent one's success hides no failure.
    gh.respond(*WORKFLOWS, stdout=json.dumps([{"id": 1, "name": "forge-next", "newField": 1},
                                              {"id": 2, "name": "codex-smoke"}]))
    gh.respond(*SMOKE, stdout=json.dumps([{"databaseId": 11, "conclusion": "success"}]))
    gh.respond(*NIGHTLY, stdout=json.dumps([{"databaseId": 7, "conclusion": "failure"}]))
    gh.respond("run", "view", "7", "--log-failed", stdout=LOG)
    red = repo.forge("next", cwd=client)
    assert red.returncode == 0, red.stderr
    lines = red.stdout.splitlines()
    start = lines.index("The latest scheduled forge-next run on main failed in: "
                        "full suite on macos-latest, group 1 of 3; "
                        "full suite on windows-latest, group 2 of 3.")
    assert lines[start + 1:start + 3] == [
        "Failing tests: tests/test_a.py::test_one, tests/test_b.py::test_two[previous release], "
        "tests/test_d.py::test_setup.",
        COMMAND]
    assert "codex-smoke" not in red.stdout
    asked = len(gh.calls())
    repo.forge("next", cwd=client)  # cached for a minute: no new request
    assert [call for call in gh.calls()[asked:] if call[:1] in (["workflow"], ["run"])] == []

    started = repo.forge(*shlex.split(COMMAND.removeprefix("Next: forge ")), cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    fix = repo.git("branch", "--list", "fix/the-scheduled-*", "--format=%(refname:short)",
                   cwd=client).removeprefix("fix/")

    # A later run still fails, now with twelve tests: next names them all, then the fix's own lines.
    monkeypatch.setenv("FORGE_NOW", "2030-01-02T10:00:00+00:00")
    many = [f"tests/test_c.py::test_{n}" for n in range(12)]
    gh.respond(*NIGHTLY, stdout=json.dumps([{"databaseId": 9, "conclusion": "failure"}]))
    gh.respond("run", "view", "9", "--log-failed", stdout="\n".join(
        f"full suite on windows-latest, group 1 of 3\tRun tests\tx FAILED {test} - boom" for test in many))
    expected = ["The latest scheduled forge-next run on main failed in: "
                "full suite on windows-latest, group 1 of 3.",
                f"Failing tests: {', '.join(sorted(many))}."]
    still = repo.forge("next", cwd=client)
    assert still.returncode == 0, still.stderr
    lines = still.stdout.splitlines()
    assert lines[:2] == expected
    assert lines[2].startswith(f"The fix {fix} ")
    assert lines.count(lines[2]) == 1
    assert "forge fix start" not in still.stdout
    machine = repo.forge("next", "--json", cwd=client)
    assert json.loads(machine.stdout)["next"]["command"] == f"forge work {fix}"

    # The fix started on another machine: only its pushed branch is here.
    tree = next(line.removeprefix("worktree ") for line in repo.git(
        "worktree", "list", "--porcelain", cwd=client).splitlines()
        if line.startswith("worktree ") and fix in line)
    pushed = subprocess.run(["git", "-c", "core.hooksPath=no-hooks", "push", "-q", "origin", f"fix/{fix}"],
                            cwd=client, capture_output=True, text=True)
    assert pushed.returncode == 0, pushed.stderr
    repo.git("worktree", "remove", "--force", tree, cwd=client)
    elsewhere = repo.forge("next", cwd=client)
    assert elsewhere.returncode == 0, elsewhere.stderr
    lines = elsewhere.stdout.splitlines()
    assert lines[:2] == expected
    assert lines[2].startswith(f"The fix {fix} was started by ")
    assert lines[2].endswith(" and runs on their machine.")
    assert "forge fix start" not in elsewhere.stdout

    monkeypatch.setenv("FORGE_NOW", "2030-01-03T10:00:00+00:00")
    gh.respond(*NIGHTLY, stdout=json.dumps([{"databaseId": 8, "conclusion": "success"}]))
    assert "The latest scheduled" not in repo.forge("next", cwd=client).stdout

    # Two workflows share a display name: each gets its own alert, told apart by its file.
    monkeypatch.setenv("FORGE_NOW", "2030-01-04T10:00:00+00:00")
    gh.respond(*WORKFLOWS, stdout=json.dumps([
        {"id": 3, "name": "nightly", "path": ".github/workflows/nightly-a.yml"},
        {"id": 4, "name": "nightly", "path": ".github/workflows/nightly-b.yml"}]))
    for run, workflow in ((21, "3"), (22, "4")):
        gh.respond("run", "list", "--workflow", workflow, stdout=json.dumps(
            [{"databaseId": run, "conclusion": "failure"}]))
        gh.respond("run", "view", str(run), "--log-failed", stdout=f"{workflow} job\tRun\tx")
    twins = repo.forge("next", cwd=client).stdout.splitlines()
    assert "The latest scheduled nightly (nightly-a.yml) run on main failed in: 3 job." in twins
    assert "The latest scheduled nightly (nightly-b.yml) run on main failed in: 4 job." in twins
    assert len([line for line in twins if line.startswith("Next: forge fix start")]) == 2
