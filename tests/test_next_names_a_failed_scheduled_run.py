"""forge next names a failed latest scheduled run of the default branch and offers its fix.

Rule: when the latest scheduled run on the default branch failed, next names its failed jobs
(which carry the platform) and every failing test, and prints the fix start command, or the
started fix's next step; GitHub is read
once a minute at most, and an unreadable GitHub prints nothing. Only gh is faked.
"""
STORY = "nightly-red-shows-in-next"

import json
import shlex
import shutil

import pytest

from conftest import ROOT
from test_fix_plans_roadmap_json_conflicts_on_almost_e import _git
from test_setup import _fresh_client, _version

LIST = ("run", "list", "--branch", "main", "--event", "schedule")
LOG = "\n".join([
    "full suite on windows-latest, group 2 of 3\tRun tests\t2030-01-01T03:40:00Z "
    "FAILED tests/test_a.py::test_one - AssertionError",
    "full suite on macos-latest, group 1 of 3\tRun tests\t2030-01-01T03:41:00Z "
    "FAILED tests/test_b.py::test_two[new] - assert 1 == 2",
    "full suite on macos-latest, group 1 of 3\tRun tests\t2030-01-01T03:41:01Z 1 failed",
])
WHY = "The scheduled forge-next run fails on main"
DONE = ("The scheduled forge-next run passes on main, with these tests passing: "
        "tests/test_a.py::test_one, tests/test_b.py::test_two[new]")
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

    gh.respond(*LIST, exit=1, stderr="network unavailable")
    offline = repo.forge("next", cwd=client)
    assert offline.returncode == 0, offline.stderr
    assert "The latest scheduled" not in offline.stdout

    gh.respond(*LIST, stdout=json.dumps([{"databaseId": 7, "conclusion": "failure",
                                          "workflowName": "forge-next", "newField": 1}]))
    gh.respond("run", "view", "7", "--log-failed", stdout=LOG)
    red = repo.forge("next", cwd=client)
    assert red.returncode == 0, red.stderr
    lines = red.stdout.splitlines()
    start = lines.index("The latest scheduled forge-next run on main failed in: "
                        "full suite on macos-latest, group 1 of 3; "
                        "full suite on windows-latest, group 2 of 3.")
    assert lines[start + 1:start + 3] == [
        "Failing tests: tests/test_a.py::test_one, tests/test_b.py::test_two[new].", COMMAND]
    assert len([call for call in gh.calls() if call[:2] == ["run", "list"]]) == 2
    repo.forge("next", cwd=client)  # cached for a minute: no new request
    assert len([call for call in gh.calls() if call[:2] == ["run", "list"]]) == 2

    started = repo.forge(*shlex.split(COMMAND.removeprefix("Next: forge ")), cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    assert COMMAND not in repo.forge("next", cwd=client).stdout
    fix = repo.git("branch", "--list", "fix/the-scheduled-*", "--format=%(refname:short)",
                   cwd=client).removeprefix("fix/")

    # A later run still fails, now with twelve tests: next names them all and the started fix's step.
    monkeypatch.setenv("FORGE_NOW", "2030-01-02T10:00:00+00:00")
    many = [f"tests/test_c.py::test_{n}" for n in range(12)]
    gh.respond(*LIST, stdout=json.dumps([{"databaseId": 9, "conclusion": "failure",
                                          "workflowName": "forge-next"}]))
    gh.respond("run", "view", "9", "--log-failed", stdout="\n".join(
        f"full suite on windows-latest, group 1 of 3\tRun tests\tx FAILED {test} - boom" for test in many))
    still = repo.forge("next", cwd=client)
    assert still.returncode == 0, still.stderr
    lines = still.stdout.splitlines()
    start = lines.index("The latest scheduled forge-next run on main failed in: "
                        "full suite on windows-latest, group 1 of 3.")
    assert lines[start + 1:start + 4] == [f"Failing tests: {', '.join(sorted(many))}.",
                                          f"The fix {fix} is started for it.", f"Next: forge work {fix}"]
    assert "forge fix start" not in still.stdout

    monkeypatch.setenv("FORGE_NOW", "2030-01-03T10:00:00+00:00")
    gh.respond(*LIST, stdout=json.dumps([{"databaseId": 8, "conclusion": "success",
                                          "workflowName": "forge-next"}]))
    assert "The latest scheduled" not in repo.forge("next", cwd=client).stdout
