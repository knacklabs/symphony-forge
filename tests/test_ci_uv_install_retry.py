"""The generated Actions contract retries uv installation once.

Test-audit gate: protect automatic recovery and a final failed install at the generated
workflow boundary, including replacement of an earlier release's existing workflow.
Omitting, relocating or restricting the retry, or allowing its error, breaks this contract.
Existing bootstrap tests only check tool presence. These command tests need no new seam.
"""
import re

import pytest

from conftest import ROOT
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "FIX-UV-SETUP-RETRY"


def _assert_retry(client):
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    jobs = dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow, re.M | re.S))
    for name in ("tests", "forge-pr-check", "full-suite"):
        steps = [dict(re.findall(r"^[ \t]*([\w-]+):[ \t]*(.*?)[ \t]*$", step, re.M))
                 for step in re.split(r"^      - ", jobs[name], flags=re.M)[1:]]
        installs = [step for step in steps if step.get("uses", "").startswith("astral-sh/setup-uv@")]
        assert len(installs) == 2, name
        first, retry = installs
        assert first.get("continue-on-error") == "true", name
        assert "if" not in first, name
        assert first["uses"] == retry["uses"], name
        assert retry.get("continue-on-error", "false") == "false", name
        assert first.get("enable-cache") == retry.get("enable-cache") == "true", name
        # Match the whole condition: an event restriction would disable trusted/nightly retries.
        # Actions accepts either a bare expression or the equivalent expression wrapper.
        condition = retry["if"].strip().removeprefix("${{").removesuffix("}}").strip()
        assert re.fullmatch(r"steps\." + re.escape(first["id"]) + r"\.outcome\s*==\s*(['\"])failure\1",
                            condition), (name, condition)


@pytest.mark.platform
def test_1_new_repo_retries_uv_install_once(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    result = repo.forge("init", "--actions", "yes", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_retry(client)


@pytest.mark.platform
def test_2_sync_replaces_a_workflow_that_has_no_retry(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    result = repo.forge("init", "--actions", "yes", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    stale = (ROOT / "tests/fixtures/doctor-v1.2.2/.github/workflows/forge.yml").read_text("utf-8")
    assert stale.count("uses: astral-sh/setup-uv@") == 2
    assert "steps.setup-uv.outcome" not in stale
    (client / ".github/workflows/forge.yml").write_text(stale, "utf-8")
    repo.git("checkout", "-qb", "fix/retry-uv", cwd=client)
    repo.git("add", "-A", cwd=client)
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Keep a workflow with no retry",
             cwd=client)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    _assert_retry(client)
