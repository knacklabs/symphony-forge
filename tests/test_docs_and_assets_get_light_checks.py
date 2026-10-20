"""Docs and brand assets use light close and skip CI groups unless tests consume them."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client, _land_fixture
from test_close import GREEN, STORY_DOC, blocked, env, finding  # noqa: F401
from test_fix_gate_on_split_checks import bash, jobs

STORY = "FIX-DOCS-ASSETS-LIGHT"


@pytest.mark.parametrize("history,case", [
    ("new", case) for case in ("docs", "asset", "generated", "read-doc", "read-asset", "code",
                              "read-jest", "read-conftest", "duplicate-basename", "longer-name",
                              "read-relative", "read-joined", "read-node-joined",
                              "duplicate-joined", "duplicate-root-joined")
] + [("adopted-v1.2.2", case) for case in ("asset", "read-conftest", "duplicate-basename")])
def test_1_docs_and_assets_get_light_review_and_skip_ci_groups(
        env, tmp_path, monkeypatch, history, case):
    # Audit: close owns the review level; the shipped workflow command and gate own CI.
    # Real test code reads the changed fixture. Only GitHub and Autoreview are faked.
    _client(env.repo, env.gh, tmp_path, history)
    env.checks(GREEN)
    env.repo.git("switch", "-qc", "fix/configure-docs-checks")
    env.repo.write(".factory/fixes/configure-docs-checks.json", json.dumps({
        "kind": "fix", "branch": "fix/configure-docs-checks", "status": "started",
        "why": "Configure docs checks", "done_when": "Docs checks are configured"}))
    path = ("README.md" if case == "duplicate-root-joined" else
            "docs/README.md" if case in {"duplicate-basename", "longer-name", "duplicate-joined"} else
            "docs/guide.txt" if case in {"docs", "read-doc", "read-relative"} else "brand/logo.svg")
    env.commit(env.repo.path, path, "Original\n")
    test = ("from pathlib import Path\ndef test_content():\n"
            f"    assert Path({json.dumps(path)}).read_text()\n"
            if case in {"read-doc", "read-asset"} else "def test_content():\n    assert True\n")
    if case.startswith("duplicate-") or case == "longer-name":
        unrelated = "docs/README.md.backup" if case == "longer-name" else "fixtures/README.md"
        env.commit(env.repo.path, unrelated, "Unrelated fixture\n")
        test = ("from pathlib import Path\ndef test_content():\n"
                f"    assert Path({json.dumps(unrelated)}).read_text()\n")
        if case.endswith("joined"):
            test = ("from pathlib import Path\ndef test_content():\n"
                    "    assert (Path('fixtures') / 'README.md').read_text()\n")
    elif case == "read-relative":
        test = ("from pathlib import Path\ndef test_content():\n"
                "    assert (Path(__file__).parent / '../docs/guide.txt').read_text()\n")
    elif case == "read-joined":
        test = ("from pathlib import Path\ndef test_content():\n"
                "    assert (Path('brand') / 'logo.svg').read_text()\n")
    elif case == "read-conftest":
        env.commit(env.repo.path, "conftest.py", "from pathlib import Path\n"
                   f"def read_input():\n    return Path({json.dumps(path)}).read_text()\n")
        test = ("import runpy\ndef test_content():\n"
                "    assert runpy.run_path('conftest.py')['read_input']()\n")
    env.commit(env.repo.path, "tests/test_content.py", test)
    receipt = tmp_path / "suite-ran"
    suite = tmp_path / "suite.py"
    run_test = "import runpy\nrunpy.run_path('tests/test_content.py')['test_content']()\n"
    if case in {"read-jest", "read-node-joined"}:
        node = shutil.which("node")
        assert node, "The JavaScript consumer regression requires Node."
        reference = (json.dumps(path) if case == "read-jest" else
                     "require('node:path').join(__dirname, '../brand', 'logo.svg')")
        env.commit(env.repo.path, "__tests__/cart.js",
                   "const fs = require('node:fs');\n"
                   f"require('node:assert/strict').ok(fs.readFileSync({reference}, 'utf8'));\n")
        run_test = ("import subprocess\n"
                    f"subprocess.run([{json.dumps(Path(node).as_posix())}, '__tests__/cart.js'], check=True)\n")
    suite.write_text("from pathlib import Path\n" + run_test +
                     f"Path({json.dumps(receipt.as_posix())}).touch()\nprint('1 passed')\n", "utf-8")
    command = f'"{Path(sys.executable).as_posix()}" "{suite.as_posix()}"'
    config = env.repo.path / "forge.toml"
    text = re.sub(r"^(?:fast_test|test) = .*\n?", "", config.read_text("utf-8"), flags=re.M)
    env.commit(env.repo.path, "forge.toml", "test = " + json.dumps(command) + "\nfast_test = "
               + json.dumps(command) + "\n" + text)
    if case == "generated":
        attrs = (env.repo.path / ".gitattributes").read_text("utf-8")
        env.commit(env.repo.path, ".gitattributes", attrs + f"{path} linguist-generated\n")
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Sync checks")
    env.repo.git("switch", "-q", "main")
    env.repo.git("merge", "-q", "--ff-only", "fix/configure-docs-checks")
    _land_fixture(env.repo)
    # Prepare the owner's plan from a fresh clone; installed client hooks
    # correctly refuse the helper's setup commits on the original main.
    coordinator = tmp_path / "story-coordinator"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(coordinator))
    env.repo.path = coordinator
    changes = {path: "Updated\n"}
    if case == "code":
        changes["app.py"] = "value = 1\n"
    # Story parts retain the full-vs-light P1 boundary; fixes now follow up
    # every non-P0 after their first review.
    item, where = env.start_approved_task(STORY_DOC, changes=changes)
    base = env.repo.git("rev-parse", "origin/main")
    light = case in {"docs", "asset", "longer-name"} or case.startswith("duplicate-")
    env.reviews(blocked(finding("P1", "Docs review finding", path)))
    closed = env.close(item)
    # The same ordinary finding is advisory in a light review and blocks a full review.
    assert (closed.returncode == 0) == light, closed.stdout + closed.stderr
    assert ("Docs review finding" in closed.stderr) == (not light), closed.stderr
    assert bool(env.gh_calls("pr", "ready")) == light
    assert receipt.exists() == (not light), closed.stdout
    checked_review = env.repo.forge("hook", "pr-check", "--base", base, "--head",
                                   env.repo.git("rev-parse", "HEAD", cwd=where),
                                   "--branch", "task/SHOP-T1")
    assert (checked_review.returncode == 0) == light, checked_review.stderr
    receipt.unlink(missing_ok=True)

    workflow = (where / ".github/workflows/forge.yml").read_text("utf-8")
    grouped = jobs(workflow)
    assert "docs-check" in grouped, "Classify docs before starting any test group"
    preflight = grouped["docs-check"]
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", env.repo.git("rev-parse", "HEAD", cwd=where))
    monkeypatch.setenv("DOCS_ONLY_EXCLUDES", re.search(
        r"DOCS_ONLY_EXCLUDES: '(.*)'", preflight)[1])
    output = tmp_path / "workflow-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    command_line = re.search(r"run: (python .forge/review-tests.py[^\n]*)", preflight)[1]
    checked = subprocess.run([sys.executable, *command_line.split()[1:]], cwd=where,
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    assert (outputs.get("docs-only") == "true") == light
    assert "needs: docs-check" in grouped["tests"]
    assert "needs.docs-check.outputs.docs-only != 'true'" in grouped["tests"]
    gate = grouped["tests-passed"]
    assert "needs: [docs-check, tests]" in gate
    gate_command = re.search(r"run: (.+)$", gate, re.M)[1]
    for check, groups, docs, expected in [
        ("success", "skipped" if light else "success", str(light).lower(), True),
        ("failure", "skipped", "true", False),
        ("success", "failure", "false", False),
        ("success", "cancelled", "false", False),
        ("success", "skipped", "false", False),
    ]:
        assert (bash("-c", gate_command, env={"DOCS_CHECK": check, "GROUPS": groups,
                                             "DOCS_ONLY": docs}).returncode == 0) == expected
