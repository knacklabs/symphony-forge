"""Next ignores dropped fixes after the owner removes their retained checkout.

Existing drop tests retain local data or let drop remove the folder itself.
This command-level lifecycle regression needs no production seam. Only GitHub
is faked at its edge.
"""
import re
import shutil

from test_fix_drop import _github, _start
from test_started_branches_claim_the_work import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "dropped-fix-next-crash"


def test_1_next_skips_a_dropped_fix_whose_checkout_is_gone(client):
    where = _start(client)
    _github(client)
    (where / ".gitignore").write_text("local-data/\n", "utf-8")
    client.git("add", ".gitignore", cwd=where)
    client.git("commit", "-qm", "Keep local data", cwd=where)
    (where / "local-data").mkdir()
    (where / "local-data" / "notes.txt").write_text("Owner data\n", "utf-8")
    dropped = client.forge("fix", "drop", "unwanted", "--because", "No longer needed")
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    assert where.exists()
    shutil.rmtree(where)
    shown = client.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "Traceback" not in shown.stderr
    assert "unwanted" not in shown.stdout
    active = _start(client, "active-greeting")
    config = active / "forge.toml"
    text = re.sub(r'^workers\s*=.*\n', '', config.read_text("utf-8"), flags=re.M)
    config.write_text('workers = "claude"\n' + text, "utf-8")
    client.git("add", "forge.toml", cwd=active)
    client.git("commit", "-qm", "Use the test worker", cwd=active)
    log = install_claude(client)
    worked = client.forge("work", "active-greeting")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = calls(log)[-1]["brief"]
    assert "Do not run `forge next`" in brief
    assert "do not ask which failure or finding to fix" in brief
