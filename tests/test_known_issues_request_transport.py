"""The board's historical GitHub request survives a Windows batch launcher.

Audit: existing known-issues tests own the issue list and once-only reads. This
test owns the transport risk that POSIX execution cannot expose: Python's
Windows argument quoting leaves an ampersand outside quotes when an argument
has no spaces. Observe the real board's external request, without replacing
production code or deciding the board result in a fake.
"""
import json
import re
import subprocess
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from test_board_after_upgrade import NOW
from test_board_counts import board
from test_close import env  # noqa: F401
from test_known_issues import kept_history  # noqa: F401
from test_upgrade_command import unsynced_up  # noqa: F401

import pytest

STORY = "FIX-KNOWN-ISSUES-TRANSPORT"


@pytest.mark.platform
def test_1_board_history_request_survives_windows_batch_launchers(kept_history, monkeypatch):
    repo, _, item = kept_history
    github = repo.bin / "gh"
    github.write_text(github.read_text("utf-8").replace(
        'args = sys.argv[1:]', '''args = sys.argv[1:]
with open(pathlib.Path(__file__).parent / "transport-calls.jsonl", "a", encoding="utf-8") as calls:
    calls.write(json.dumps(args) + "\\n")''', 1), "utf-8")

    # Upgrade fills the daily history cache before request recording starts.
    # Leave a gap beyond weekly coverage so both new and adopted repos must
    # rebuild the complete inventory through the external request transport.
    monkeypatch.setenv("FORGE_NOW", (NOW + timedelta(days=50)).isoformat())
    issues = board(repo)["known_issues"]
    assert any(row["item"] == item for row in issues), issues
    calls = [json.loads(line) for line in
             (repo.bin / "transport-calls.jsonl").read_text("utf-8").splitlines()]
    requests = [call for call in calls if call[:1] == ["api"]
                and any("/pulls?" in arg for arg in call)]
    assert requests, calls
    pages = []
    for call in requests:
        endpoint = next(arg for arg in call if "/pulls?" in arg)
        fields = [call[n + 1] for n, arg in enumerate(call) if arg == "--raw-field"]
        query = parse_qs(urlsplit(endpoint).query)
        query.update({key: [value] for key, value in (field.split("=", 1) for field in fields)})
        pages.append((query.get("per_page", [""])[0], query.pop("page", ["1"])[0]))
        assert query.pop("per_page", None) in (["1"], ["100"]), call
        assert query == {"state": ["closed"]}, call
        assert (call[call.index("--method") + 1] if "--method" in call
                else "POST" if fields else "GET") == "GET", call
        # .cmd launchers interpret unquoted shell operators even with shell=False.
        unquoted = re.sub(r'"[^"]*"', "", subprocess.list2cmdline(call))
        assert not re.search(r"[&|<>]", unquoted), unquoted
    # The kept evidence is on page two: a parallel inventory must preserve the
    # complete history and keep pagination fields out of Windows shell syntax.
    assert pages[0] == ("1", "1"), pages
    assert sorted(pages[1:]) == [("100", "1"), ("100", "2")], pages
