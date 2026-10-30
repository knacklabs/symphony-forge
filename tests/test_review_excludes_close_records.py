"""Close's next review treats its recorded findings as Forge records, in every repo.

The asserted boundary is the review instructions, not the stub reviewer's verdict.
"""
import shutil
from pathlib import Path

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_review_leaves_out_forge_records import _outside

STORY = "FIX-REVIEW-SKIPS-FORGE-RECORDS"


@pytest.mark.parametrize("client", ["forge", "new", "upgraded"])
def test_1_next_review_excludes_close_records_from_the_parts_scope(env, client):
    repo = env.repo
    if client == "upgraded":
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text("utf-8")
        config = config.replace('version = "v1.2.2"', f'version = "{version}"')
    else:
        config = (repo.path / "forge.toml").read_text("utf-8")
        config += f'repo = "{"forge-source" if client == "forge" else "client"}"\n'
    env.commit(repo.path, "forge.toml", config, "Use the installed Forge")
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_task()
    # The shared list still exists in repositories adopted before per-item records.
    env.commit(where, "plans/spotted.json", '{"items": []}\n')
    env.commit(where, "plans/SHOP.read.md", "# Read notes\n")
    env.reviews(blocked(finding("P1", "Saving loses the basket")), CLEAN)
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    record = "plans/spotted/SHOP.T1.json"
    assert record in repo.git("show", "--pretty=", "--name-only", "HEAD", cwd=where)
    assert "Saving loses the basket" in (where / record).read_text("utf-8")

    env.commit(where, "app.py", "print('basket saved')\n", "Keep the basket")
    second = env.close(item)
    assert second.returncode == 0, second.stdout + second.stderr
    assert len(env.review_calls()) == 2
    prompt = " ".join(env.prompt().split())
    # Prompt-byte contract: these records cannot be judged as unrelated worker edits,
    # even when they appear in the helper's raw Git diff on the second round.
    assert ("The spotted lists (`plans/spotted.json` and everything under `plans/spotted/`) "
            "are also Forge's own records. Close writes them on this branch after a review; "
            "never report those writes as files outside Scope or as unrelated changes.") in prompt
    outside = _outside(env.prompt())
    assert "- other.py" in outside, "product changes still receive scope review"
    for path in (record, "plans/spotted.json", "plans/SHOP.read.md", ".factory/"):
        assert path not in outside
