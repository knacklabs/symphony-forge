"""A fix that changes a forge.toml setting keeps it through close when main moves the pin."""
import pytest

from test_close import GREEN, env  # noqa: F401
from test_codex_worker import MODELS, _toml
from test_upgrade_command import Upgrade, unsynced_up  # noqa: F401
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "fix-keeps-test-setting"


def test_1_close_keeps_the_fix_test_setting_after_main_moves_the_pin(env, unsynced_up):
    env.checks(GREEN)
    version = env.repo.forge("--version").stdout.split()[-1]
    base = _toml(version, "codex", MODELS, "client").replace(
        f'version = "{version}"', f'version = "{version}" # old pin')
    base = 'test = "echo ok"\nchecks = ["tests", "forge-pr-check"]\n' + base
    client, main = env.repo, unsynced_up
    main.on_main("forge.toml", base)
    started = client.forge("fix", "start", "Correct spelling", "--done", "Update forge.toml",
                           "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = client.path.parent / f"{client.path.name}-fix-correct-spelling"
    env.commit(folder, "forge.toml", base.replace('"echo ok"', '"echo fix"'), "Change the test command")
    main.on_main("forge.toml", base.replace(f'version = "{version}"', 'version = "v9.9.9"'))  # main moves the pin
    client.git("fetch", "-q", "origin", "main", cwd=folder)
    env.gh.respond("pr", "list", "--head", stdout=  # a behind pull request makes close merge main itself
                   '[{"number":7,"state":"OPEN","body":"","isDraft":false,"mergeStateStatus":"BEHIND"}]')
    closed = client.forge("close", "correct-spelling", cwd=folder)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert "nothing to review" not in closed.stdout
    text = (folder / "forge.toml").read_text("utf-8")
    assert 'test = "echo fix"' in text and 'version = "v9.9.9"' in text  # merged by close
    sent = env.review_calls()[-1]["args"]  # the review reads the branch against this base
    assert "echo fix" in client.git("diff", sent[sent.index("--base") + 1], "HEAD", "--", "forge.toml", cwd=folder)
    assert client.git("diff", "origin/main...HEAD", "--", "forge.toml", cwd=folder)


@pytest.mark.parametrize("client", [False], indirect=True, ids=["new"])
def test_2_close_refuses_when_the_merge_left_the_fix_no_change(env, client, tmp_path):
    env.checks(GREEN)
    version = client.forge("--version").stdout.split()[-1]
    base = 'test = "echo ok"\nchecks = ["tests", "forge-pr-check"]\n' + _toml(
        version, "codex", MODELS, "client")
    main = Upgrade(env, tmp_path)
    main.on_main("forge.toml", base)
    client.forge("fix", "start", "Correct spelling", "--done", "Update forge.toml", "--kind", "mechanical")
    folder = client.path.parent / f"{client.path.name}-fix-correct-spelling"
    env.commit(folder, "forge.toml", base.replace('"echo ok"', '"echo fix"'), "Change the test command")
    main.on_main("forge.toml", base.replace('"echo ok"', '"echo main"'))
    client.git("fetch", "-q", "origin", "main", cwd=folder)
    client.git("merge", "-q", "-X", "theirs", "-m", "Merge main", "origin/main", cwd=folder)  # takes main's value
    closed = client.forge("close", "correct-spelling")
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Ready:" not in closed.stdout
    assert "this fix has no change left" in closed.stderr
