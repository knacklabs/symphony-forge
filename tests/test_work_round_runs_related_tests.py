"""Each worker round runs its real test command and allows one repair turn on failure."""
import json
import os
import re
import sys

import pytest

from test_worker import calls, install_claude
from test_tools_session_hold import Session
from conftest import ROOT, _install
from test_codex_worker import sdk_data, _sent  # noqa: F401

STORY = "laptop-tests-before-push"


# Observable contract: work executes the configured check against the worker's actual edit.
# Regression: CI-mode work returns without executing that check, or repeatedly repairs a red run.
# Existing prompt tests cannot detect a command that never runs. Only the external model is fake;
# the configured check, git commits, work command and test lane are real. No production seam.
@pytest.mark.parametrize("test_place", ["local", "ci"])
@pytest.mark.parametrize("result", ["pass", "repair", "red"])
@pytest.mark.parametrize("route", ["external", "native", "codex"])
def test_1_work_runs_related_tests_and_repairs_once(repo, monkeypatch, tmp_path, request,
                                                  test_place, result, route):
    log = install_claude(repo)
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    version = repo.forge("--version").stdout.split()[-1]
    counted = repo.bin / "test-runs.txt"
    repo.write("check.py", "from pathlib import Path\n"
               f"counter = Path({counted.as_posix()!r})\n"
               "with counter.open('a', encoding='utf-8') as out: out.write('run\\n')\n"
               "assert Path('product.txt').read_text('utf-8') == 'good', 'product is broken'\n")
    command = f'"{sys.executable}" check.py'
    family = "codex" if route == "codex" else "claude"
    model = "gpt-6-sol" if route == "codex" else "sonnet"
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               f'workers = "{family}"\n'
               f'test_place = "{test_place}"\nchecks = ["tests"]\n'
               f'test = {json.dumps(command)}\n'
               f'models.lite = {{ model = "{model}", effort = "medium" }}\n')
    repo.write("product.txt", "good")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure the real product check")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Repair product", "--done", "The product check passes",
                         "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    expected = 1 if result == "pass" else 2
    if route == "codex":
        # The real SDK talks to a fake model service; only that service makes the worker edit.
        monkeypatch.setenv("XDG_DATA_HOME", str(request.getfixturevalue("sdk_data")))
        stub = (ROOT / "tests/stubs/codex-app-server").read_text("utf-8")
        marker = '        elif method == "turn/start":\n'
        edit = ("            import subprocess\n"
                "            repairing = \"The change's related tests failed.\" in params['input'][0]['text']\n"
                f"            good = {result == 'pass'!r} or (repairing and {result == 'repair'!r})\n"
                "            (pathlib.Path(cwd) / 'product.txt').write_text('good' if good else 'broken', encoding='utf-8')\n"
                "            subprocess.run(['git', 'add', 'product.txt'], cwd=cwd, check=True)\n"
                "            subprocess.run(['git', 'commit', '--allow-empty', '-qm', 'Worker edit'], cwd=cwd, check=True, stdout=sys.stderr)\n")
        _install(repo.bin, "codex-app-server", stub.replace(marker, marker + edit))
        monkeypatch.setenv("CODEX_BIN", str(repo.bin / (
            "codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
        built = repo.forge("work", "repair-product")
        assert built.returncode == 0, built.stdout + built.stderr
        codex_log = repo.bin / "codex-app-server.jsonl"
        turns = _sent(codex_log, "turn/start")
        assert len(turns) == expected
        if result != "pass":
            assert "product is broken" in turns[1]["input"][0]["text"]
            assert _sent(codex_log, "thread/resume")
        assert counted.read_text("utf-8").splitlines() == ["run"] * expected
        assert ("Related tests failed." if result == "red" else "Related tests passed.") in built.stdout
        return
    if route == "native":
        # A real session owns the native handback and must keep its place for the repair turn.
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        data = tmp_path / "without-claude-sdk"
        data.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(data))
        host = Session(repo, tmp_path / "host", "claude-session")
        folder = repo.path.parent / f"{repo.path.name}-fix-repair-product"
        try:
            given = host.forge("work", "repair-product")
            assert given.returncode == 0, given.stdout + given.stderr
            match = re.search(r"forge handback repair-product --round (\d+)", given.stdout)
            assert match, given.stdout + given.stderr
            number = match[1]
            for turn in range(expected):
                good = result == "pass" or (turn == 1 and result == "repair")
                (folder / "product.txt").write_text("good" if good else "broken", "utf-8")
                repo.git("add", "product.txt", cwd=folder)
                repo.git("commit", "--allow-empty", "-qm", "Worker edit", cwd=folder)
                built = host.forge("handback", "repair-product", "--round", number,
                                   "--subagent", "worker", "--text", "The edit is committed.")
                assert built.returncode == 0, built.stdout + built.stderr
                if turn == 0 and result != "pass":
                    assert "Send this to subagent worker, then hand back again:" in built.stdout
                    assert "product is broken" in built.stdout
            assert "Send this to subagent" not in built.stdout
        finally:
            host.close()
        assert counted.read_text("utf-8").splitlines() == ["run"] * expected
        assert ("Related tests failed." if result == "red" else "Related tests passed.") in built.stdout
        return
    sdk = repo.bin / "claude_agent_sdk" / "__init__.py"
    source = sdk.read_text("utf-8")
    marker = '    if os.environ.get("STUB_CLAUDE_LEAVE"):'
    assert marker in source
    edit = ("    import subprocess\n"
            f"    repairing = \"The change's related tests failed.\" in prompt\n"
            f"    good = {result == 'pass'!r} or (repairing and {result == 'repair'!r})\n"
            "    Path('product.txt').write_text('good' if good else 'broken', encoding='utf-8')\n"
            "    subprocess.run(['git', 'add', 'product.txt'], check=True)\n"
            "    subprocess.run(['git', 'commit', '--allow-empty', '-qm', 'Worker edit'], check=True)\n")
    sdk.write_text(source.replace(marker, edit + marker), "utf-8")
    built = repo.forge("work", "repair-product")
    assert built.returncode == 0, built.stdout + built.stderr
    assert counted.exists(), built.stdout + built.stderr
    assert counted.read_text("utf-8").splitlines() == ["run"] * expected
    turns = calls(log)
    assert len(turns) == expected
    if result != "pass":
        assert "product is broken" in turns[1]["brief"]
        assert turns[1]["options"]["resume"]
    assert ("Related tests failed." if result == "red" else "Related tests passed.") in built.stdout
