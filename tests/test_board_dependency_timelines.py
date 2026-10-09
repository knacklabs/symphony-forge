"""The command board restores dependency pictures and recorded stage timelines."""
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET

import pytest

from conftest import ROOT, _install
from test_board import DOC, seen
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_story import GRILL, READER, claude_plan, hook, ready, worktree

STORY = "FIX-BOARD-VISUALS"


def _land_fixture(repo):
    """The third-party merge supplies default-branch history without a client main push."""
    remote = repo.git("remote", "get-url", "origin")
    repo.git("--git-dir", remote, "fetch", "-q", "--no-tags", repo.path.as_posix(), "main:main")
    repo.git("fetch", "-q", "origin")


def _client(repo, gh, tmp_path, history):
    if history == "new":
        client = _new_repo(repo, gh, tmp_path)
        initialized = repo.forge("init", cwd=client)
        assert initialized.returncode == 0, initialized.stderr
        repo.path = client
        _land_fixture(repo)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        _land_fixture(repo)
        repo.git("switch", "-qc", "fix/upgrade-client")
        repo.write(".factory/fixes/upgrade-client.json", json.dumps({
            "kind": "fix", "branch": "fix/upgrade-client", "why": "Upgrade Forge",
            "done_when": "The client uses this release", "status": "started"}))
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        upgraded = repo.forge("sync")
        assert upgraded.returncode == 0, upgraded.stderr
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade Forge")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade-client")
        _land_fixture(repo)


def _svg(page, label):
    drawings = [ET.fromstring(raw) for raw in re.findall(r"<svg\b.*?</svg>", page, re.S)]
    matches = [drawing for drawing in drawings if drawing.attrib.get("aria-label") == label]
    assert len(matches) == 1, f"Expected one accessible inline picture: {label}"
    assert matches[0].attrib.get("role") == "img"
    return matches[0]


def _titles(svg):
    return {node.text for node in svg.iter() if node.tag.rsplit("}", 1)[-1] == "title"}


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_dependency_map_and_stage_timelines_use_the_command_data(
        repo, gh, tmp_path, claude_payload, monkeypatch, history):
    # Coverage owns the renderer boundary. Machine-view tests own production of these
    # records; plain-text run fixtures give deterministic visible durations here.
    _client(repo, gh, tmp_path, history)
    configured = repo.forge("fix", "start", "Configure the client", "--done", "The client is configured",
                            "--slug", "configure-client")
    assert configured.returncode == 0, configured.stderr
    main = repo.path
    repo.path = worktree(repo, "fix/configure-client")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n{GRILL}')
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure the client")
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    repo.path = main
    repo.git("merge", "-q", "--ff-only", "fix/configure-client")
    _land_fixture(repo)
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T10:00:00+00:00")
    doc = DOC.replace("`tests/test_share.py` | SAVE | yes |",
                      "`tests/test_share.py` | SHOW | yes |")
    doc = doc.replace("\nNew moving parts:",
                      "\n| EXTRA | Print a basket | Paper copy | 1 | `print.py` | "
                      "`tests/test_print.py` | none | no |\n\nNew moving parts:")
    story_tree = ready(repo, "SHOP", doc)
    assert hook(repo, claude_plan(claude_payload, doc, cwd=story_tree)).returncode == 0

    def task_state(tid, status):
        branch = f"task/SHOP-{tid}"
        folder = tmp_path / f"part-{tid}"
        repo.git("worktree", "add", "-q", "-b", branch, str(folder), "story/SHOP")
        state = folder / f".factory/stories/SHOP/tasks/{tid}.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"branch": branch, "status": status, "round": 1,
                                    "steps": [{"step": "start", "at": "2026-10-09T09:00:00Z"}]}),
                         encoding="utf-8")
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Start the part", cwd=folder)
        return branch

    save = task_state("SAVE", "working")
    accepted = repo.forge("fix", "start", "Accept the saved basket", "--done", "The basket is accepted",
                         "--slug", "accept-basket")
    assert accepted.returncode == 0, accepted.stderr
    accept_tree = worktree(repo, "fix/accept-basket")
    repo.git("merge", "-q", "--squash", save, cwd=accept_tree)
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-09-20T10:00:00+00:00")
    repo.git("commit", "-qm", "Accept the saved basket", cwd=accept_tree)
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    repo.git("merge", "-q", "--ff-only", "fix/accept-basket")
    _land_fixture(repo)
    task_state("SHOW", "working")
    fixed = repo.forge("fix", "start", "Readme greets new readers", "--done", "Readers see a greeting",
                       "--slug", "readme-greets")
    assert fixed.returncode == 0, fixed.stderr
    records = []
    for item in ("SHOP/SHOW", "readme-greets"):
        for step, seconds, outcome in (("worker round", 120, "completed"),
                                       ("test run", 30, "completed"), ("review", 60, "clean")):
            records.append({"item": item, "round": 1, "step": step, "seconds": seconds,
                            "start": "2026-10-09T09:00:00Z", "outcome": outcome})
    forge = repo.path / ".git/forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "timings.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), "utf-8")
    (forge / "events.jsonl").write_text("".join(json.dumps({
        "event": "run start", "id": item + ":ci", "item": item, "round": 1,
        "kind": "ci", "at": "2026-10-09T09:59:00Z"}) + "\n"
        for item in ("SHOP/SHOW", "readme-greets")), "utf-8")

    machine = repo.forge("board", "--json")
    assert machine.returncode == 0, machine.stderr
    data = json.loads(machine.stdout)
    rows = {r["id"]: r for r in data["items"]}
    children = {r["id"]: r for r in rows["SHOP"]["children"]}
    assert set(children) == {"SHOP/SHOW"}, "Old merged parts stay outside active item rows"
    maps = {r["id"]: r for r in data["dependency_maps"]}
    parts = {r["id"]: r for r in maps["SHOP"]["parts"]}
    assert set(parts) == {"SHOP/SAVE", "SHOP/SHOW", "SHOP/SHARE", "SHOP/EXTRA"}
    assert parts["SHOP/SHOW"]["waits_for"] == ["SHOP/SAVE"]
    assert parts["SHOP/SHARE"]["waits_for"] == ["SHOP/SHOW"]
    assert {key: part["status"] for key, part in parts.items()} == {
        "SHOP/SAVE": "Merged", "SHOP/SHOW": "Running",
        "SHOP/SHARE": "Waiting", "SHOP/EXTRA": "Not started"}

    out = tmp_path / "board.html"
    rendered = repo.forge("board", "--out", str(out))
    assert rendered.returncode == 0, rendered.stderr
    page = out.read_text("utf-8")
    drawing = _svg(page, "Shoppers can save a basket dependencies")
    titles = _titles(drawing)
    node_titles = {"Save a basket: Merged", "Show when it was saved: Running",
                   "Share a basket: Waiting", "Print a basket: Not started"}
    assert node_titles <= titles
    assert {"Show when it was saved waits for Save a basket",
            "Share a basket waits for Show when it was saved"} <= titles
    shapes = []
    for group in drawing.iter():
        if any(n.tag.rsplit("}", 1)[-1] == "title" and n.text in node_titles for n in group):
            shape = next(n for n in group if n.tag.rsplit("}", 1)[-1] in
                         ("rect", "circle", "ellipse", "polygon", "path"))
            shapes.append((shape.tag, shape.get("rx"), shape.get("stroke-dasharray")))
    assert len(set(shapes)) == 4, "Each state needs its own shape, beyond its colour and label"

    for row in (children["SHOP/SHOW"], rows["readme-greets"]):
        stages = {s["name"]: s for s in row["stages"]}
        assert {name: stages[name]["seconds"] for name in stages} == {
            "Build": 120, "Tests": 30, "Review": 60, "CI": None, "Merge": None}
        assert stages["CI"]["status"] == "running"
        timeline = _svg(page, row["title"] + " stage timeline")
        assert {"Build: 2 minutes", "Tests: 30 seconds", "Review: 1 minute",
                "CI: unknown; current", "Merge: unknown"} <= _titles(timeline)
        painted = " ".join(" ".join(node.itertext()) for node in timeline.iter()
                           if node.tag.rsplit("}", 1)[-1] == "text")
        assert all(label in painted for label in ("Build", "Tests", "Review", "Checks", "Merge",
                                                 "2 minutes", "30 seconds", "1 minute", "unknown", "current"))
    text = seen(out)
    assert all(section in text for section in ("Parts", "Small fixes", "How the factory is doing"))
    assert "<script" not in page.lower()
    assert not re.search(r"<(?:img|link|script)\b|<svg[^>]*\bsrc=|<image\b|<use\b", page, re.I)

    # A worker remains live while it runs tests; the narrower current activity wins.
    with (forge / "events.jsonl").open("a", encoding="utf-8") as events:
        for kind in ("work", "test"):
            events.write(json.dumps({"event": "run start", "id": "show:" + kind,
                                     "item": "SHOP/SHOW", "round": 1, "kind": kind,
                                     "at": "2026-10-09T10:00:00Z"}) + "\n")
    assert repo.forge("board", "--out", str(out)).returncode == 0
    nested = _titles(_svg(out.read_text("utf-8"), "Show when it was saved stage timeline"))
    assert "Tests: 30 seconds; current" in nested
    assert "Build: 2 minutes; current" not in nested
