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
    assert "5. Score the release." in section and section.index("5. Score the release.") > section.index("forge --version")
    exact = (
        # The policy lines: Claude only, nothing else starts it, no pull request, no hold, a failed build scores.
        "Nothing else starts this, a pull request never does, and it never holds the release. Use Claude only",
        "A failed build still gets a score",
        # The scratch folder is a git checkout with an origin remote, which forge init needs.
        "git init -b main app", "git init --bare -b main origin.git", "git -C app remote add origin ../origin.git",
        # The release's own Forge, and the one scorer command with every option it requires.
        "uvx --from git+https://github.com/knacklabs/symphony-forge@vX.Y.Z forge init --starter react --actions no",
        "uv run --frozen --python 3.11 python scripts/bench_score.py <scratch app> --checks benchmark/checks.toml"
        " --release vX.Y.Z --results benchmark/results",
        # The subagent: its task, its boundary, and what it must not do.
        "general-purpose", "not the `worker`", "benchmark/notes.md", "no person is here",
        "to build the reference app described in the notes", "only in the scratch folder",
        "starts in your working directory", "no stories", "no fixes", "does not commit", "AGENTS.md", "skills",
        # Limits, the fix that holds the score, the compose project, and the builder's model.
        "120 minutes", "Start the fix before you write the score", "worktree", "normal fix",
        "forge-bench-", "BENCH_PROJECT", "`ports`", "`setup`", "down --volumes", "[models.build.claude]",
        # The usage file: all four keys, null for an unknown value.
        "`input_tokens`", "`output_tokens`", "`turns`", "`minutes`", "`null`",
        # What to report with no comparable earlier score.
        "No earlier score to compare with", "first score", "This is a new baseline", "no direction",
    )
    for phrase in exact:
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
