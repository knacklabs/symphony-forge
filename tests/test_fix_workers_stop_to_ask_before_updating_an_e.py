"""Existing tests broken by intended work may be updated across task scopes."""
from __future__ import annotations

from test_close import env
from test_task import story
from test_worker import calls, install_claude

STORY = "FIX-WORKERS-STOP-TO-ASK-BEFORE-UPDATING-AN-E"


def test_1_worker_brief_allows_existing_broken_tests_and_requires_handoff(repo):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
                             'models.build = { model = "sonnet", effort = "medium" }\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")

    started = repo.forge("fix", "start", "Allow broken existing tests", "--done",
                         "Workers update tests their changes break")
    assert started.returncode == 0, started.stderr
    built = repo.forge("work", "allow-broken-existing-tests")
    assert built.returncode == 0, built.stderr
    brief = calls(log)[-1]["brief"]
    assert "existing test" in brief.lower()
    assert "outside Scope" in brief
    assert "name each" in brief.lower()
    assert "why" in brief.lower()
    assert "never weaken a test to hide a defect" in brief.lower()

    story(repo)
    started = repo.forge("task", "start", "BOARD/PAGE")
    assert started.returncode == 0, started.stderr
    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stderr
    task_brief = calls(log)[-1]["brief"]
    assert "You may also update an existing test your intended change breaks" in task_brief
    assert "name each such test and why it changed in your handoff" in task_brief


def test_2_close_excludes_existing_tests_and_flags_weakened_tests(env):
    env.repo.write("tests/test_old.py", "def test_old():\n    assert True\n")
    env.repo.write("web/test_board.py", "def test_board():\n    assert True\n")
    env.repo.write("src/component.test.ts", "export const old = true;\n")
    env.repo.write("src/component.spec.ts", "export const old = true;\n")
    env.repo.write("web/board_test.py", "def board():\n    assert True\n")
    env.repo.write("web/tests/board.py", "def board():\n    assert True\n")
    env.repo.write("tests/fixtures/data.txt", "original\n")
    env.repo.git("add", "tests", "web", "src")
    env.repo.git("commit", "-q", "-m", "Add existing tests")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_task(changes={
        "app.py": "print('saved')\n",
        "tests/test_old.py": "def test_old():\n    assert False\n",
        "web/test_board.py": "def test_board():\n    assert False\n",
        "src/component.test.ts": "export const old = false;\n",
        "src/component.spec.ts": "export const old = false;\n",
        "web/board_test.py": "def board():\n    assert False\n",
        "web/tests/board.py": "def board():\n    assert False\n",
        "tests/test_new.py": "def test_new():\n    assert True\n",
        "web/test_new.py": "def test_new():\n    assert True\n",
        "tests/fixtures/data.txt": "changed\n",
        "other.py": "x = 1\n",
    })
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    prompt = env.prompt()
    outside = prompt.split("Files the branch changes outside that scope", 1)[1].split(
        "## Done when", 1)[0]
    for path in ("tests/test_old.py", "web/test_board.py", "src/component.test.ts",
                 "src/component.spec.ts", "web/board_test.py", "web/tests/board.py"):
        assert path not in outside
    for path in ("tests/test_new.py", "web/test_new.py", "tests/fixtures/data.txt",
                 "other.py"):
        assert f"- {path}" in outside
    assert "Report a test weakened to hide a real defect as a P1 finding." in prompt
