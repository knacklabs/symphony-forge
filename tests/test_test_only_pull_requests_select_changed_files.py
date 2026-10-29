"""Test-only CI selects one Linux group and only changed Windows platform files.

Test-audit: This protects CI's executable classification contract. Static matrices
previously allocated every group. Picker tests cover execution, but do not cover
the CI outputs that choose runners. No production seam or fake decides selection.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_groups_pytest import _adopted_client, _branch, _new_client, _settings
from test_ci_limits_pull_requests_to_linux import expression

STORY = "FIX-TEST-ONLY-PR-RUNS-EVERY-GROUP"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_test_only_pull_requests_select_changed_files(repo, gh, tmp_path, adopted):
    client = (_adopted_client(repo, tmp_path, "client") if adopted
              else _new_client(repo, gh, tmp_path, "client"))
    if not adopted:
        _branch(repo, client, "ci-selection")
    _settings(client, test=json.dumps(Path(sys.executable).as_posix()) + " -m pytest tests -q")
    ignore = client / ".gitignore"
    ignore.write_text((ignore.read_text("utf-8") if ignore.exists() else "")
                      + "\n__pycache__/\n", encoding="utf-8")
    for name, source in {
        "score_notes": "def test_scores(): assert True\n",
        "platform_case": "import pytest\n@pytest.mark.platform\ndef test_native(): assert True\n",
        "unrelated": "def test_unrelated(): assert False\n",
        "shared": "VALUE = 1\ndef test_shared(): assert VALUE == 2\n",
        "bridge": "from test_shared import VALUE\n",
        "consumer": "import pytest\nfrom test_bridge import VALUE\n"
                    "@pytest.mark.platform\ndef test_consumer(): assert VALUE == 2\n",
    }.items():
        path = client / f"tests/test_{name}.py"
        path.parent.mkdir(exist_ok=True)
        path.write_text(source, encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Set up CI selection", cwd=client)
    base = repo.git("rev-parse", "HEAD", cwd=client).strip()
    output = tmp_path / "outputs"

    for name in ("score_notes", "platform_case", "shared"):
        path = client / f"tests/test_{name}.py"
        path.write_text(path.read_text("utf-8").replace("VALUE = 1", "VALUE = 2")
                        + "# Changed\n", encoding="utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-qm", "Change one test", cwd=client)
        output.write_text("", encoding="utf-8")
        classified = subprocess.run(
            [sys.executable, ".forge/review-tests.py"], cwd=client,
            env={**os.environ, "BASE_SHA": base, "HEAD_SHA": "HEAD",
                 "DOCS_ONLY_EXCLUDES": '[]', "GITHUB_OUTPUT": str(output)},
            capture_output=True, text=True, timeout=30)
        assert classified.returncode == 0, classified.stdout + classified.stderr
        values = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
        assert values.get("test-only") == ("false" if name == "shared" else "true"), (
            name, values, repo.git("diff", "--name-only", base, cwd=client))
        expected = ["tests/test_platform_case.py"] if name == "platform_case" else []
        assert json.loads(values["platform-files"]) == expected
        assert values["run-windows"] == str(name == "shared" or bool(expected)).lower()
        workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
        groups = re.search(r"^        group: (.+)$", workflow, re.M)[1]
        groups = groups.replace("needs.docs-check.outputs.test-only", "github.test_only")
        selected_groups = expression(groups, test_only=values["test-only"])
        assert selected_groups == (list(range(1, 7)) if adopted and name == "shared" else [1])
        windows = (ROOT / ".github/workflows/forge-next.yml").read_text("utf-8")
        matrix = re.search(r"include: >-\n(.+?)\n    runs-on:", windows, re.S)[1]
        rows = expression(" ".join(matrix.splitlines()), test_only=values["test-only"])
        assert rows == ([{"os": "windows-latest", "group": group, "groups": 5}
                         for group in range(1, 6)] if name == "shared" else
                        [{"os": "windows-latest", "group": 1, "groups": 1}])
        # The emitted one-group decision uses the real picker, which must never
        # collect the deliberately failing unrelated file.
        selected = repo.forge("test", "--pytest", base, cwd=client)
        assert selected.returncode == 0, selected.stdout + selected.stderr
        assert ("2 passed" if name == "shared" else "1 passed") in selected.stdout
        repo.git("revert", "--no-edit", "HEAD", cwd=client)

    assert "needs.selection.outputs.run-windows != 'false'" in windows
    assert "ConvertFrom-Json $env:PLATFORM_FILES" in windows
