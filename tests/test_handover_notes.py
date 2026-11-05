"""Fresh sessions read committed decisions, rather than work-branch notes."""
import shutil

import pytest

from conftest import ROOT

STORY = "FORGE-HANDOVER-1"


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new repo", "earlier adopted"])
def test_2_a_new_clone_shows_the_committed_notes(repo, tmp_path, setup):
    # Audit: context owns session delivery. Scratch-hook coverage cannot catch
    # lost committed notes in a clone or work-branch notes leaking into context.
    # The real command needs no production seam or output-deciding fake.
    if setup == "earlier adopted":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        repo.write("forge.toml", 'repo = "client"\n')
        repo.write("docs/handover.md", "# Hand over\n\n## Current state\nDo not show this.\n\n"
                   "## Decisions and lessons\n- Keep the client wording.\n\n"
                   "## Other notes\nDo not show this either.\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Save client notes")
    repo.git("push", "-q", "origin", "main")
    clone = tmp_path / "new machine"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(clone))
    repo.git("checkout", "-q", "-b", "fix/local", cwd=clone)
    (clone / "docs").mkdir(exist_ok=True)
    (clone / "docs/handover.md").write_text(
        "## Decisions and lessons\n- Local branch only.\n", encoding="utf-8")
    before = repo.forge("next", cwd=clone)
    context = repo.forge("hook", "context", cwd=clone)
    assert before.returncode == context.returncode == 0, context.stdout + context.stderr
    assert before.stdout.strip() in context.stdout
    assert "Local branch only" not in context.stdout
    if setup == "new repo":
        assert context.stdout.endswith("## Decisions and lessons\n- Keep the client wording.\n")
        assert context.stdout.index("## Decisions and lessons") > context.stdout.index(before.stdout.strip())
        assert "Do not show this" not in context.stdout
    else:
        assert context.stdout == before.stdout
