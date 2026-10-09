"""Close publishes the current contract and decodes story titles independently of locale.

Real amend and close commands own the result; only GitHub and the reviewer are faked.
Existing title coverage never amends a published contract or changes the platform encoding.
"""
import pytest

from conftest import patient
from test_close import STORY_DOC, body, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "skipped-close"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_replaces_done_when_after_amend_and_preserves_human_notes(env, previous):
    client(env, previous)
    item, where = env.start_fix()
    first = env.close(item)
    assert first.returncode == 0, first.stdout + first.stderr
    original = body(env.gh_calls("pr", "create")[-1])
    note = "Checked by the shop owner.\nDone when: a quoted example in the notes.\n"
    env.open_pr(original + note)
    contract = r"The greeting includes a literal \1 and a basket"
    amended = env.repo.forge("fix", "amend", item, "--done", contract,
                             "--because", "The owner clarified the greeting")
    assert amended.returncode == 0, amended.stdout + amended.stderr
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    updated = body(env.gh_calls("pr", "edit")[-1])
    assert updated.splitlines()[1] == f"Done when: {contract}"
    assert "Done when: The readme opens with a greeting" not in updated
    assert updated.endswith(note)
    assert len(env.review_calls()) == 2


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_2_close_reads_story_title_as_utf8_in_a_legacy_locale(env, previous, monkeypatch):
    client(env, previous)
    title = "Shoppers save a basket 雪"
    env.commit(env.repo.path, "plans/SHOP.md",
               STORY_DOC.replace("Shoppers can save a basket", title, 1))
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_task()
    # Initialize UTF-8 argv encoding, then switch only text decoding to the C locale.
    # Starting Linux in an uncoerced C locale also makes publishing Unicode argv fail.
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.setenv("LC_CTYPE", "C")
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONCOERCECLOCALE", "1")
    shim = env.repo.bin / "forge"
    source = shim.read_text("utf-8")
    patient(lambda: shim.write_text(source.replace("from forge.cli import main",
        "import locale\n"
        "assert sys.getfilesystemencoding() == 'utf-8'\n"
        "assert not sys.flags.utf8_mode\n"
        "locale.setlocale(locale.LC_CTYPE, 'C')\n"
        "assert locale.getpreferredencoding(False).lower() not in ('utf-8', 'utf8')\n"
        "from forge.cli import main"), encoding="utf-8"))
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    [created] = env.gh_calls("pr", "create")
    assert created[created.index("--title") + 1] == f"{title}: Save a basket"
