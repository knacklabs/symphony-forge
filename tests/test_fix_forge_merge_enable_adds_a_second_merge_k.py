"""forge merge enable changes the merge key however forge.toml writes it, and adds one only when absent."""
from __future__ import annotations

import tomllib

import pytest

from test_close import env  # noqa: F401
from test_merge_enable import BRANCH, READY, enable, owner, raw, set_main, worktree  # noqa: F401

STORY = "forge-merge-enable-adds-a-second-merge-k"
# How forge.toml may write the setting, and the line enable leaves in its place.
FORMS = {
    "indented": ('  merge = "human"\n', '  merge = "agent"\n'),
    "double-quoted key": ('"merge" = "human"\n', '"merge" = "agent"\n'),
    "single-quoted": ("'merge' = 'human'\n", "'merge' = \"agent\"\n"),
    "comment": ('merge = "human"  # the owner merges\n', 'merge = "agent"  # the owner merges\n'),
}


@pytest.mark.parametrize("form", FORMS)
def test_1_enable_changes_an_existing_merge_key_however_it_is_written(owner, form):
    line, changed = FORMS[form]
    set_main(owner, line + (owner.repo.path / "forge.toml").read_text("utf-8"))
    before = raw(owner, "origin/main")

    switched = enable(owner)

    assert switched.returncode == 0, switched.stdout + switched.stderr
    assert switched.stdout.splitlines()[-2:] == READY
    after = raw(owner, f"origin/{BRANCH}")
    assert after == before.replace(line.encode(), changed.encode(), 1)
    assert tomllib.loads(after.decode()) == {**tomllib.loads(before.decode()), "merge": "agent"}


def test_2_enable_leaves_a_form_it_cannot_edit_alone_and_says_so(owner):
    set_main(owner, 'merge = """human"""\n' + (owner.repo.path / "forge.toml").read_text("utf-8"))
    before = raw(owner, "origin/main")

    refused = enable(owner)

    assert refused.returncode != 0
    where = worktree(owner)
    # The edit left a file that does not parse, so Forge refused before writing it.
    assert refused.stderr.startswith("forge.toml is not usable: ")
    assert refused.stderr.endswith("\nNext: forge doctor\n")
    assert (where / "forge.toml").read_bytes() == before
    assert not owner.gh_calls("pr", "create")
