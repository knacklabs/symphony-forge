"""The generated Actions contract retries uv installation once.

Test-audit gate: protect automatic recovery and a final failed install at the generated
workflow boundary, including replacement of an earlier release's existing workflow.
Omitting, relocating or restricting the retry, or allowing its error, breaks this contract.
Existing bootstrap tests only check tool presence. These command tests need no new seam.
"""
import re
import shutil

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
def test_2_earlier_adopted_repo_gets_uv_retry_on_sync(repo):
    shutil.copytree(ROOT / "tests/fixtures/doctor-v1.2.2", repo.path, dirs_exist_ok=True)
    workflow = repo.path / ".github/workflows/forge.yml"
    before = workflow.read_text("utf-8")
    assert before.count("uses: astral-sh/setup-uv@") == 2
    assert "steps.setup-uv.outcome" not in before
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt an earlier Forge release")
    repo.git("checkout", "-qb", "fix/retry-uv")
    config = (repo.path / "forge.toml").read_text("utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"'))
    result = repo.forge("sync")
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_retry(repo.path)
