"""forge next offers a dependency and base-image refresh fix once lockfiles are a week old by git log."""
import shlex

from test_story import setup

STORY = "a-new-security-advisory-in-a-transitive"

LISTED = "The dependencies and base images haven't been refreshed in over a week; refresh them."


def _old_lockfile(repo, monkeypatch):
    setup(repo)
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-09-01T10:00:00+00:00")
    repo.write("uv.lock", "version = 1\n")
    repo.write("Dockerfile", "FROM python:3.11-slim\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Lock dependencies")
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    repo.git("push", "-q", "origin", "main")


def test_1_an_old_lockfile_lists_a_refresh_fix_the_agent_can_start(repo, monkeypatch):
    _old_lockfile(repo, monkeypatch)
    monkeypatch.setenv("FORGE_NOW", "2026-09-10T10:00:00+00:00")

    result = repo.forge("next")

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert LISTED in lines
    start = lines[lines.index(LISTED) + 1]
    assert start.startswith("Next: forge fix start ")
    words = shlex.split(start.removeprefix("Next: "))
    assert "<" not in start and words[-2:] == ["--slug", "refresh-dependencies"]

    started = repo.forge(*words[1:])
    assert started.returncode == 0, started.stderr
    assert started.stdout.startswith("Started fix refresh-dependencies")
    again = repo.forge("next")
    assert LISTED not in again.stdout
    assert "The fix refresh-dependencies is started" in again.stdout


def test_2_a_lockfile_changed_this_week_lists_nothing(repo, monkeypatch):
    _old_lockfile(repo, monkeypatch)
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-09-08T10:00:00+00:00")
    repo.write("uv.lock", "version = 1\nrevision = 2\n")
    repo.git("commit", "-q", "-am", "Refresh dependencies")
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    repo.git("push", "-q", "origin", "main")
    monkeypatch.setenv("FORGE_NOW", "2026-09-10T10:00:00+00:00")

    result = repo.forge("next")

    assert result.returncode == 0, result.stderr
    assert LISTED not in result.stdout
    assert "refresh-dependencies" not in result.stdout


def test_3_a_repo_without_a_lockfile_lists_nothing(repo, monkeypatch):
    setup(repo)
    repo.write("Dockerfile", "FROM python:3.11-slim\n")  # an old base image alone lists nothing
    repo.git("add", "Dockerfile")
    repo.git("commit", "-q", "-m", "Add a Dockerfile")
    repo.git("push", "-q", "origin", "main")
    monkeypatch.setenv("FORGE_NOW", "2030-01-01T10:00:00+00:00")

    result = repo.forge("next")

    assert result.returncode == 0, result.stderr
    assert LISTED not in result.stdout
    assert "refresh-dependencies" not in result.stdout


def _start_listed(repo):
    lines = repo.forge("next").stdout.splitlines()
    assert LISTED in lines
    started = repo.forge(*shlex.split(lines[lines.index(LISTED) + 1].removeprefix("Next: "))[1:])
    assert started.returncode == 0, started.stderr
    return started.stdout


def test_4_a_later_numbered_refresh_holds_the_offer_back(repo, monkeypatch):
    _old_lockfile(repo, monkeypatch)
    monkeypatch.setenv("FORGE_NOW", "2026-09-10T10:00:00+00:00")
    first = _start_listed(repo)
    where = first.splitlines()[0].rsplit(" in ", 1)[1]
    # The refresh found nothing to update: its squash merge carries only its fix record.
    repo.git("worktree", "remove", "--force", where)
    repo.git("merge", "-q", "--squash", "fix/refresh-dependencies")
    repo.git("commit", "-q", "-m", "Refresh dependencies (#1)")
    repo.git("push", "-q", "origin", "main")
    assert repo.git("diff", "--name-only", "HEAD~1") == ".factory/fixes/refresh-dependencies.json"

    # The lockfile is still old by git log, so it is offered again, and fix start numbers the name.
    assert _start_listed(repo).startswith("Started fix refresh-dependencies-2")
    again = repo.forge("next").stdout
    assert LISTED not in again
    assert "The fix refresh-dependencies-2 is started" in again
