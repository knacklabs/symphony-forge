"""The plan read names a file that three or more parts list, and the guide says what to plan."""
import json
import re
import shutil

import pytest

from conftest import ROOT
from test_codex_reader import GRILL
from test_codex_worker import _toml
from test_scope_overlap_explains_waits import _prepare
from test_story import DOC, claude_plan, hook, new_story, setup
from test_tools_native_reads import native_host  # noqa: F401  (the session fixture)

STORY = "FORGE-GENFILE-1"
pytestmark = pytest.mark.platform

OLD = re.search(r"\| ID \|.*?\n\nNew moving parts", DOC, re.S)[0]
FILE = "src/api/openapi.json"


def plan(*rows):
    lines = [f"| {name} | {name} | Part {name} | {covers} | {scope} | `tests/test_{name.lower()}.py` | "
             f"{after} | no |" for name, covers, scope, after in rows]
    head = OLD.split("\n")[0:2]
    return DOC.replace(OLD, "\n".join(head + lines) + "\n\nNew moving parts")


def chain(*scopes):
    return plan(*[(name, 1, scope, "none" if not index else "ABC"[index - 1])
                  for index, (name, scope) in enumerate(zip("ABC", scopes))])


THREE = chain(f"`{FILE}` (regenerated), `tests/`", f"`src/a.py`, `{FILE}`, `tests/`", f"`{FILE}`, `tests/`")
LINE = re.compile(rf"^Shared file: 3 parts of this plan list {FILE} in their Scope \(A, B, C\)\. .*$", re.M)


def start(repo, adopted):
    if adopted:
        _prepare(repo, True)
        setup(repo)
    else:
        setup(repo)
        repo.git("switch", "-qc", "fix/sync-guides")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("config", "core.hooksPath", (repo.path.parent / "fixture-no-hooks").as_posix())
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Sync the guides")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/sync-guides")
        repo.git("push", "-q", "origin", "main")


@pytest.mark.parametrize("adopted", [False, True], ids=["new repo", "earlier adopted"])
def test_1_the_plan_read_names_a_file_that_three_parts_share(repo, claude_payload, adopted):
    start(repo, adopted)
    path = new_story(repo, "SHOP")
    doc = path / "plans/SHOP.md"
    doc.write_text(THREE, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    out = read.stdout.replace("\r\n", "\n")
    assert len(LINE.findall(out)) == 1 and "tests/" not in "".join(LINE.findall(out)), out
    note = LINE.search(out)[0]
    assert "make it at build time and take it out of every Scope" in note
    assert "put its change in one first part that the other parts wait for" in note
    assert out.index("Shared file:") < out.index("Round 1") and "found nothing" in out
    assert "Shared file" not in (path / "plans/SHOP.read.md").read_text("utf-8")
    # Advice only: the plan is approved and its first part starts.
    assert hook(repo, claude_plan(claude_payload, THREE, cwd=path)).returncode == 0
    started = repo.forge("task", "start", "SHOP/A")
    assert started.returncode == 0, started.stdout + started.stderr

    # Two parts on the file, and a folder with two other files under it, print no note.
    for text in (chain(f"`{FILE}`", f"`{FILE}`", "`src/b.py`"),
                 chain("`src/api/`", "`src/api/a.json`", "`src/api/b.json`")):
        doc.write_text(text, encoding="utf-8")
        again = repo.forge("read", "SHOP")
        assert again.returncode == 0 and "Shared file" not in again.stdout, again.stdout + again.stderr

    # The shipped guides and the plan template carry the planner rule.
    for host in (".claude", ".codex"):
        guide = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "a file that a script can make at build time" in guide
        assert "The `Shared file:` note is advice" in guide
    made = new_story(repo, "WISH")
    assert "a file that a script can make at build time" in " ".join(
        (made / "plans/WISH.md").read_text("utf-8").split())


@pytest.mark.parametrize("tool", ["claude"])
def test_2_session_read_prints_the_note_when_the_result_is_handed_back(
        repo, monkeypatch, tmp_path, tool, native_host):
    setup(repo)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "native-reader-session")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(THREE, "utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    (shop / "forge.toml").write_text(_toml(version, "split", GRILL).replace(
        'workers = "split"', 'workers = "split"\ntools = "claude"'), "utf-8")
    handed = repo.forge("read", "SHOP")
    assert handed.returncode == 0, handed.stdout + handed.stderr
    offer = json.loads(handed.stdout)
    assert "Shared file" not in handed.stdout
    done = repo.forge("handback", "SHOP", "--round", str(offer["round"]), "--subagent", "reader-chat",
                      "--text", "No findings.")
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(LINE.findall(done.stdout)) == 1
    assert done.stdout.index("Shared file:") < done.stdout.index("Round ")
