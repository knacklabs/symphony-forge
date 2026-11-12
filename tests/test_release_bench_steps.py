"""The maintainer guide's steps for scoring a release, and clients getting nothing from them."""
import shutil
from pathlib import Path

import pytest

from test_setup import _fresh_client

ROOT = Path(__file__).resolve().parents[1]
STORY = "FORGE-BENCH-1"


def _files(root):
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git/" not in p.as_posix()}


def _bench_paths(files):
    return [f for f in files if f.startswith(("benchmark/", "scripts/bench"))]


def test_1_the_guide_carries_the_steps_to_score_a_release_in_claude_code():
    guide = (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    section = " ".join(guide.split("## Releasing Forge", 1)[1].split("\n## ", 1)[0].split())
    assert "5." in section and section.index("5.") > section.index("forge --version")
    for phrase in ("scratch folder", "outside the Forge repo", "uvx --from git+", "forge init",
                   "general-purpose", "not the `worker`", "benchmark/notes.md", "no person is here",
                   "no stories", "no fixes", "does not commit", "AGENTS.md", "skills",
                   "Start the fix before you write the score", "worktree", "120 minutes", "stop",
                   "forge-bench-", "BENCH_PROJECT", "`ports`", "`setup`", "down --volumes",
                   "uv run --frozen --python 3.11 python scripts/bench_score.py",
                   "--results benchmark/results", "normal fix", "[models.build.claude]"):
        assert phrase in section, phrase
    assert "fable" not in section.lower().replace("no model whose id contains `fable`", "")
    assert "astra" not in section.lower().replace("or `astra`", "")


@pytest.mark.platform
def test_5_a_new_and_an_existing_client_repo_get_no_benchmark_files(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react", "--actions", "no")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.git("checkout", "-q", "-b", "fix/new-client", cwd=client)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert _bench_paths(_files(client)) == []

    repo.git("checkout", "-q", "-b", "fix/adopted-client")
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    installed = repo.forge("--version").stdout.split()[-1]
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", settings.replace('version = "v1.2.2"', f'version = "{installed}"'))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert _bench_paths(_files(repo.path)) == []
