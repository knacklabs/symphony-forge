"""Closing works when a Git launcher consumes unquoted Windows caret escapes."""
import json
import shutil
import sys

import pytest

from conftest import _install
from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

pytestmark = pytest.mark.platform

STORY = "FIX-WINDOWS-TEST-FIXES"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_resolves_commits_through_a_git_batch_launcher(env, previous):
    client(env, previous)
    item, _ = env.start_fix()
    real_git = shutil.which("git")
    # On Windows _install creates the real .cmd launcher. Elsewhere reproduce only
    # its caret forwarding and command limit, leaving Git to judge the real paths.
    # Gate: close must work with the complete client skill bundle behind a batch launcher.
    # A per-file exclusion list exceeds cmd.exe's 8,191-character limit. Windows already
    # catches it; reproduce that transport limit here so other platforms catch it too.
    # This extends the existing boundary owner and adds no production seam.
    _install(env.repo.bin, "git", f'''#!{sys.executable}
import os, subprocess, sys
args = sys.argv[1:]
if args[:1] in (["diff"], ["log"]) and len(subprocess.list2cmdline(["git", *args])) > 8191:
    sys.stderr.write("The command line is too long.\\n")
    sys.exit(1)
if os.name != "nt":
    args = [arg.replace("^", "") for arg in args]
sys.exit(subprocess.call([{json.dumps(real_git)}, *args]))
''')

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Ready: {item} has a clean review and green checks." in closed.stdout
