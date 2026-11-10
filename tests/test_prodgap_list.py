"""Done-when 1-3 of FORGE-PRODGAP-1: forge next and the board list what a signed-off prototype still lacks.

Each test runs the real forge commands on a client whose remote default branch holds the facts.
A second clone pushes the changes, the way a merge from another checkout would.
"""
import itertools
import json
import os
import re
import shutil
import sys

import pytest

import conftest
from test_sample_checklist import brief
from test_setup import _fresh_client
from test_story import DOC

MINUTES = itertools.count(1)
STORY = "FORGE-PRODGAP-1"
SIGNOFF = "---\nstatus: accepted\n---\n\n# Client sign-off\n"
LABEL = '<Badge>Demo only</Badge>\n'
APP = "apps/web/src/orders.tsx"
SAMPLE = ('Sample data is on, so the app has no back end, no tests and no CI. Say: "Leave sample data: '
          'settle the Personal data answer, set the test command and checks, then set sample_data = '
          'false in forge.toml"')
APP2 = "apps/web/src/basket.tsx"
DEMO = f'1 file carries the "Demo only" label: {APP}. Say: "Build each demo-only feature properly or remove it: {APP}"'


def settings(text: str, stage: str = "prototype", sample_data: bool | None = None) -> str:
    text = re.sub(r"^(stage|sample_data) = .*\n", "", text, flags=re.M)
    extra = "" if sample_data is None else f"sample_data = {str(sample_data).lower()}\n"
    return re.sub(r"^(repo = .*\n)", rf'\1stage = "{stage}"\n{extra}', text, count=1, flags=re.M)


def publish(repo, folder, message):
    """Commit and push to the remote default branch, as a merge made elsewhere would."""
    quiet = folder.parent / f"{folder.name}-no-hooks"
    quiet.mkdir(exist_ok=True)
    hooks = f"core.hooksPath={quiet.as_posix()}"
    repo.git("add", "-A", cwd=folder)
    os.environ["GIT_COMMITTER_DATE"] = f"2026-11-10T10:{next(MINUTES):02d}:00+00:00"  # every change lands later
    try:
        repo.git("-c", hooks, "commit", "-q", "-m", message, cwd=folder)
    finally:
        del os.environ["GIT_COMMITTER_DATE"]
    repo.git("-c", hooks, "push", "-q", "origin", "HEAD:main", cwd=folder)


def push(repo, tmp_path, files, message="Change the app"):
    """A second clone changes files (None deletes) on the remote; the main checkout keeps its files."""
    other = tmp_path / "second"
    if other.exists():
        repo.git("pull", "-q", "--ff-only", "origin", "main", cwd=other)
    else:
        repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(other))
    for name, text in files.items():
        path = other / name
        if text is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text(path.read_text("utf-8")) if callable(text) else text, encoding="utf-8")
    publish(repo, other, message)


def client(repo, gh, tmp_path, adoption, sample_data=None, signed=True):
    """A prototype on the remote default branch, with its sign-off recorded unless signed is False."""
    if adoption == "new client":
        path, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        repo.path = path
    else:
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    toml = repo.path / "forge.toml"
    toml.write_text(settings(toml.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                             sample_data=sample_data), encoding="utf-8")
    if signed:
        repo.write("docs/decisions/0001-client-signoff.md", SIGNOFF)
    publish(repo, repo.path, "Record the prototype")
    return repo.path


def lines(repo, *command):
    shown = repo.forge(*command)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    return shown.stdout.splitlines()


def gaps(repo):
    """The listing in forge next: its heading and rows; and the board's version of it."""
    repo.git("fetch", "-q", "origin")
    text = lines(repo, "next")
    board = json.loads(repo.forge("board", "--json").stdout)["signoff"]
    rows = [row for row in text if row.startswith("- ")]
    assert [f'- {row["item"]}. Say: "{row["say"]}"' for row in board["open"]] == rows or not board["line"]
    heading = [row for row in text if row.startswith("Before production:")]
    assert heading == ([board["line"]] if board["line"] else [])
    return heading, rows


@pytest.mark.parametrize("adoption", ["new client", "earlier adopted"])
def test_1_sample_data_gap_shows_after_signoff_and_clears(repo, gh, tmp_path, adoption):
    new = adoption == "new client"
    client(repo, gh, tmp_path, adoption, sample_data=True if new else None, signed=False)
    repo.write("docs/product/BRIEF.md", brief(("Demo workflow", "Demo workflow: ask the client (salesperson, 2026-11-02)")))
    publish(repo, repo.path, "Write the brief")
    # Before the sign-off is accepted, the line is today's sign-off line and no list shows.
    before = "\n".join(lines(repo, "next"))
    assert "Sign-off: 1 open question, signer Sam Lee" in before and "Before production" not in before

    push(repo, tmp_path, {"docs/decisions/0001-client-signoff.md": SIGNOFF})
    if not new:
        # An old record's sample_data line is not the setting; forge.toml holds none.
        push(repo, tmp_path, {"docs/decisions/0001-client-signoff.md": SIGNOFF.replace("accepted\n", "accepted\nsample_data: true\n")})
        assert gaps(repo) == ([], [])
        push(repo, tmp_path, {"forge.toml": lambda text: settings(text, sample_data=True)})
    heading, rows = gaps(repo)
    assert heading == ["Before production: 1 open gap"] and rows == [f"- {SAMPLE}"]
    board = json.loads(repo.forge("board", "--json").stdout)["signoff"]
    assert board["line"] == "Before production: 1 open gap" and len(board["open"]) == 1

    # Another checkout turns sample data off: this checkout still has the old file, the row is gone.
    push(repo, tmp_path, {"forge.toml": lambda text: settings(text, sample_data=False)})
    assert 'sample_data = false' not in (repo.path / "forge.toml").read_text("utf-8")
    assert gaps(repo) == ([], [])
    # A live app shows no list at all, and the list returns when the stage is a prototype again.
    push(repo, tmp_path, {"forge.toml": lambda text: settings(text, "live", True)})
    assert gaps(repo) == ([], [])
    push(repo, tmp_path, {"forge.toml": lambda text: settings(text, "prototype", True)})
    assert gaps(repo)[0] == ["Before production: 1 open gap"]


def fix(name, why="Build it", level="P0", allowance=True, **state):
    review = {"blocking_level": level, "findings": []}
    return {f".factory/fixes/{name}.json": json.dumps({
        "kind": "fix", "status": "waiting for checks", "why": why, "done_when": "It works", "review": review,
        **({"allow_large": "Prototype before sign-off"} if allowance else {}), **state})}


def light(*names):
    return f'Review and test {"this part" if len(names) == 1 else "these parts"} in full: {", ".join(names)}'


@pytest.mark.parametrize("adoption", ["new client", "earlier adopted"])
def test_2_demo_only_labels_show_and_clear(repo, gh, tmp_path, adoption):
    client(repo, gh, tmp_path, adoption, sample_data=False)
    for name in ("codex", "claude", "autoreview"):  # the list asks no model
        conftest._install(repo.bin, name, f"#!{sys.executable}\nimport pathlib, sys\n"
                          f"pathlib.Path({str(tmp_path / 'model-called')!r}).write_text('called')\nsys.exit(1)\n")
    push(repo, tmp_path, {APP: f"export const Orders = () => {LABEL}", "docs/specs/demo.md": "Demo only pages.\n",
                          APP2: f"export const Basket = () => {LABEL}", "tests/test_orders.py": "assert 'Demo only'\n",
                          ".github/notes.yml": "Demo only\n", "apps/web/tests/orders.spec.ts": "Demo only\n"})
    heading, rows = gaps(repo)
    both = f'2 files carry the "Demo only" label: {APP2}, {APP}. Say: "Build each demo-only feature properly or remove it: {APP2}, {APP}"'
    assert heading == ["Before production: 1 open gap"] and rows == [f"- {both}"]
    assert not (tmp_path / "model-called").exists()
    # Another checkout removes the label; this checkout still holds the old file.
    push(repo, tmp_path, {APP: "export const Orders = () => null\n"})
    assert gaps(repo)[1] == [f"- {DEMO.replace(APP, APP2)}"]
    push(repo, tmp_path, {APP2: "export const Basket = () => null\n"})
    assert gaps(repo) == ([], [])


@pytest.mark.parametrize("adoption", ["new client", "earlier adopted"])
def test_3_open_gaps_show_together_and_stay_while_work_runs(repo, gh, tmp_path, adoption):
    client(repo, gh, tmp_path, adoption, sample_data=True)
    push(repo, tmp_path, {APP: LABEL, **fix("build-login")})
    rows = [f"- {SAMPLE}", f'- 1 part was built with only the light review: build-login. Say: "{light("build-login")}"',
            f"- {DEMO}"]
    assert gaps(repo) == (["Before production: 3 open gaps"], rows)
    started = repo.forge("fix", "start", "Review and test build-login in full", "--done",
                         "build-login is reviewed and tested in full", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    busy = lines(repo, "next")
    assert "Before production: 3 open gaps" in busy and [row for row in busy if row.startswith("- ")] == rows
    assert any("review-and-test-build-login" in row for row in busy)
    push(repo, tmp_path, {"forge.toml": lambda text: settings(text, sample_data=False)})
    assert gaps(repo) == (["Before production: 2 open gaps"], rows[1:])


@pytest.mark.parametrize("adoption", ["new client", "earlier adopted"])
def test_5_light_reviewed_parts_show_and_clear_when_named(repo, gh, tmp_path, adoption):
    client(repo, gh, tmp_path, adoption, sample_data=False, signed=False)
    # The fixes and the sign-off reach the remote just before the command, with no earlier fetch here.
    old_shape = fix("old-page")
    old_shape = {name: json.dumps({key: value for key, value in json.loads(text).items() if key != "fix_kind"})
                 for name, text in old_shape.items()}
    push(repo, tmp_path, {
        "docs/decisions/0001-client-signoff.md": SIGNOFF, **fix("build-login"), **old_shape,
        **fix("fix-copy", "Fix the copy", level="P1"), **fix("add-orders", status="dropped"),
        **fix("tune-search", "Tune the search", allowance=False)})
    row = f'- 2 parts were built with only the light review: build-login, old-page. Say: "{light("build-login", "old-page")}"'
    assert lines(repo, "next").count(row) == 1  # no earlier fetch in this checkout
    assert gaps(repo) == (["Before production: 1 open gap"], [row])

    # A change that landed before a part was built cannot have reviewed it.
    push(repo, tmp_path, fix("early-review", "Review and test late-part in full", level="P1"))
    push(repo, tmp_path, fix("late-part"))
    assert "late-part" in gaps(repo)[1][0]
    push(repo, tmp_path, {".factory/fixes/late-part.json": None, **fix("review-login", "x", level="P1")})
    # A full review that names build-login clears that name only, even beside build-login-2.
    push(repo, tmp_path, {**fix("review-login", "Review and test build-login in full", level="P1"),
                          **fix("build-login-2", "Build the second login, then old-page")})
    row = f'- 2 parts were built with only the light review: build-login-2, old-page. Say: "{light("build-login-2", "old-page")}"'
    assert gaps(repo) == (["Before production: 1 open gap"], [row])

    # A change with a P0 level that names old-page does not clear it; a story counts only once done.
    push(repo, tmp_path, fix("tune-search", "Review and test old-page in full", allowance=False))
    assert gaps(repo)[1] == [row]
    one = {"plans/MOVE-1.md": DOC, ".factory/stories/MOVE-1/story.json": json.dumps(
        {"status": "approved", "title": "Review and test old-page in full"})}
    push(repo, tmp_path, {**one, ".factory/stories/MOVE-1/tasks/SAVE.json": json.dumps(
        {"status": "waiting for checks", "touches": 0})}, "Finish the first part")
    assert gaps(repo)[1] == [row]
    push(repo, tmp_path, {".factory/stories/MOVE-1/tasks/SHOW.json": json.dumps(
        {"status": "merged", "touches": 1})}, 'Finish the story\n\nForge-story-done: ' + json.dumps(
        {"key": "MOVE-1", "outcome": "The parts are reviewed."}))
    assert gaps(repo) == (["Before production: 1 open gap"], [
        f'- 1 part was built with only the light review: build-login-2. Say: "{light("build-login-2")}"'])
