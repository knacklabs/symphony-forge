"""An upgrade fix that holds only the version line and Forge's own synced files skips the model review."""
import json
import re
import shutil

import pytest

import conftest
from test_close import CLEAN, GREEN, blocked, env, finding  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import NAME, RELEASE, Upgrade, unsynced_up  # noqa: F401
from test_upgrade_synced import _commit, _sync

STORY = "FIX-UPGRADE-NO-MODEL-REVIEW"


def _ready(up, adopted, *init_args):
    """A repo on an older Forge: a fresh client, or one adopted on an earlier release."""
    if adopted:
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client",
                        up.repo.path, dirs_exist_ok=True)
        up.repo.git("switch", "-q", "-c", "adoption")
        up.repo.git("add", "-A")
        up.repo.git("commit", "-q", "-m", "Adopt the earlier release")
        up.repo.git("switch", "-q", "main")
        up.repo.git("merge", "-q", "--ff-only", "adoption")
        up.repo.git("push", "-q", "origin", "main")
        return up
    client, initialized = _fresh_client(up.repo, up.env.gh, up.tmp, *init_args)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    up.repo.path = client
    up = Upgrade(up.env, up.tmp)
    up.env.checks(GREEN)
    return up


def _commit_in_fix(up, message, *paths):
    up.repo.git("add", *paths, cwd=up.folder)
    up.repo.git("-c", f"core.hooksPath={up.tmp / 'no-hooks'}", "commit", "-q", "-m", message,
                cwd=up.folder)


def _hand_edit(up):
    (up.folder / "docs").mkdir(exist_ok=True)
    (up.folder / "docs" / "notes.md").write_text("hand edit\n", encoding="utf-8")
    _commit_in_fix(up, "Add a note", "docs/notes.md")


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_pure_upgrade_skips_review_and_extra_edit_gets_one(unsynced_up, adopted):
    up = _ready(unsynced_up, adopted)

    upgraded = up.run(RELEASE)

    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    assert up.env.review_calls() == []

    # One hand-edited file turns the same fix back into a normal reviewed change.
    _hand_edit(up)
    closed = up.repo.forge("close", NAME, cwd=up.folder)

    assert len(up.env.review_calls()) == 1, closed.stdout + closed.stderr


@pytest.mark.parametrize("case", ["starter-pnpm", "new-client-npm", "adopted-pnpm"])
def test_2_pure_upgrade_in_a_repo_with_a_lockfile_skips_review(unsynced_up, case):
    # The workflow Forge writes caches by the lockfile, so the check must render it the same way.
    up = _ready(unsynced_up, case.startswith("adopted"), *(["--starter"] if "starter" in case else []))
    if "npm" in case:
        up.on_main("package.json", '{"name": "app", "version": "1.0.0"}\n')
        up.on_main("package-lock.json", '{"lockfileVersion": 3}\n')
    elif "adopted" in case:
        up.on_main("pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
    else:
        assert (up.repo.path / "pnpm-lock.yaml").is_file()

    upgraded = up.run(RELEASE)

    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    assert re.search(r"pnpm-lock\.yaml|cache-dependency-path: package-lock\.json",
                     up.show(".github/workflows/forge.yml"))
    assert up.env.review_calls() == []


LAUNCHER = ".claude/skills/impeccable/scripts/impeccable"


@pytest.mark.parametrize("change, adopted", [
    ("forge.toml comment", False), ("executable bit", False), ("new launcher loses its bit", True)],
    ids=["forge.toml-comment", "executable-bit", "new-launcher-adopted-v1.2.2"])
def test_3_a_byte_that_is_not_the_version_or_sync_output_gets_a_review(unsynced_up, change, adopted):
    up = _ready(unsynced_up, adopted)
    assert up.run(RELEASE).returncode == 0
    assert up.env.review_calls() == []

    if change == "forge.toml comment":
        (up.folder / "forge.toml").write_bytes((up.folder / "forge.toml").read_bytes() + b"# a note\n")
        _commit_in_fix(up, "Note in forge.toml", "forge.toml")
    elif change == "executable bit":
        up.repo.git("update-index", "--chmod=+x", ".claude/skills/forge/SKILL.md", cwd=up.folder)
        _commit_in_fix(up, "Make the skill executable")
    else:
        # The adopted release shipped no launcher, so the upgrade adds it, and sync makes it
        # executable. An extra commit that clears the bit is not what sync writes.
        assert up.repo.git("ls-tree", f"fix/{NAME}", LAUNCHER, cwd=up.folder).startswith("100755 ")
        up.repo.git("update-index", "--chmod=-x", LAUNCHER, cwd=up.folder)
        _commit_in_fix(up, "Clear the launcher's executable bit")
    closed = up.repo.forge("close", NAME, cwd=up.folder)

    assert len(up.env.review_calls()) == 1, closed.stdout + closed.stderr


@pytest.mark.parametrize("name, why", [
    ("tidy-readme", "Readme greets new readers"),
    ("upgrade-forge-to-{}", "Readme greets new readers"),
], ids=["other-fix", "upgrade-name-only"])
def test_4_a_fix_that_forge_upgrade_did_not_make_gets_a_review(env, name, why):
    # The default branch pins an older Forge; the fix pins the installed one and syncs, as an
    # upgrade does, but it is not the fix that forge upgrade made.
    toml = (env.repo.path / "forge.toml").read_text("utf-8")
    installed = re.search(r'^version = "(.+)"$', toml, re.M)[1]
    env.commit(env.repo.path, "forge.toml", toml.replace(installed, "v1.0.0"), "Pin Forge v1.0.0")
    env.repo.git("push", "-q", "origin", "main")
    name = name.format(installed.replace(".", "-"))
    item, where = env.start(name, f"fix/{name}", f".factory/fixes/{name}.json",
                            {"kind": "fix", "why": why, "done_when": "The readme opens with a greeting",
                             "allow_large": "Forge's first synced files"}, {"forge.toml": toml})
    _sync(env, where)
    _commit(env, where)

    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 0, done.stdout + done.stderr
    assert len(env.review_calls()) == 1


def test_5_an_earlier_blocking_finding_is_not_replaced_by_the_mechanical_result(unsynced_up):
    up = _ready(unsynced_up, False)
    assert up.run(RELEASE).returncode == 0
    # A hand edit gets a review that blocks and stops for the owner's choice. Its finding names a
    # file that is not in the tree, so the review leaves no spotted record behind in the diff.
    _hand_edit(up)
    up.env.reviews(blocked({**finding("P1", "The note is wrong", "docs/missing.md"),
                            "body": "Gain 4, Work 1, Harm 2\nThe note is wrong."}), CLEAN)
    stopped = up.repo.forge("close", NAME, cwd=up.folder)
    assert len(up.env.review_calls()) == 1, stopped.stdout + stopped.stderr
    chosen = up.repo.forge("close", NAME, "--resolve", "more", "--reason", "One more round",
                           cwd=up.folder)
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr

    # The worker drops the hand edit instead of repairing the finding. The branch is a pure
    # upgrade again, but the blocker was never checked, so the model reviews once more.
    up.repo.git("rm", "-q", "docs/notes.md", cwd=up.folder)
    _commit_in_fix(up, "Drop the note")
    again = up.repo.forge("close", NAME, cwd=up.folder)

    assert len(up.env.review_calls()) == 2, again.stdout + again.stderr
    state = json.loads((up.folder / ".factory" / "fixes" / f"{NAME}.json").read_text("utf-8"))
    assert state["review"]["findings"] == []
