"""Test audit: real decision commands protect repaired stops and upgrade proof.

Old stops skip repair reviews; old full-run walks reject version-only changes.
Existing coverage has no repaired stopped review or version-only upgrade.
Reuse client fixtures and external service stubs without a production seam.
"""
import json
from pathlib import Path

import pytest

from conftest import StubGh
from test_proto_signoff import _adopted_client, _client, _decision, _request_build
from test_signoff_review_rounds import _report

STORY = "FIX-A-SAVED-SIGN-OFF-STOP-IS-SHOWN-WITHOUT-C"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-release"])
def test_1_repaired_stop_checks_latest_product(repo, tmp_path, monkeypatch, adopted):
    fix, answers, queue = (_adopted_client if adopted else _client)(repo, tmp_path, monkeypatch)
    if adopted:
        _request_build(repo, fix)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([_report("P1"), _report("P1")]), encoding="utf-8")

    def accept():
        return repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert "Order submission fails" in accept().stderr
    assert "One more round, split or accept?" in accept().stderr
    calls = queue.with_suffix(".calls.jsonl")
    before = len(calls.read_text("utf-8").splitlines())
    assert "One more round, split or accept?" in accept().stderr
    assert len(calls.read_text("utf-8").splitlines()) == before
    (fix / "app.py").write_text("print('repaired order')\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=fix)
    repo.git("commit", "-qm", "Repair order flow", cwd=fix)
    queue.write_text(json.dumps([{"report": {"review_status": "scoped-clean", "findings": []}}]),
                     encoding="utf-8")
    repaired = accept()
    assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    assert len(calls.read_text("utf-8").splitlines()) == before + 1
    assert "status: accepted" in page.read_text("utf-8")


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-release"])
@pytest.mark.parametrize("other_setting", [False, True], ids=["version-only", "other-setting"])
def test_2_upgrade_keeps_full_run_only_for_version(repo, tmp_path, monkeypatch, adopted, other_setting):
    fix, answers, queue = (_adopted_client if adopted else _client)(repo, tmp_path, monkeypatch)
    if adopted:
        _request_build(repo, fix)
    config = repo.path / "forge.toml"
    current = config.read_text("utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    changed = current.replace(json.dumps(version), json.dumps(
        version[1:] if version.startswith("v") else "v" + version), 1)
    if other_setting:
        changed = 'stack = "off"\n' + changed
    config.write_text(changed, encoding="utf-8")
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Update the Forge pin")
    remote = Path(repo.git("remote", "get-url", "origin"))
    repo.git("fetch", "-q", str(repo.path), "main:main", cwd=remote)
    sha = repo.git("rev-parse", "HEAD")
    StubGh(repo.bin).respond("api", f"repos/{{owner}}/{{repo}}/commits/{sha}/statuses", stdout="[]")
    repo.git("merge", "--no-edit", "main", cwd=fix)
    page = _decision(fix, answers)
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == (1 if other_setting else 0), accepted.stdout + accepted.stderr
    if other_setting:
        assert "full test run" in accepted.stderr
    else:
        assert "status: accepted" in page.read_text("utf-8")
