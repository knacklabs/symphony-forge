"""Clients receive general test rules; Forge has no special hook exemption."""
import os
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_doctor_fix import HOOKS_FIXED, HOOKS_ROW, _commit_refused
from test_setup import _fresh_client, _version
from test_worker import calls, install_claude

STORY = "client-workers-and-reviews-receive-forge"


@pytest.mark.parametrize("setup", ["new", "previous-release adoption"])
def test_1_sync_and_worker_briefs_carry_only_general_rules(repo, gh, tmp_path, monkeypatch, setup):
    log = install_claude(repo)
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "1")
    if setup == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        started = repo.forge("fix", "start", "Check general rules", "--done",
                             "Workers receive general rules", cwd=client)
        assert started.returncode == 0, started.stdout + started.stderr
        client = tmp_path / "client-fix-check-general-rules"
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path,
                              capture_output=True, text=True)
        client = repo.path.parent / "repo-fix-adopt-forge"
    assert made.returncode == 0, made.stdout + made.stderr
    config = client / "forge.toml"
    text = config.read_text(encoding="utf-8")
    if setup != "new":
        # A real old adoption carries Forge's principles before the release is upgraded.
        assert "## Forge's 13 principles" in (
            client / ".codex/skills/forge/standards.md").read_text(encoding="utf-8")
        text = text.replace('version = "v1.2.2"', f'version = "{_version(repo)}"')
    text = text.replace('workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"')
    config.write_text(text, encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert config.read_text(encoding="utf-8") == text

    built = repo.forge("work", "check-general-rules" if setup == "new" else "adopt-forge",
                       cwd=client)
    assert built.returncode == 0, built.stdout + built.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert "A test that fails in the suite but passes alone is flaky; its failure stays unresolved" in brief
    for host in (".claude", ".codex"):
        standards = " ".join((client / host / "skills/forge/standards.md").read_text(
            encoding="utf-8").split())
        for phrase in (
            "Tests own and clean up every process they start, even after a crash",
            "Isolate host-side configuration",
            "Only setup and cleanup file operations retry briefly on Windows file locks",
            "persistent failures still fail",
            "never retry assertions or whole tests",
        ):
            assert phrase in standards, phrase
            assert phrase in brief, phrase
        for forbidden in ("Forge's 13 principles", "FORGE_LIVE_CODEX", "codex-smoke",
                          "machine load from parallel workers", "forge-source",
                          "no module over 1,200 lines", "fixed ceiling on `forge` commands"):
            assert forbidden not in standards
            assert forbidden not in brief


def test_2_doctor_checks_and_repairs_forge_source_hooks_without_an_exemption(repo, gh):
    repo.write("forge.toml", f'version = "{_version(repo)}"\nrepo = "forge-source"\n'
                             'workers = "claude"\ntest = "true"\nchecks = ["tests"]\n')
    assert not _commit_refused(repo)
    checked = repo.forge("doctor")
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert HOOKS_ROW in checked.stdout
    repaired = repo.forge("doctor", "--fix")
    assert HOOKS_FIXED in repaired.stdout, repaired.stdout + repaired.stderr
    assert HOOKS_ROW not in repo.forge("doctor").stdout
    assert _commit_refused(repo)


def test_3_failed_git_commits_report_the_actual_reason(repo, tmp_path):
    # The Ubuntu functional-check failure only showed Git's exit code. Exercise a real failed
    # commit, so pytest must print the captured diagnostic without retrying or hiding failure.
    (repo.path / ".git/index.lock").write_text("held\n", encoding="utf-8")
    probe = tmp_path / "test_failed_commit.py"
    probe.write_text(
        "from pathlib import Path\nfrom conftest import Repo\n\n"
        "def test_failed_commit():\n"
        f"    repo = Repo(Path({str(repo.path)!r}), Path({str(repo.bin)!r}))\n"
        "    repo.git('commit', '--allow-empty', '-m', 'Record a walkthrough')\n",
        encoding="utf-8")
    failed = subprocess.run([sys.executable, "-m", "pytest", str(probe), "-q", "--tb=short",
                             "-p", "no:cacheprovider"], capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": str(ROOT / "tests")})
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "index.lock" in failed.stdout, failed.stdout
    assert "File exists" in failed.stdout, failed.stdout
