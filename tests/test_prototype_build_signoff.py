"""Working-build proof reaches the strict sign-off reviewer.

Contract: sign-off gives the review a proof map and test results for its product.
Regression: the isolated reviewer sees test names but cannot verify their outcomes,
or receives stale passing results after the product changes. Existing sign-off
tests cover answers and customer approval, not the test-run transport and binding.
No production seam: invoke the decision commands; fake only the reviewer.
"""
import json
import sys
from pathlib import Path

from test_proto_signoff import SOL_HIGH, _client, _decision


STORY = "FORGE-PACE-1"


def test_36_working_build_signoff_requires_and_reviews_demo_proof(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    created = repo.forge("decision", "new", "client-signoff", cwd=fix)
    assert created.returncode == 0, created.stderr
    page = fix / "docs/decisions/0001-client-signoff.md"
    assert "## Proof" in page.read_text("utf-8")
    page = _decision(fix, answers, proof="")
    missing = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert missing.returncode == 1, missing.stdout + missing.stderr
    assert "Proof" in missing.stderr
    assert not queue.with_suffix(".calls.jsonl").exists()

    # The positive proof names a real demo test, run through Forge, not a fabricated receipt.
    tests = fix / "tests"
    tests.mkdir(exist_ok=True)
    (fix / ".gitignore").write_text("__pycache__/\n*.pyc\n.pytest_cache/\n", encoding="utf-8")
    (tests / "test_demo.py").write_text(
        "import subprocess, sys\n\ndef test_open():\n"
        "    result = subprocess.run([sys.executable, 'app.py'], capture_output=True, "
        "text=True, check=True)\n"
        "    assert result.stdout.strip() == 'prototype'\n", encoding="utf-8")
    config = fix / "forge.toml"
    command = f'"{Path(sys.executable).as_posix()}" -m pytest -q'
    config.write_text(config.read_text("utf-8") + "\ntest = " + json.dumps(command) + "\n",
                      encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-qm", "Prove the demo workflow", cwd=fix)
    tested = repo.forge("test", cwd=fix)
    assert tested.returncode == 0, tested.stdout + tested.stderr
    assert "1 passed" in tested.stdout
    proof = "## Proof\n- Open the prototype: tests/test_demo.py::test_open\n"
    page.write_text(page.read_text("utf-8") + "\n" + proof, encoding="utf-8")
    clean = {"report": {"review_status": "scoped-clean", "findings": []}}
    queue.write_text(json.dumps([
        {**clean, "say": "model: claude-opus-5-5\nthinking: high\nautoreview done"},
        {**clean, "say": SOL_HIGH},
    ]))
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text().splitlines()]
    [call] = [call for call in calls if "Test results for this product" in
              "\n".join(call["prompt_files"].values())]
    prompt = "\n".join(call["prompt_files"].values())
    assert "Open the prototype: tests/test_demo.py::test_open" in prompt
    assert "every demo workflow step" in prompt
    assert "passing test" in prompt
    assert "Test results for this product" in prompt
    assert "passed tests/test_demo.py::test_open" in prompt

    # A new product commit needs its own results, even when the old test would still pass.
    app = fix / "app.py"
    app.write_text(app.read_text("utf-8") + "# A new product revision.\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=fix)
    repo.git("commit", "-qm", "Revise the demo", cwd=fix)
    _decision(fix, answers, proof="- Open the prototype: tests/test_demo.py::test_open")
    queue.write_text(json.dumps([clean | {"say": SOL_HIGH}]))
    reviewed = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text().splitlines()]
    [call] = [call for call in calls if "No test results match this product" in
              "\n".join(call["prompt_files"].values())]
    prompt = "\n".join(call["prompt_files"].values())
    assert "No test results match this product" in prompt
    assert "passed tests/test_demo.py::test_open" not in prompt
