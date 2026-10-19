"""Fresh and previously adopted clients receive the board guidance."""
import shutil

from conftest import ROOT

STORY = "FORGE-BOARD-2"


def _synced_guides(repo):
    """Yields (adopted, host, guide) for a new repo and one adopted on an earlier release."""
    installed = repo.forge("--version").stdout.split()[-1]
    for adopted in (False, True):
        if adopted:
            shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                            dirs_exist_ok=True)
            settings = (repo.path / "forge.toml").read_text("utf-8")
            repo.write("forge.toml", settings.replace('version = "v1.2.2"',
                                                     f'version = "{installed}"'))
        else:
            repo.write("forge.toml", f'version = "{installed}"\nmerge = "human"\n'
                       'test = "echo passed"\n')
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        for host in (".claude", ".codex"):
            yield adopted, host, (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")


def test_14_synced_guides_explain_upgrade_time_backfill(repo):
    # The installed prompt is the public contract. A stale or incomplete upgrade
    # paragraph leaves the coordinator unaware of retries and the board check.
    repo.git("checkout", "-q", "-b", "fix/upgrade-board-guide")
    for adopted, host, skill in _synced_guides(repo):
        upgrade = " ".join(skill.split("## Upgrade Forge\n", 1)[1].split("\n## ", 1)[0].split())
        for instruction in ("backfill", "as part of the upgrade", "next close",
                            "opens the board", "reports what is still missing"):
            assert instruction in upgrade, (adopted, host, instruction)
        assert "nothing extra to type" in upgrade
        assert "Both views add `team`" in skill
        assert "stage_counts" not in skill


def test_1_synced_guides_describe_only_the_live_board_page(repo):
    # The old static page is gone. A guide that still describes it sends the coordinator
    # looking for sections, folds and a dependency picture the board no longer has.
    repo.git("checkout", "-q", "-b", "fix/live-board-guide")
    for adopted, host, skill in _synced_guides(repo):
        text = " ".join(skill.split())
        for live in ("127.0.0.1", "token", "refreshes by itself", "`--out <path>` writes"):
            assert live in text, (adopted, host, live)
        for old in ("HTML board", "HTML page", "static page", "720px", "dependency graph"):
            assert old not in text, (adopted, host, old)
