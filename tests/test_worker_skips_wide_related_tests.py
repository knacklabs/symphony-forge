"""Work skips broad laptop selections and keeps narrow ones in the test lane."""
import json
import re
import sys
from pathlib import Path

import pytest

from test_worker import calls, install_claude

STORY = "laptop-tests-before-push"


# Audit: the command-level contract is whether a worker round runs selected pytest files or
# records the agreed skip when selection reaches half the suite or the full-suite fallback.
# Regression: broad selections spend hours on the laptop, while a narrow selection is skipped.
# Existing worker tests cover pass/repair reporting but not width-based selection or its guidance.
# Real fix/work commands, pytest collection and execution receipts own this boundary; only Claude
# is stubbed. This uses no production seam.
@pytest.mark.platform
@pytest.mark.parametrize("test_place", ["ci", "local"])
@pytest.mark.parametrize("scenario", [
    "below-half",
    "exactly-half",
    "always-node-ids-one-file",
    "always-test-reaches-half",
    "root-dependency-fallback",
    "custom-full-test-fallback",
])
def test_4_worker_skips_wide_related_test_selections(repo, tmp_path, monkeypatch,
                                                       test_place, scenario):
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    monkeypatch.delenv("FORGE_WORKER_TESTS", raising=False)
    log = install_claude(repo)
    receipts = tmp_path / "pytest-receipts.txt"
    python = json.dumps(Path(sys.executable).as_posix())
    forge = json.dumps((repo.bin / "forge").as_posix())
    test_command = f"{python} -m pytest -q tests"
    lines = [f'version = {json.dumps(repo.forge("--version").stdout.split()[-1])}',
             'repo = "forge-source"', 'workers = "claude"',
             f'test_place = {json.dumps(test_place)}', 'checks = ["tests"]',
             f"test = {json.dumps(test_command)}"]

    if scenario == "custom-full-test-fallback":
        check = repo.write("check.py", "from pathlib import Path\n"
                           f"with Path({json.dumps(receipts.as_posix())}).open('a', encoding='utf-8') as out:\n"
                           "    out.write('custom full test command\\n')\n")
        lines[-1] = f"test = {json.dumps(f'{python} {json.dumps(check.name)}')}"
    else:
        picker = f"{python} {forge} test --pytest {{base}}"
        lines.append("fast_test = " + json.dumps(picker))

    references = {
        "below-half": 1,
        "exactly-half": 2,
        "always-node-ids-one-file": 1,
        "always-test-reaches-half": 1,
        "root-dependency-fallback": 1,
        "custom-full-test-fallback": 1,
    }[scenario]
    always_nodes = []
    test_counts = [1, 1, 1, 1]
    if scenario == "always-node-ids-one-file":
        test_counts[0] = 3
        always_nodes = [f"tests/test_1.py::test_receipt_{number}" for number in range(1, 4)]
    elif scenario == "always-test-reaches-half":
        test_counts[1] = 2
        always_nodes = [f"tests/test_2.py::test_receipt_{number}" for number in range(1, 3)]
    if always_nodes:
        repo.write(".forge/always-tests.txt", "\n".join(always_nodes) + "\n")

    repo.write("forge.toml", "\n".join(lines) + "\n")
    repo.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
    repo.write("README.md", "# A test repo\n")
    repo.write("app/__init__.py", "")
    repo.write("app/product.py", "VALUE = 'before'\n")
    if scenario == "root-dependency-fallback":
        repo.write("requirements.txt", "base dependency\n")
    for index, count in enumerate(test_counts, 1):
        body = [f"# This test covers app/product.py." if index <= references else ""]
        if index <= references:
            body.extend(["from app import product", ""])
        for number in range(1, count + 1):
            name = f"test_receipt_{number}"
            if index <= references:
                body.append(f"def {name}():")
                body.append("    assert product.VALUE == 'after'")
            else:
                body.append(f"def {name}():")
                body.append("    assert Path('README.md').read_text('utf-8').startswith('#')")
                body.insert(0, "from pathlib import Path")
            body.extend([f"    with Path({json.dumps(receipts.as_posix())}).open('a', encoding='utf-8') as out:",
                         f"        out.write('tests/test_{index}.py::{name}\\n')", ""])
        if index <= references:
            body.insert(0, "from pathlib import Path")
        repo.write(f"tests/test_{index}.py", "\n".join(body))

    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up wide-selection worker checks")
    repo.git("push", "-q", "origin", "main")

    slug = f"wide-{test_place}-{scenario}"
    started = repo.forge("fix", "start", f"Check {scenario} worker tests", "--done",
                         "The worker skips broad related tests", "--kind", "mechanical",
                         "--slug", slug)
    assert started.returncode == 0, started.stdout + started.stderr
    match = re.search(r" in (.+)$", started.stdout.splitlines()[0])
    assert match, started.stdout
    checkout = Path(match[1])
    (checkout / "app" / "product.py").write_text("VALUE = 'after'\n", encoding="utf-8")
    changed = ["app/product.py"]
    if scenario == "root-dependency-fallback":
        (checkout / "requirements.txt").write_text("changed dependency\n", encoding="utf-8")
        changed.append("requirements.txt")
    repo.git("add", *changed, cwd=checkout)
    repo.git("commit", "-qm", "Change product behavior", cwd=checkout)

    built = repo.forge("work", slug)

    assert built.returncode == 0, built.stdout + built.stderr
    skip = scenario in {"exactly-half", "always-test-reaches-half",
                        "root-dependency-fallback", "custom-full-test-fallback"}
    output = receipts.read_text("utf-8").splitlines() if receipts.exists() else []
    expected = []
    if not skip:
        count = test_counts[0] if scenario == "always-node-ids-one-file" else 1
        expected = [f"tests/test_1.py::test_receipt_{number}" for number in range(1, count + 1)]
    assert output == expected, built.stdout + built.stderr
    if skip:
        assert "skipped: selection near the full suite, CI tests it" in built.stdout
        assert "Related tests passed." not in built.stdout
    else:
        assert "skipped: selection near the full suite, CI tests it" not in built.stdout
        assert "Related tests passed." in built.stdout

    if test_place == "ci" and scenario == "exactly-half":
        explicit = repo.forge("test", "--change", cwd=checkout)
        assert explicit.returncode == 0, explicit.stdout + explicit.stderr
        assert "skipped: selection near the full suite, CI tests it" not in explicit.stdout
        assert receipts.read_text("utf-8").splitlines() == [
            "tests/test_1.py::test_receipt_1", "tests/test_2.py::test_receipt_1"]

    turn = calls(log)[0]
    assert "at least half of the test files" in turn["brief"].lower()
    assert "the selection falls back to the full suite" in turn["brief"].lower()
