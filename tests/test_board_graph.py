"""The board's dependency graph: every roadmap story, parts in columns by when they can start,
arrows for waits across stories, running marks, done folds, no-plan boxes and a Fixes row."""
import json
import re
import subprocess
import xml.etree.ElementTree as ET

import pytest

from conftest import REAL_UV
from test_board_dependency_timelines import _configured, _land_fixture
from test_story import claude_plan, hook, new_story, worktree

STORY = "FORGE-BOARD-2"
SORT = "Sort the list by when each item was first added to it and who added it"


def _doc(title, rows):
    table = "\n".join(f"| {tid} | {name} | {name} | 1 | `src/{tid.lower()}-{n}.py` | "
                      f"`tests/test_{tid.lower()}_{n}.py` | {after} | no |"
                      for n, (tid, name, after) in enumerate(rows))
    return (f"# {title}\n\n## What changes for you\n\n{title}.\n\n## Why\n\nAsked for.\n\n"
            "## Done when\n\n1. It works.\n\n## Tasks\n\n| ID | Name | What it delivers | Covers | Scope | Tests | "
            f"After | User-facing |\n|---|---|---|---|---|---|---|---|\n{table}\n\nNew moving parts: none\n\n"
            "## Risks\n\nRisks: none\n\n## Notes\n")


def _story(repo, key, title, rows, read=True):
    tree = new_story(repo, key, title)
    doc = _doc(title, rows)
    (tree / f"plans/{key}.md").write_text(doc, "utf-8")
    if read:
        assert repo.forge("read", key).returncode == 0
    return tree, doc


def _node(svg, title):
    """The drawn group whose <title> starts with this part's title."""
    for group in svg.iter("{http://www.w3.org/2000/svg}g"):
        named = group.find("{http://www.w3.org/2000/svg}title")
        if named is not None and named.text.startswith(title + ":"):
            return group
    raise AssertionError(title)


def _x(group):
    return float(re.match(r"translate\(([\d.]+)", group.get("transform"))[1])


def _painted(group):
    return " ".join(t.strip() for t in group.itertext()
                    if t.strip() and t not in [n.text for n in group.iter("{http://www.w3.org/2000/svg}title")])


@pytest.mark.timeout(600)
@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_11_dependency_graph(repo, gh, tmp_path, claude_payload, monkeypatch, history):
    _configured(repo, gh, tmp_path, history, ("ALPHA", "BETA", "GAMMA", "DELTA", "IDEA", "NOTE", "LATER"))
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T10:00:00+00:00")
    alpha, doc = _story(repo, "ALPHA", "Shoppers keep a list", [
        ("T0", "Store the list", "none"), ("T1", "Draw the list", "none"),
        ("T2", SORT, "T1"), ("T3", "Print the list", "none")])
    assert hook(repo, claude_plan(claude_payload, doc, cwd=alpha)).returncode == 0
    _story(repo, "BETA", "Shoppers share a list", [("T1", "Send the list", "ALPHA/T2")])
    # A wait cycle across two stories: neither can start before the other.
    _story(repo, "GAMMA", "Couriers plan a route", [("T1", "Map the route", "DELTA/T1")], read=False)
    # A wait on a part no plan names counts as no wait, and the label says why.
    _story(repo, "DELTA", "Couriers book a slot", [("T1", "Book the slot", "GAMMA/T1"),
                                                     ("T2", "Confirm the slot", "ALPHA/T9")], read=False)
    new_story(repo, "IDEA", "Shoppers get ideas")  # made by forge story new: an untouched template

    def start(tid):
        branch, folder = f"task/ALPHA-{tid}", tmp_path / f"part-{tid}"
        repo.git("worktree", "add", "-q", "-b", branch, str(folder), "story/ALPHA")
        state = folder / f".factory/stories/ALPHA/tasks/{tid}.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"branch": branch, "status": "working", "round": 1,
                                     "steps": [{"step": "start", "at": "2026-10-09T09:00:00Z"}]}), "utf-8")
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Start the part", cwd=folder)
        return branch, folder

    # One finished part, carried to main by a fix (the same shortcut the timeline test takes).
    finished, _ = start("T0")
    assert repo.forge("fix", "start", "Land the stored list", "--done", "It is landed",
                      "--slug", "land-list").returncode == 0
    land = worktree(repo, "fix/land-list")
    repo.git("merge", "-q", "--squash", finished, cwd=land)
    repo.git("commit", "-qm", "Land the stored list", cwd=land)
    repo.git("merge", "-q", "--ff-only", "fix/land-list")
    _land_fixture(repo)
    start("T3")
    _, sorting = start("T2")
    stacked = repo.forge("fix", "start", "Sort ignores case", "--done", "Case is ignored",
                         "--slug", "sort-case", cwd=sorting)
    assert stacked.returncode == 0, stacked.stderr
    running = repo.forge("fix", "start", "Readme greets new readers", "--done", "Readers see a greeting",
                         "--slug", "readme-greets")
    assert running.returncode == 0, running.stderr
    forge = repo.path / ".git/forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "events.jsonl").write_text("".join(json.dumps({
        "event": "run start", "id": item + ":ci", "item": item, "round": 1, "kind": "ci",
        "at": "2026-10-09T09:59:00Z"}) + "\n" for item in ("ALPHA/T3", "readme-greets")), "utf-8")

    machine = repo.forge("board", "--json")
    assert machine.returncode == 0, machine.stderr
    listed = json.loads(machine.stdout)["dependency_maps"]
    assert [entry["id"] for entry in listed if entry.get("kind") != "fixes"] == [
        "ALPHA", "BETA", "GAMMA", "DELTA", "IDEA", "NOTE", "LATER"], "Roadmap order"
    maps = {entry["id"]: entry for entry in listed}
    columns = {part["id"]: part.get("column") for entry in maps.values() for part in entry["parts"]}
    assert {k: columns[k] for k in ("ALPHA/T1", "ALPHA/T3", "ALPHA/T2", "BETA/T1")} == {
        "ALPHA/T1": 0, "ALPHA/T3": 0, "ALPHA/T2": 1, "BETA/T1": 2}
    assert columns["ALPHA/T0"] is None and maps["ALPHA"]["done"] == 1
    assert columns["GAMMA/T1"] == columns["DELTA/T1"] == columns["DELTA/T2"] == 0
    assert [maps[k]["planned"] for k in ("IDEA", "NOTE", "LATER")] == [False] * 3
    assert all(maps[k]["planned"] for k in ("ALPHA", "BETA", "GAMMA", "DELTA"))
    fixes = next(entry for entry in maps.values() if entry.get("kind") == "fixes")
    open_fixes = {part["id"]: part for part in fixes["parts"]}
    assert set(open_fixes) == {"sort-case", "readme-greets"}, "The merged fixes are left out"
    assert {part["column"] for part in open_fixes.values()} == {0}
    assert open_fixes["readme-greets"]["running"] and not open_fixes["sort-case"]["running"]
    assert open_fixes["sort-case"]["started_on"] == "ALPHA/T2"

    out = tmp_path / "board.html"
    assert repo.forge("board", "--out", str(out)).returncode == 0
    page = out.read_text("utf-8")
    svg = ET.fromstring(re.search(r'<svg\b[^>]*aria-label="Roadmap dependencies".*?</svg>', page, re.S)[0])
    titles = [t.text for t in svg.iter("{http://www.w3.org/2000/svg}title")]
    assert _x(_node(svg, "Draw the list")) == _x(_node(svg, "Print the list")) < _x(_node(svg, SORT))
    assert _x(_node(svg, SORT)) < _x(_node(svg, "Send the list"))
    assert f"Send the list waits for {SORT}" in titles
    assert "running" in _painted(_node(svg, "Print the list"))
    assert "Store the list" not in " ".join(titles) and "1 done" in _painted(svg)
    assert len([t for t in titles if t.startswith("No plan yet:")]) == 3
    greets, case = _node(svg, "Readme greets new readers"), _node(svg, "Sort ignores case")
    assert _x(greets) == _x(case) == _x(_node(svg, "Draw the list"))
    assert "running" in _painted(greets) and f"started on {SORT}" in _painted(case), "The whole part name shows"
    assert not any("Sort ignores case" in t and "waits for" in t for t in titles)
    assert "Land the stored list" not in " ".join(titles)
    assert _x(_node(svg, "Map the route")) == _x(_node(svg, "Book the slot"))
    assert "waits on each other" in _painted(_node(svg, "Map the route"))
    assert "waits on a part no plan names" in _painted(_node(svg, "Confirm the slot"))
    assert not any("Confirm the slot waits for" in t for t in titles)
    assert any(t.startswith("No plan yet: Shoppers get ideas") for t in titles)
    if history == "new":
        _browser(out)


def _browser(page):
    """In real Chrome at 1440 and 390 wide: the graph fills its slot at laptop width at its own
    size (no stretching), no label overlaps another, no arrow runs through a label, and only the
    graph's own focusable box scrolls sideways when narrow."""
    script = """
import sys
from playwright.sync_api import sync_playwright
CHECK = '''() => {
  const svg = document.querySelector('svg[aria-label="Roadmap dependencies"]');
  const box = svg.getBoundingClientRect(), slot = svg.parentElement.getBoundingClientRect();
  const rects = [...svg.querySelectorAll('text')].map(t => t.getBoundingClientRect()).filter(r => r.width);
  let overlaps = 0, crossings = 0;
  rects.forEach((a, i) => rects.slice(i + 1).forEach(b => {
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) overlaps++; }));
  for (const path of svg.querySelectorAll('.dependency-edge')) {
    const m = path.getScreenCTM();
    for (let d = 0; d < path.getTotalLength(); d += 2) {
      const p = path.getPointAtLength(d).matrixTransform(m);
      if (rects.some(r => p.x > r.left + 1 && p.x < r.right - 1 && p.y > r.top + 1 && p.y < r.bottom - 1)) crossings++;
    }
  }
  return {scale: box.width / svg.viewBox.baseVal.width, fill: box.width / slot.width, overlaps, crossings,
          page: document.documentElement.scrollWidth <= window.innerWidth,
          focusable: svg.parentElement.tabIndex === 0, label: svg.parentElement.getAttribute('aria-label')};
}'''
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for width in (1440, 390):
            page = browser.new_page(viewport={'width': width, 'height': 900})
            page.goto(sys.argv[1])
            seen = page.evaluate(CHECK)
            assert seen['scale'] == 1, seen
            assert seen['overlaps'] == 0 and seen['crossings'] == 0, seen
            assert seen['page'] and seen['focusable'] and seen['label'], seen
            if width == 1440:
                assert seen['fill'] > 0.97, seen
            page.close()
    finally:
        browser.close()
"""
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                            "playwright==1.55.0", "python", "-c", script, page.resolve().as_uri()],
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert shown.returncode == 0, shown.stdout + shown.stderr
