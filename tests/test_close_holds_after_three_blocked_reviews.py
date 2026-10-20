"""Close keeps both review-loop holds and their owner choices after init or upgrade."""
STORY = "any-file-hold"

import shutil
from pathlib import Path

from test_close import GREEN, STORY_DOC, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client as review_client
from test_setup import _fresh_client
from test_upgrade_command import Upgrade


QUESTION_RULE = ("When a cold read or review loop stops and you must ask, ask the human the question it printed, "
                 "in its words, one item per question.")
PATHS = ["docs/product/BRIEF.md", "docs/specs/README.md", "docs/product/settings.md"]


def client_item(env, tmp_path, previous, stop_default=False, part=False):
    if part:
        review_client(env, previous)
        if stop_default:
            config = (env.repo.path / "forge.toml").read_text("utf-8")
            Upgrade(env, tmp_path).on_main("forge.toml", 'stop_default = "off"\n' + config)
        item, where = env.start_approved_task(STORY_DOC)
        env.checks(GREEN)
        return item, where
    if previous:
        # Land the earlier release's plain-text adoption fixture before it installs git hooks.
        for path in PATHS[:-1]:
            env.repo.write(path, "# Existing client document\n")
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        env.repo.path, dirs_exist_ok=True)
        env.repo.git("add", "-A")
        env.repo.git("commit", "-q", "-m", "Client adopted on an earlier release")
        env.repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        env.repo.path = client
    if stop_default:
        # Product fixes now keep default settings, so coordinator setup belongs on main.
        config = (env.repo.path / "forge.toml").read_text("utf-8")
        Upgrade(env, tmp_path).on_main("forge.toml", 'stop_default = "off"\n' + config)
    item, where = env.start_fix()
    if previous:
        version = env.repo.forge("--version").stdout.split()[-1]
        config = (where / "forge.toml").read_text("utf-8")
        env.commit(where, "forge.toml", config.replace('version = "v1.2.2"',
                                                       f'version = "{version}"'))
        synced = env.repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stderr
        env.commit(where, "app.py", "print('upgraded client')\n")
    # Init's branch-protection responses must not stand in for the actual CI responses.
    env.checks(GREEN)
    return item, where
