"""Release pushes reuse full proof only across Forge-owned changes.

Audit: real tag pushes protect reuse and product-change refusal. The old gate
rejects a version-only commit; existing release tests cover only same-head proof.
Only GitHub statuses are fake, and no production seam is needed.
"""
from types import SimpleNamespace

import pytest

from test_githooks import hooked, push
from test_testplace_fullrun import _set_status
from test_testplace_upgrade import prepare_adopted_client

STORY = "release-tag-reuses-full-run"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new-repo", "earlier-adopted"])
def test_1_release_reuses_full_run_until_product_changes(repo, gh, adopted):
    if adopted:
        prepare_adopted_client(SimpleNamespace(repo=repo), [])
    else:
        hooked(repo)
    base = repo.git("rev-parse", "HEAD")
    _set_status(gh, base, "success")
    settings = (repo.path / "forge.toml").read_text("utf-8")
    version_line = next(line for line in settings.splitlines() if line.startswith("version ="))
    repo.write("forge.toml", settings.replace(version_line, 'version = "v1.2.2"'))

    def publish(message):
        repo.git("add", "-A")
        # Model a reviewed merge on GitHub, outside the local commit/push hooks.
        repo.git("-c", "core.hooksPath=absent-hooks", "commit", "-qm", message)
        repo.git("-c", "core.hooksPath=absent-hooks", "push", "-q", "origin", "main")
        head = repo.git("rev-parse", "HEAD")
        _set_status(gh, head, None)
        return head

    head = publish("Change only the Forge version")
    repo.git("tag", "-a", "v2.0.0", "-m", "Release", head)
    accepted = push(repo.path, "refs/tags/v2.0.0")
    assert accepted.returncode == 0, accepted.stderr

    repo.git("tag", "-a", "v2.0.1", "-m", "Old head", base)
    stale = push(repo.path, "refs/tags/v2.0.1")
    assert stale.returncode != 0
    assert "must point to the latest commit on main" in stale.stderr

    repo.write("app.py", "print('product change')\n")
    head = publish("Change the product")
    repo.git("tag", "v2.0.2", head)
    refused = push(repo.path, "refs/tags/v2.0.2")
    assert refused.returncode != 0
    assert "has no green full test run" in refused.stderr
