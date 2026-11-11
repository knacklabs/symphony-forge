"""The plan read names a file that three or more parts list, and the guide says what to plan."""
import json
import os
import re

import pytest

from conftest import ROOT, _install
from test_after_another_story_task import OTHER
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


def chain(*scopes, first="none"):
    return plan(*[(name, 1, scope, first if not index else "ABC"[index - 1])
                  for index, (name, scope) in enumerate(zip("ABC", scopes))])


THREE = chain(f"`{FILE}` (regenerated), `tests/`", f"`src/a.py`, `{FILE}`, `tests/`", f"`{FILE}`, `tests/`")
LINE = re.compile(rf"^Shared file: 3 parts of this plan list {FILE} in their Scope \(A, B, C\)\. .*$", re.M)
# The planner rule has two halves, and each place that carries it must say both.
KEEP_OUT = re.compile(r"a file that a script can make at build time.{0,90}out of the repo and out of every Scope")
KEPT = re.compile(r"the repo keeps such a file on purpose, give its change to one (?:first )?part "
                  r"that the others? (?:parts )?wait for")


def start(repo, adopted):
    """A client repo with the stub reader: a new one, or the earlier release's client fixture
    moved to this release. Both run `forge sync` for the guides."""
    if adopted:
        _prepare(repo, True)
        settings = (repo.path / "forge.toml").read_text("utf-8")
        setup(repo, kind="client")  # the roadmap, the app look and the stub reader
        repo.write("forge.toml", settings)  # but keep the adopted client's own settings
    else:
        setup(repo, kind="client")
        repo.git("switch", "-qc", "fix/sync-guides")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("config", "core.hooksPath", (repo.path.parent / "fixture-no-hooks").as_posix())
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Sync the guides")
    if not adopted:
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/sync-guides")
    repo.git("push", "-q", "origin", "main")
    assert 'repo = "client"' in (repo.path / "forge.toml").read_text("utf-8")


@pytest.mark.parametrize("adopted", [False, True], ids=["new repo", "earlier adopted"])
def test_1_the_plan_read_names_a_file_that_three_parts_share(repo, claude_payload, adopted):
    start(repo, adopted)
    path = new_story(repo, "SHOP")
    assert 'repo = "client"' in (path / "forge.toml").read_text("utf-8")
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

    # No note: two parts on the file; a folder with two other files under it; a folder written
    # without its slash, as an existing directory and as one that another entry lists files in.
    (path / "src/api").mkdir(parents=True, exist_ok=True)
    (path / "src/api/openapi.json").write_text("{}\n", encoding="utf-8")
    for text in (chain(f"`{FILE}`", f"`{FILE}`", "`src/b.py`"),
                 chain("`src/api/`", "`src/api/a.json`", "`src/api/b.json`"),
                 chain("`src/api`", "`src/api`", "`src/api`"),
                 chain("`src/web`", "`src/web`", "`src/web`, `src/web/page.tsx`")):
        doc.write_text(text, encoding="utf-8")
        again = repo.forge("read", "SHOP")
        assert again.returncode == 0 and "Shared file" not in again.stdout, text + again.stdout + again.stderr

    # The planner rule, both halves, in the plan template and in every guide that carries it.
    made = new_story(repo, "WISH")
    places = {"plan template": (made / "plans/WISH.md").read_text("utf-8"),
              "guide source": (ROOT / "src/forge/templates/skill.md").read_text("utf-8"),
              "docs guide": (ROOT / "docs/guide.md").read_text("utf-8")}
    for host in (".claude", ".codex"):
        places[f"synced {host} guide"] = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
    for name, text in places.items():
        text = " ".join(text.split())
        assert KEEP_OUT.search(text), f"{name} does not say to keep a generated file out of the repo and Scopes"
        assert KEPT.search(text), f"{name} does not say to give a kept file to one first part"
        if name != "plan template":
            assert "The `Shared file:` note is advice: it does not stop the read or the approval" in text, name
        if name == "guide source" or name.startswith("synced"):  # the rule must not cut the sentence before it
            assert "Tasks that need it wait for that task through After, then own only their files." in text, name


def native(repo, monkeypatch, tmp_path, tool, text=THREE, keys=("SHOP",), rounds=2):
    """A client repo where the coordinating `tool` session owns the read of SHOP; returns SHOP's folder."""
    setup(repo, kind="client", keys=keys)
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    _install(repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
    monkeypatch.setenv("CODEX_BIN", str(repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
    if tool == "claude":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "native-reader-session")
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(text, "utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    (shop / "forge.toml").write_text(_toml(version, "split", GRILL, "client").replace(
        'workers = "split"', f'workers = "split"\ntools = "{tool}"\ncold_read_rounds = {rounds}'), "utf-8")
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(f'[projects.{json.dumps(str(shop))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    return shop


def handed(repo):
    offer = repo.forge("read", "SHOP")
    assert offer.returncode == 0, offer.stdout + offer.stderr
    assert "Shared file" not in offer.stdout  # the offer is JSON for the session; the result carries the note
    return json.loads(offer.stdout)["round"]


def back(repo, number, text):
    return repo.forge("handback", "SHOP", "--round", str(number), "--subagent", "reader-chat", "--text", text)


def once(done):
    out = done.stdout.replace("\r\n", "\n")
    assert len(LINE.findall(out)) == 1, out
    return out


@pytest.mark.parametrize("tool", ["codex", "claude"])
def test_2_a_session_read_prints_the_note_with_each_result(repo, monkeypatch, tmp_path, tool, native_host):
    shop = native(repo, monkeypatch, tmp_path, tool, rounds=1)
    # A result at the round limit with an open note stops the read; the note still shows, once.
    stopped = back(repo, handed(repo), "1. Missing saved basket ownership.")
    assert stopped.returncode == 1 and "asks the owner" in stopped.stderr, stopped.stdout + stopped.stderr
    once(stopped)
    assert "Shared file" not in stopped.stderr
    # The owner's choice shows it again before approval.
    accepted = repo.forge("read", "SHOP", "--resolve", "accept", "--reason", "the owner accepts it")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert once(accepted).index("Shared file:") < accepted.stdout.index("Recorded the human's choice")
    # A clean result prints it before the round line.
    doc = shop / "plans/SHOP.md"
    doc.write_text(doc.read_text("utf-8") + "\nSaved baskets belong to their shopper.\n", "utf-8")
    done = back(repo, handed(repo), "No findings.")
    assert done.returncode == 0, done.stdout + done.stderr
    assert once(done).index("Shared file:") < done.stdout.index("Round ") and "found nothing" in done.stdout


@pytest.mark.parametrize("tool", ["claude"])
def test_3_a_conflicting_other_story_cannot_stop_a_read_for_its_note(
        repo, monkeypatch, tmp_path, tool, native_host):
    waiting = chain(f"`{FILE}`", f"`{FILE}`", f"`{FILE}`", first="TURN-1/T4")
    shop = native(repo, monkeypatch, tmp_path, tool, text=waiting, keys=("SHOP", "TURN-1"))
    turn = new_story(repo, "TURN-1")
    (turn / "plans/TURN-1.md").write_text(OTHER, "utf-8")
    repo.git("add", "-A", cwd=turn)
    repo.git("commit", "-qm", "Plan TURN-1", cwd=turn)
    repo.git("push", "-q", "-u", "origin", "story/TURN-1", cwd=turn)
    number = handed(repo)  # SHOP's After names TURN-1/T4, which exists now
    # While the reader works, TURN-1's own and published plans get edits that git cannot merge.
    published = tmp_path / "published"
    repo.git("worktree", "add", "-q", "-b", "published", str(published), "origin/story/TURN-1")
    for where, branch, word in ((published, "published", "early"), (turn, "story/TURN-1", "a shop")):
        file = where / "plans/TURN-1.md"
        file.write_text(file.read_text("utf-8").replace("when they leave.", f"when they leave {word}."), "utf-8")
        repo.git("commit", "-aqm", f"Change TURN-1 for {word}", cwd=where)
    repo.git("push", "-q", "origin", "published:story/TURN-1", cwd=published)
    repo.git("fetch", "-q", "origin")
    done = back(repo, number, "No findings.")
    assert done.returncode == 0, done.stdout + done.stderr
    assert once(done).index("Shared file:") < done.stdout.index("Round ") and "found nothing" in done.stdout
    assert shop.joinpath("plans/SHOP.read.md").is_file()
