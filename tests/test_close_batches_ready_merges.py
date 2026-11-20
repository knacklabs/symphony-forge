"""Close groups Ready fixes. Next-only coverage cannot detect this output bug.

Test audit: Old close prints separate merge advice. Real close creates readiness,
only external services use fakes, and no production seam is needed.
"""
import json

from test_close import env  # noqa: F401
from test_machine_views import github, pull

STORY = "close-suggests-land"


def test_1_close_names_this_fix_and_other_ready_fixes(env):
    repo = env.repo
    config = repo.path / "forge.toml"
    env.commit(repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    repo.git("push", "-q", "origin", "main")
    first, folder = env.start_fix()
    closed = env.close(first)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Next: forge merge {first}" in closed.stdout.splitlines()
    pr = pull(7, f"fix/{first}")
    pr["headRefOid"] = repo.git("rev-parse", "HEAD", cwd=folder)
    github(env.gh, [pr])
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([pr]))
    second, _ = env.start("footer", "fix/footer", ".factory/fixes/footer.json",
                          {"kind": "fix", "why": "Repair the footer", "done_when": "The footer works"},
                          {"footer.py": "print('footer')\n"})
    closed = env.close(second)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Next: forge land {second} {first}" in closed.stdout.splitlines(), closed.stdout
    assert not env.gh_calls("pr", "merge")
