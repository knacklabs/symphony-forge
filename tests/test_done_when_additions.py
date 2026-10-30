"""Amend adds to or replaces Done-when and shows the change before it writes."""
from pathlib import Path
import os
import subprocess
import sys

from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "amend-append"


def test_1_amend_preserves_done_when_on_append_and_previews_both_changes(client):
    # Previously --append was unavailable and --done silently replaced the old text.
    log = install_claude(client)
    old = "The readme opens with a greeting"
    extra = "The install steps follow the greeting"
    started = client.forge("fix", "start", "Greet readers", "--done", old,
                           "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    for option, text, expected in (("--append", extra, f"{old} {extra}"),
                                   ("--done", "Readers see the install steps",
                                    "Readers see the install steps")):
        before = client.git("rev-parse", "HEAD", cwd=folder)
        # A closed output pipe makes the preview fail. No write can precede it,
        # including an uncommitted record write. Close the reader before launch.
        reader, writer = os.pipe()
        os.close(reader)
        with os.fdopen(writer, "wb") as output:
            interrupted = subprocess.run(
                [sys.executable, str(client.bin / "forge"), "fix", "amend", "greet-readers",
                 option, text, "--because", "The owner clarified the result"],
                cwd=client.path, stdout=output, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", timeout=60)
        assert interrupted.returncode != 0, interrupted.stderr
        assert client.git("rev-parse", "HEAD", cwd=folder) == before
        assert client.git("status", "--porcelain", cwd=folder) == ""
        amended = client.forge("fix", "amend", "greet-readers", option, text,
                               "--because", "The owner clarified the result")
        assert amended.returncode == 0, amended.stdout + amended.stderr
        assert f"Old Done-when:\n{old}\nNew Done-when:\n{expected}\n" in amended.stdout
        assert amended.stdout.index("New Done-when:") < amended.stdout.index(
            "Fix greet-readers is now done when:")
        # The next amendment's old text proves the previous change was stored.
        old = expected
    # Start one worker after both changes; resumed briefs do not repeat Done-when.
    worked = client.forge("work", "greet-readers")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert f"Done when: {old}\n" in calls(log)[-1]["brief"]
    for host in (".codex", ".claude"):
        guide = (folder / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert 'forge fix amend <fix> --append "<text>" --because "<why>"' in guide
    before = client.git("rev-parse", "HEAD", cwd=folder)
    for options in ((), ("--done", "Replace", "--append", "Add")):
        refused = client.forge("fix", "amend", "greet-readers", *options,
                               "--because", "The owner clarified the result")
        assert refused.returncode == 1
        assert "Use either --done to replace the Done-when or --append to add to it." in refused.stderr
        assert "Next: forge fix amend greet-readers --append" in refused.stderr
        assert client.git("rev-parse", "HEAD", cwd=folder) == before
    for options in (("--append", " ", "--because", "Clarify"),
                    ("--append", "First\nSecond", "--because", "Clarify"),
                    ("--append", extra, "--because", " ")):
        refused = client.forge("fix", "amend", "greet-readers", *options)
        assert refused.returncode == 1
        assert "A new done-when needs one line of text and a one-line reason." in refused.stderr
        assert client.git("rev-parse", "HEAD", cwd=folder) == before
