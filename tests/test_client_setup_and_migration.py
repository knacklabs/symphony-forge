"""Clients receive setup, migration and advisory PR-size guidance at init or sync."""
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version

STORY = "FIX-CLIENT-SETUP-AND-MIGRATION"


@pytest.mark.parametrize("case", ["new", "adopt", "previous adoption"])
def test_1_init_and_sync_ship_setup_migration_and_advisory_pr_size(repo, gh, tmp_path, case):
    if case == "new":
        client, done = _fresh_client(repo, gh, tmp_path)
    elif case == "adopt":
        done = repo.forge("init", "--test", "true", "--checks", "tests",
                          "--interfaces", "**/routes/**", "--approver", "Owner",
                          "--merger", "Owner")
        client = next(Path(line.removeprefix("worktree ")) for line in
                      repo.git("worktree", "list", "--porcelain").splitlines()
                      if line.startswith("worktree ") and line != f"worktree {repo.path}")
    else:
        # Real v1.2.2 adoption output, built from plain text, then upgraded and synced.
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/setup")
        config = (repo.path / "forge.toml").read_text(encoding="utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        client, done = repo.path, repo.forge("sync")
    assert done.returncode == 0, done.stdout + done.stderr

    for host in (".claude", ".codex"):
        folder = client / host / "skills/forge"
        skill = (folder / "SKILL.md").read_text(encoding="utf-8")
        setup = skill.split("## Laptop setup and after cloning\n", 1)[1].split("\n## ", 1)[0]
        assert "forge.toml" in setup and "pinned" in setup
        assert "uv tool install git+https://github.com/knacklabs/symphony-forge@<release>" in setup
        assert setup.index("forge sync") < setup.index("forge doctor --fix")
        for installer in ("install-mac.sh", "install-windows.ps1"):
            assert f"https://raw.githubusercontent.com/knacklabs/symphony-forge/main/scripts/{installer}" in setup
        assert "before running `forge migrate" in skill
        assert "[migration playbook](migrate-skill.md)" in skill
        guide = (folder / "migrate-skill.md").read_text(encoding="utf-8")
        for instruction in ("forge migrate --dry-run", "Go on only after a yes",
                            "Review it independently", "Audit leftovers after the merge"):
            assert instruction in guide

    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    step = workflow.split("      - name: Report pull request size\n", 1)[1]
    assert "continue-on-error: true" in step and "if: always()" in step
    assert "BASE_SHA: ${{ github.event.pull_request.base.sha }}" in step
    assert "HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in step
    script = re.search(r"        run: \|\n((?:          .*\n)+)", step)[1]
    script = "\n".join(line[10:] for line in script.splitlines())
    if os.name != "nt":
        # Execute the shipped step against actual commits; no fake supplies the totals.
        repo.git("init", "-q", str(tmp_path / "diff"))
        diff = tmp_path / "diff"
        file = diff / "lines.txt"
        file.write_text("keep\nremove\n", encoding="utf-8")
        repo.git("add", ".", cwd=diff)
        repo.git("commit", "-qm", "Before", cwd=diff)
        base = repo.git("rev-parse", "HEAD", cwd=diff)
        file.write_text("keep\nadd one\nadd two\n", encoding="utf-8")
        repo.git("add", ".", cwd=diff)
        repo.git("commit", "-qm", "After", cwd=diff)
        summary = tmp_path / "summary"
        result = subprocess.run(["bash", "-c", script], cwd=diff, capture_output=True,
                                text=True, env={**os.environ, "BASE_SHA": base,
                                "HEAD_SHA": "HEAD", "GITHUB_STEP_SUMMARY": str(summary)})
        assert result.returncode == 0, result.stderr
        assert "Net lines: +1 (2 added, 1 removed)" in summary.read_text(encoding="utf-8")

    if case == "new":
        # The guide must survive packaging, not just exist in an editable checkout.
        dist = tmp_path / "dist"
        subprocess.run(["uv", "build", "--wheel", "--out-dir", str(dist), str(ROOT)],
                       check=True, capture_output=True, text=True)
        with zipfile.ZipFile(next(dist.glob("*.whl"))) as wheel:
            packaged = wheel.read("forge/templates/migrate-skill.md").decode("utf-8")
        assert packaged == guide
