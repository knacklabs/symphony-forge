"""The company question ships to new apps without changing adopted app code."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_setup import _fresh_client


@pytest.mark.platform
@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_1_the_constitution_asks_one_or_many_companies_once(repo, gh, tmp_path, adoption):
    app_files = {
        "apps/web/src/features/home.tsx": b"export const home = new Date().toLocaleString();\n",
        "eslint.config.mjs": b"export default [{ rules: { 'our/rule': 'error' } }];\n",
    }
    if adoption == "new init":
        top, initialized = _fresh_client(repo, gh, tmp_path, "--starter")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        assert "APP_COMPANIES=many" in (top / ".env.example").read_text("utf-8").splitlines()
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        for rel, contents in app_files.items():
            path = repo.path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        _fixture_git(repo, tmp_path, "add", "-A")
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Prepare the earlier client")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
        started = repo.forge("fix", "start", "Sync the company guide", "--done",
                             "The company guide is current", "--kind", "mechanical")
        assert started.returncode == 0, started.stdout + started.stderr
        top = Path(re.search(r" in (.+)\n", started.stdout)[1])
        synced = repo.forge("sync", cwd=top)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        for rel, contents in app_files.items():
            assert (top / rel).read_bytes() == contents
        assert not (top / "libs/organisations").exists()
        assert not (top / ".env.example").exists()

    question = (
        'In an app whose .env.example has APP_COMPANIES, ask once: "Is the app for one company, '
        'or for many customer companies?" Write the answer under ## Defaults, set APP_COMPANIES '
        "to one or many in .env.example and in the host's settings, and ask it again only when "
        "the person wants to change it."
    )
    fixed_rule = (
        'When the answer is one company, also copy this line into ## Fixed rules: "- Built in: '
        "APP_COMPANIES=one makes a one-company app: corepack pnpm run setup:company "
        "(uv run --no-sync python -m app.setup_company in the Python starter) makes the company "
        'and its first admin, and people join only from an admin\'s invite."'
    )
    for host in (".claude", ".codex"):
        guide = (top / host / "skills/forge/SKILL.md").read_text("utf-8")
        constitution = guide.split("\n## App constitution\n")[1].split("\n## Adopt a live app\n")[0]
        # This is the prompt delivered by init/sync, before the post-prototype interview.
        first_half = " ".join(constitution.split("After the customer's sign-off", 1)[0].split())
        assert question in first_half
        assert fixed_rule in first_half
        assert constitution.count("Is the app for one company, or for many customer companies?") == 1
