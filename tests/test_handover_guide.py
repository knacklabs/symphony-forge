"""Init and sync deliver the hand-over guide."""
import shutil

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client, _version

STORY = "FORGE-HANDOVER-1"


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_3_the_guides_state_hand_over(repo, gh, tmp_path, setup):
    if setup == "new init":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), "utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Prepare the earlier client", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)

    started = repo.forge("fix", "start", "Check hand over guidance", "--done",
                         "The hand over guidance is delivered", "--kind", "mechanical",
                         cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-hand-over-guidance"
    if setup == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        changed = {line.split(None, 1)[1] for line in
                   repo.git("status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED

    sources = [ROOT / "docs/guide.md", ROOT / "src/forge/templates/skill.md"]
    guides = [client / host / "skills/forge/SKILL.md" for host in (".claude", ".codex")]
    assert not (client / "docs/handover.md").exists()
    sections = []
    for path in (*sources, *guides):
        text = " ".join(path.read_text("utf-8").split())
        # Audit: these are the handover instructions people receive. Missing a step can
        # leave work unpushed, unassigned, or unavailable on the next machine. Existing
        # guide tests cover other topics; real init and sync verify delivery without a seam.
        for instruction in (
            "## Hand over",
            "Push everything",
            "commit and push",
            "docs/handover.md",
            "forge assign <KEY or KEY/TASK> <login>",
            "Fixes cannot be reassigned",
            "Continue",
            "forge next",
            "forge work",
            "forge close",
            "forge merge",
            "checkout from GitHub",
        ):
            assert instruction.lower() in text.lower(), (path, instruction)
        sections.append(text.split("## Hand over ", 1)[1].split(" ## ", 1)[0])

    assert all(section == sections[0] for section in sections)

    for path in guides:
        text = " ".join(path.read_text("utf-8").split())
        assert "The file is local and never committed" not in text
