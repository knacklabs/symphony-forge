"""Fresh and previously adopted clients' guides describe only the live board page."""
from test_board_guide import _synced_guides

STORY = "FORGE-BOARD-4"


def test_10_synced_guides_describe_only_the_live_board_page(repo):
    # The old static page is gone. A guide that still describes it sends the coordinator
    # looking for sections, folds and a dependency picture the board no longer has.
    repo.git("checkout", "-q", "-b", "fix/live-board-guide")
    for adopted, host, skill in _synced_guides(repo):
        text = " ".join(skill.split())
        for live in ("127.0.0.1", "token", "refreshes by itself", "`--out <path>` writes"):
            assert live in text, (adopted, host, live)
        for old in ("HTML board", "HTML page", "static page", "720px", "dependency graph"):
            assert old not in text, (adopted, host, old)
