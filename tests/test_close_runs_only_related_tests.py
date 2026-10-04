"""Forge's own close uses related pytest files; shared test inputs require the full suite."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from test_close import env  # noqa: F401 (pytest fixture)

STORY = "FIX-FORGE-S-OWN-CLOSES-STILL-RUN-THE-WHOLE-T"
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("shared_input", [None, "conftest.py", "pyproject.toml", "uv.lock"])
def test_1_close_runs_only_changed_and_module_related_tests_unless_shared_inputs_change(
        env, monkeypatch, shared_input):
    # Use this repo's commands and dependencies, with tiny real tests so closing cannot
    # accidentally recurse into the enclosing suite. Only review and GitHub are faked.
    for rel in ("forge.toml", "pyproject.toml", "uv.lock", "scripts/fast-test.py"):
        source = ROOT / rel
        if source.exists():
            env.repo.write(rel, source.read_text("utf-8"))
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", sys.prefix)
    monkeypatch.setenv("UV_NO_SYNC", "1")  # Reuse the enclosing run's installed test dependencies.
    log = env.tmp / "pytest-ran"
    log.mkdir()
    env.repo.write("conftest.py", f'''import json, pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
@pytest.fixture(autouse=True)
def record_run(request):
    workers = request.config.workerinput["workercount"]
    (pathlib.Path({str(log)!r}) / request.node.name).write_text(json.dumps(workers))
''')
    env.repo.write("src/probe_module.py", "VALUE = 1\n")
    # Relatedness now comes from the filename or a qualified Forge reference,
    # rather than any bare module name appearing in the test's body.
    env.repo.write("tests/test_probe_module_related.py", "from probe_module import VALUE\n"
                   "def test_related():\n    assert VALUE >= 1\n")
    env.repo.write("tests/test_changed.py", "def test_changed():\n    assert 2 + 2 == 4\n")
    env.repo.write("tests/test_unrelated.py", "def test_unrelated():\n    assert 3 + 3 == 6\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Use Forge's own test settings")
    env.repo.git("push", "-q", "origin", "main")
    changes = {"src/probe_module.py": "VALUE = 2\n",
               "tests/test_changed.py": "def test_changed():\n    assert 4 + 4 == 8\n"}
    if shared_input:
        changes[shared_input] = (env.repo.path / shared_input).read_text("utf-8") + "\n# Changed\n"
    item, _ = env.start_fix(changes)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    expected = {"test_changed", "test_related"}
    if shared_input:
        expected.add("test_unrelated")
    assert {path.name for path in log.iterdir()} == expected
    assert {json.loads(path.read_text()) for path in log.iterdir()} == {
        max(1, (os.cpu_count() or 1) // 2)}
