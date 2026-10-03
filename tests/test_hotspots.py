STORY = "FORGE-SPOTTED-1"

import json
import shlex
import string
from pathlib import Path

import pytest

from test_close import env, STORY_DOC  # noqa: F401
from test_spotted import entry, listed, note, LIST
from test_fix_plans_roadmap_json_conflicts_on_almost_e import _git
from test_setup import _fresh_client
from test_measure import SPEC, DUE


WHY = "Simplify app.py: problems keep turning up there"
DONE = "app.py is simpler and none of these happen any more: Alpha; Beta; Gamma"
COMMAND = f'Next: forge fix start "{WHY}" --done "{DONE}"'


def land(env, branch):
    env.repo.git("merge", "-q", "--no-edit", branch)
    env.repo.git("push", "-q", "origin", "main")


def seed(env, items, raw=None):
    env.repo.write("app.py", "pass\n")
    env.repo.write(LIST, raw if raw is not None else json.dumps({"items": items}))
    env.repo.git("add", "-A")
    committed = _git(env.repo, "commit", "-q", "-m", "Noted problems")
    assert committed.returncode == 0, committed.stderr
    env.repo.git("push", "-q", "origin", "main")


def opens():
    return [entry("bug", "app.py", 1, text, "worker", item="earlier")
            for text in ("Alpha", "Beta", "Gamma")]


def _close_lands_hotspots_and_the_printed_command_starts_the_fix(env):
    item, where = env.start_fix()
    note(env, where, "Notes\n\n" + "\n".join(
        f"Spotted: bug app.py:1 {text}" for text in ("Gamma", "Alpha", "Beta")))
    assert env.close(item).returncode == 0
    land(env, "fix/tidy-readme")
    env.repo.git("worktree", "remove", str(where))
    result = env.repo.forge("next")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("app.py keeps breaking: 3 noted problems are open there.\n"
                                    + COMMAND + "\nNo story or fix is in progress")
    started = env.repo.forge(*shlex.split(COMMAND.removeprefix("Next: forge ")))
    assert started.returncode == 0, started.stderr
    folder = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    # Locate the new state rather than the earlier merged fix's state.
    states = [json.loads(p.read_text()) for p in (folder / ".factory/fixes").glob("*.json")]
    state = next(s for s in states if s["why"] == WHY)
    assert state["done_when"] == DONE
    assert "app.py keeps breaking" not in env.repo.forge("next").stdout


COUNT_CASES = [
    (opens()[:2], None, 0),
    ([*opens()[:2], {**opens()[2], "status": "done", "closed_by": "earlier"}], None, 0),
    ([entry("bug", "app.py", 1, str(n), "blocking") for n in range(3)], None, 0),
    ([entry("bug", "app.py", 1, "Same", "blocking", item=i) for i in ("one", "two")], "blocking", 2),
    ([entry(k, "app.py", 1, "Same", "blocking", item=i)
      for k, i in (("bug", "one"), ("simplify", "two"))], None, 0),
    ([entry(k, "app.py", 1, "Same", "blocking", item=i)
      for k, names in (("bug", ("one", "two")), ("simplify", ("one", "two", "three")))
      for i in names], "blocking", 3),
    ([*[{**e, "from": "review"} for e in opens()],
      *[entry("bug", "app.py", 1, "Same", "blocking", item=i) for i in ("one", "two")]], "open", 3),
]


def _counts_open_advice_and_distinct_changes_per_kind(env, items, reason, count):
    seed(env, items)
    result = env.repo.forge("next")
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if "keeps breaking:" in line]
    if reason is None:
        assert lines == []
    elif reason == "open":
        assert lines == [f"app.py keeps breaking: {count} noted problems are open there."]
    else:
        assert lines == [f"app.py keeps breaking: {count} changes had the same kind of serious review finding there."]


def _command_cleans_punctuation_and_limits_texts(env):
    seed(env, [entry("bug", "app.py", 1, f"{n} {string.punctuation}", "worker")
               for n in range(7)])
    result = env.repo.forge("next")
    command = next(line for line in result.stdout.splitlines() if line.startswith('Next: forge fix start "Simplify'))
    cleaned = ",-./:; _"
    expected = "app.py is simpler and none of these happen any more: " + "; ".join(
        f"{n} {cleaned}" for n in range(5)) + "; and 2 more"
    assert shlex.split(command)[-1] == expected


def _success_checks_then_sorted_hotspots_then_idle_lines(env):
    env.repo.write("docs/specs/invoices.md", "---\nstatus: confirmed\ntitle: Invoices by email\n---\n" + SPEC)
    env.repo.write("plans/roadmap.json", json.dumps({"items": [
        {"key": key, "spec": "docs/specs/invoices.md"} for key in ("INV-1", "INV-2")]}))
    for key in ("INV-1", "INV-2"):
        env.repo.write(f".factory/stories/{key}/story.json", '{"status": "done"}')
    env.repo.write("z.py", "pass\n")
    seed(env, [*[entry("bug", "z.py", 1, text, "worker") for text in ("Z", "Y", "X")], *opens()])
    result = env.repo.forge("next")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[:8] == [*DUE,
        "app.py keeps breaking: 3 noted problems are open there.", COMMAND,
        "z.py keeps breaking: 3 noted problems are open there.",
        'Next: forge fix start "Simplify z.py: problems keep turning up there" --done "z.py is simpler and none of these happen any more: X; Y; Z"',
        "No story or fix is in progress."]


def _missing_deleted_and_unreadable_lists(env):
    assert "keeps breaking" not in env.repo.forge("next").stdout
    seed(env, opens())
    env.repo.git("rm", "app.py")
    assert _git(env.repo, "commit", "-q", "-m", "Remove app").returncode == 0
    env.repo.git("push", "-q", "origin", "main")
    assert "keeps breaking" not in env.repo.forge("next").stdout
    seed(env, [], raw="broken")
    result = env.repo.forge("next")
    assert result.returncode == 0
    assert result.stdout.startswith("plans/spotted.json on the default branch can't be read, so no hotspots are listed: it isn't UTF-8 JSON.\n")


@pytest.mark.parametrize("case,details", [
    (_close_lands_hotspots_and_the_printed_command_starts_the_fix, ()),
    (_command_cleans_punctuation_and_limits_texts, ()),
    (_success_checks_then_sorted_hotspots_then_idle_lines, ()),
    (_missing_deleted_and_unreadable_lists, ()),
    *[(_counts_open_advice_and_distinct_changes_per_kind, details) for details in COUNT_CASES],
])
def test_3_hotspots_offer_ready_fixes(env, monkeypatch, case, details):
    monkeypatch.setenv("FORGE_NOW", "2026-10-01T09:00:00+00:00")
    case(env, *details)


def _closed_fix_resolves_only_named_paths_and_leaves_its_own_notes(env):
    seed(env, [*opens(), entry("bug", "other/app.py", 1, "Other", "worker", item="earlier"),
               entry("bug", "app.py.bak", 1, "Backup", "worker", item="earlier")])
    item, where = env.start_fix(done_when=DONE)
    note(env, where, "Notes\n\nSpotted: edge app.py:1 New issue")
    assert env.close(item).returncode == 0
    entries = listed(where)
    assert all(e["status"] == "done" and e["closed_by"] == item
               for e in entries if e["text"] in ("Alpha", "Beta", "Gamma"))
    assert all(e["status"] == "open" for e in entries if e["text"] in ("Other", "Backup", "New issue"))
    assert "keeps breaking" in env.repo.forge("next").stdout
    land(env, "fix/tidy-readme")
    assert "keeps breaking" not in env.repo.forge("next").stdout


def _task_naming_a_path_closes_nothing(env):
    seed(env, opens())
    item, where = env.start_approved_task(STORY_DOC.replace("A shopper can save a basket.", DONE))
    assert env.close(item).returncode == 0
    assert listed(where) == opens()


@pytest.mark.parametrize("case", [_closed_fix_resolves_only_named_paths_and_leaves_its_own_notes,
                                  _task_naming_a_path_closes_nothing])
def test_4_only_a_fix_closes_its_named_files_entries(env, case):
    case(env)


@pytest.mark.parametrize("previous", [False, True])
def test_6_new_and_previously_adopted_clients_get_hotspot_guidance(repo, gh, previous, tmp_path):
    if previous:
        import shutil
        source = Path(__file__).parent / "fixtures/adopted-v1.2.2/client"
        shutil.copytree(source, repo.path, dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/hotspot-guide")
        # Upgrade the previous release's pin before the new release syncs its guide.
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text()
        repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"'))
        client = repo.path
        synced = repo.forge("sync")
    else:
        client, synced = _fresh_client(repo, gh, tmp_path)
    assert synced.returncode == 0, synced.stderr
    template = (Path(__file__).parents[1] / "src/forge/templates/skill.md").read_text()
    for text in [template, *[(client / host / "skills/forge/SKILL.md").read_text()
                            for host in (".claude", ".codex")]]:
        assert text.index("## Closing") < text.index("## Hotspots") < text.index("## Check-back")
        flat = " ".join(text.split())
        for sentence in (
            "A worker or review notes problems outside its change as spotted items, which Forge keeps in `plans/spotted.json` and nobody edits by hand.",
            "A spotted item never widens the change in hand, except a bug that blocks it.",
            "When `forge next` names a file that keeps breaking, start its fix command at once, like any ready item, without asking the owner.",
            "When `forge merge` fails because the pull request no longer merges cleanly, run `forge close <item>` again, which merges the default branch with Forge's own rule for the spotted list and the roadmap.",
            "Count the story's items' entries per file in `plans/spotted.json` on the default branch, open or done; each file with three or more, or one a task was stopped on (its state's `stop`), gets one trap line naming the file and the kind of problem that kept coming back."):
            assert sentence in flat
