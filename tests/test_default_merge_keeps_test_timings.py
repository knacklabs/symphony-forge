"""Default merges preserve parallel timing updates without a repair round.

Audit: real close/work commands and Git merges own this contract. Existing
conflict tests have no timing-file collision. Removing automatic resolution
fails the union assertion; no production test seam is needed.
"""
import json

import pytest

from test_close import env  # noqa: F401
from test_upgrade_command import Upgrade
from test_worker import calls, install_claude
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "merge-test-timings-union"


@pytest.mark.parametrize("client, command, other", [
    (False, "close", False), (False, "work", False),
    (False, "close", True), (False, "work", True),
    (True, "close", False),
], indirect=["client"])
def test_1_default_merge_resolves_only_test_timings(env, client, command, other):
    setup = Upgrade(env, env.tmp)
    setup.on_main(".test_durations", json.dumps({"shared": 1}))
    setup.on_main("app.py", "base\n")
    item, folder = env.start_fix({
        ".test_durations": json.dumps({"shared": 2, "worker": 3}),
        "app.py": "worker\n",
    })
    before = client.git("rev-parse", "HEAD", cwd=folder)
    setup.on_main(".test_durations", json.dumps({"shared": 4, "default": 5}))
    if other:
        setup.on_main("app.py", "default\n")
    incoming = client.git("rev-parse", "main")
    if command == "work":
        log = install_claude(client)
    result = client.forge(command, item)
    output = result.stdout + result.stderr
    if other:
        if command == "close":
            assert result.returncode == 1, output
            assert "conflicts in .test_durations, app.py" in output
            assert client.git("rev-parse", "HEAD", cwd=folder) == before
        else:
            assert "First, finish the merge of origin/main" in calls(log)[-1]["brief"]
        assert (folder / ".test_durations").read_text("utf-8") == json.dumps({"shared": 2, "worker": 3})
    else:
        assert result.returncode == 0, output
        assert "First, finish the merge" not in output
        if command == "work":
            assert "First, finish the merge" not in calls(log)[-1]["brief"]
        expected = {"default": 5, "shared": 4, "worker": 3}
        assert (folder / ".test_durations").read_text("utf-8") == json.dumps(expected, indent=4, sort_keys=True) + "\n"
        client.git("merge-base", "--is-ancestor", incoming, "HEAD", cwd=folder)
        client.git("merge-base", "--is-ancestor", before, "HEAD", cwd=folder)
    assert client.git("diff", "--name-only", "--diff-filter=U", cwd=folder) == ""
