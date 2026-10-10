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
from test_story import GRILL, READER, claude_plan, hook, new_story, ready, worktree

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
def test_1_dependency_map_and_stage_timelines_use_the_command_data(
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
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}, {"key": "PACK"},
                                                        {"key": "PLAN"}, {"key": "IDEA"}]}))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure the client")
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    repo.path = main
    repo.git("merge", "-q", "--ff-only", "fix/configure-client")
    _land_fixture(repo)
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T10:00:00+00:00")
    packing = DOC.replace("Shoppers can save a basket", "Baskets can be packed").replace(
        "Save a basket |", "Prepare packaging |")
    ready(repo, "PACK", packing)
    new_story(repo, "PLAN", "Plan the next improvement")
    doc = DOC.replace("`tests/test_share.py` | SAVE | yes |",
                      "`tests/test_share.py` | SHOW, PACK/SAVE | yes |")
    doc = doc.replace("\nNew moving parts:",
                      "\n| EXTRA | Print a basket | Paper copy | 1 | `print.py` | "
                      "`tests/test_print.py` | none | no |\n"
                      "| BUSY | Change the basket page | Page improvement | 2 | `src/page.py` | "
                      "`tests/test_busy.py` | none | no |\n\nNew moving parts:")
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
    assert set(parts) == {"SHOP/SAVE", "SHOP/SHOW", "SHOP/SHARE", "SHOP/EXTRA", "SHOP/BUSY"}
    assert parts["SHOP/SHOW"]["waits_for"] == ["SHOP/SAVE"]
    assert parts["SHOP/SHARE"]["waits_for"] == ["SHOP/SHOW", "PACK/SAVE"]
    assert parts["SHOP/EXTRA"]["waits_for"] == [], "This unstarted part can start now"
    assert {key: part["status"] for key, part in parts.items()} == {
        "SHOP/SAVE": "Merged", "SHOP/SHOW": "Running",
        "SHOP/SHARE": "Waiting", "SHOP/EXTRA": "Can start now", "SHOP/BUSY": "Waiting"}
    assert parts["SHOP/BUSY"]["waits_for"] == ["SHOP/SHOW"], "Active scopes block starting"
    assert maps["PACK"]["parts"][0]["status"] == "Not started", "Unapproved stories cannot start"
    next_steps = repo.forge("next")
    assert next_steps.returncode == 0, next_steps.stderr
    assert "Next: forge task start SHOP/EXTRA" in next_steps.stdout
    assert "Next: forge task start PACK/SAVE" not in next_steps.stdout
    assert "Next: forge task start SHOP/BUSY" not in next_steps.stdout
    assert "SHOP/BUSY waits for SHOP/SHOW to merge first" in next_steps.stdout

    out = tmp_path / "board.html"
    rendered = repo.forge("board", "--out", str(out))
    assert rendered.returncode == 0, rendered.stderr
    page = out.read_text("utf-8")
    assert not re.search(r"\b[0-9a-f]{7,}\b", page), "SVG coordinates must not look like hashes"
    drawing = _svg(page, "Roadmap dependencies")
    titles = _titles(drawing)
    node_titles = {"Save a basket: Merged", "Show when it was saved: Running",
                   "Share a basket: Waiting", "Print a basket: Can start now",
                   "Prepare packaging: Not started"}
    assert node_titles <= titles
    assert {"Show when it was saved waits for Save a basket",
            "Share a basket waits for Show when it was saved",
            "Share a basket waits for Prepare packaging",
            "Change the basket page waits for Show when it was saved"} <= titles
    shapes = []
    for group in drawing.iter():
        if any(n.tag.rsplit("}", 1)[-1] == "title" and n.text in node_titles for n in group):
            shape = next(n for n in group if n.tag.rsplit("}", 1)[-1] in
                         ("rect", "circle", "ellipse", "polygon", "path"))
            shapes.append((shape.tag, shape.get("rx"), shape.get("stroke-dasharray")))
    assert len(set(shapes)) == 5, "Each state needs its own shape, beyond its colour and label"

    for row in (children["SHOP/SHOW"], rows["readme-greets"]):
        stages = {s["name"]: s for s in row["stages"]}
        assert {name: stages[name]["seconds"] for name in stages} == {
            "Build": 120, "Tests": 30, "Review": 60, "CI": None, "Merge": None}
        assert stages["CI"]["status"] == "running"
        timeline = _svg(page, row["title"] + " stage timeline")
        assert {"Build: 2 minutes", "Tests: 30 seconds", "Review: 1 minute",
                "CI: 1 minute; current", "Merge: unknown"} <= _titles(timeline)
        painted = " ".join(" ".join(node.itertext()) for node in timeline.iter()
                           if node.tag.rsplit("}", 1)[-1] == "text")
        assert all(label in painted for label in ("Build", "Tests", "Review", "Checks", "Merge",
                                                 "2 minutes", "30 seconds", "1 minute", "unknown", "current"))
    text = seen(out)
    assert all(section in text for section in ("Parts", "Small fixes", "How the factory is doing"))
    assert "In progress: 1 of 5 parts finished." in text
    assert len(re.findall(r"<svg\b", page)) == 3, "One roadmap map and two active-item timelines"
    assert sum(n.tag.rsplit("}", 1)[-1] == "title" and n.text ==
               "Prepare packaging: Not started" for n in drawing.iter()) == 1
    assert all("(other story)" not in title for title in titles)
    expected_counts = {"needs a spec": 1, "planning": 1, "waiting for approval": 1,
                       "building": 2, "ready to merge": 0,
                       "done": 3 if history == "adopted-v1.2.2" else 2}
    assert data["stage_counts"] == expected_counts
    # The old header mixed stories and fixes. Each labelled group now matches its JSON counts.
    for kind, counts in data["kind_stage_counts"].items():
        assert kind.capitalize() in text
        assert all(f"{name.capitalize()}: {count}" in text for name, count in counts.items())
    numbers = re.search(r'<ul class="numbers">(.*?)</ul>', page, re.S).group(1)
    assert len(re.findall(r"<li>", numbers)) == 3, "The three factory measures stay"
    # These are the shipped, script-free theme and responsive-page contracts.
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in page
    css = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
    assert "@media (prefers-color-scheme: dark)" in css
    for token in ("paper", "ink", "muted"):
        colors = re.findall(rf"--{token}:\s*(#[0-9a-f]+)", css)
        assert len(set(colors)) == 2, f"{token} has light and dark values"
    picture_css = re.search(r"\.board-picture\s*\{([^}]+)\}", css).group(1)
    assert "width: 100%" in picture_css and "color: var(--ink)" in picture_css
    assert "fill: currentColor" in css and "fill: var(--muted)" in css
    assert drawing.attrib["viewBox"].split()[:3] == ["0", "0", "260"]
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

    # The count consumes the close producer's recorded reviewed-head receipt;
    # machine-view tests own close/check production on both client histories.
    receipts = forge / "ready"
    receipts.mkdir(exist_ok=True)
    (receipts / "readme-greets.json").write_text(json.dumps({
        "review": "clean", "commit": repo.git("rev-parse", "fix/readme-greets")}), "utf-8")
    with (forge / "events.jsonl").open("a", encoding="utf-8") as events:
        events.write(json.dumps({"event": "run end", "id": "readme-greets:ci:end",
                                 "run_id": "readme-greets:ci", "item": "readme-greets",
                                 "kind": "ci", "at": "2026-10-09T10:00:00Z"}) + "\n")
    ready_counts = {**expected_counts, "building": 1, "ready to merge": 1}
    ready_page = repo.forge("board", "--out", str(out))
    assert ready_page.returncode == 0, ready_page.stderr
    assert "Ready to merge: 1" in seen(out)
    ready_json = repo.forge("board", "--json")
    assert ready_json.returncode == 0, ready_json.stderr
    assert json.loads(ready_json.stdout)["stage_counts"] == ready_counts

    # A story counts once as ready only when every remaining part is ready.
    plan_tree = worktree(repo, "story/PLAN")
    plan_doc = "\n".join(line for line in DOC.splitlines()
                         if not line.startswith(("3. ", "| SHARE |")))
    plan_doc = plan_doc.replace("`src/basket.py`", "`src/plan-save.py`").replace(
        "`src/page.py`", "`src/plan-show.py`").replace("| SAVE | yes |", "| none | yes |")
    (plan_tree / "plans/PLAN.md").write_text(plan_doc, encoding="utf-8")
    plan_read = repo.forge("read", "PLAN")
    assert plan_read.returncode == 0, plan_read.stderr
    assert hook(repo, claude_plan(claude_payload, plan_doc, cwd=plan_tree)).returncode == 0
    for tid in ("SAVE", "SHOW"):
        started = repo.forge("task", "start", f"PLAN/{tid}")
        assert started.returncode == 0, started.stderr
    part_counts = {**ready_counts, "planning": 0, "building": 2}
    for tid in ("SAVE", "SHOW"):
        (receipts / "PLAN").mkdir(exist_ok=True)
        (receipts / "PLAN" / f"{tid}.json").write_text(json.dumps({
            "review": "clean", "commit": repo.git("rev-parse", f"task/PLAN-{tid}")}), "utf-8")
        plan_json = repo.forge("board", "--json")
        assert plan_json.returncode == 0, plan_json.stderr
        if tid == "SHOW":
            part_counts = {**part_counts, "building": 1, "ready to merge": 2}
        assert json.loads(plan_json.stdout)["stage_counts"] == part_counts
    plan_next = repo.forge("next")
    assert plan_next.returncode == 0, plan_next.stderr
    assert all(f"PLAN/{tid} is ready and waiting for someone to merge it." in plan_next.stdout
               for tid in ("SAVE", "SHOW"))
    assert "Next: merge its pull request, then forge next" in plan_next.stdout
    plan_page = repo.forge("board", "--out", str(out))
    assert plan_page.returncode == 0, plan_page.stderr
    # One ready story and one ready fix remain separate in the labelled header.
    assert seen(out).count("Ready to merge: 1") == 2 and "Building: 1" in seen(out)

    # Task/fix checkouts retain an equally recent inherited story record, but
    # the owning story's live task table is what next and board must both read.
    table_edit = doc.replace("SHOW, PACK/SAVE | yes |", "SAVE, PACK/SAVE | yes |")
    table_edit = table_edit.replace("\nNew moving parts:",
                                    "\n| ADDED | Export a basket | A portable copy | 1 | "
                                    "`src/export.py` | `tests/test_export.py` | none | no |"
                                    "\n\nNew moving parts:")
    table_edit = re.sub(r"^(\| )(SAVE|SHOW|SHARE|EXTRA|BUSY|ADDED)( \|)",
                        r"\1`\2`\3", table_edit, flags=re.M)
    (story_tree / "plans/SHOP.md").write_text(table_edit, encoding="utf-8")
    table_next = repo.forge("next")
    assert table_next.returncode == 0, table_next.stderr
    assert "Next: forge read SHOP" in table_next.stdout
    assert "Next: forge task start SHOP/EXTRA" not in table_next.stdout
    assert "Next: forge task start SHOP/ADDED" not in table_next.stdout
    table_json = repo.forge("board", "--json")
    assert table_json.returncode == 0, table_json.stderr
    edited_map = next(m for m in json.loads(table_json.stdout)["dependency_maps"] if m["id"] == "SHOP")
    edited_parts = {p["id"]: p for p in edited_map["parts"]}
    assert set(edited_parts) == {*parts, "SHOP/ADDED"}
    assert edited_parts["SHOP/SHARE"]["waits_for"] == ["SHOP/SAVE", "PACK/SAVE"]
    assert {key: edited_parts[key]["status"] for key in
            ("SHOP/SAVE", "SHOP/SHOW", "SHOP/EXTRA", "SHOP/ADDED")} == {
        "SHOP/SAVE": "Merged", "SHOP/SHOW": "Running",
        "SHOP/EXTRA": "Not started", "SHOP/ADDED": "Not started"}
    table_page = repo.forge("board", "--out", str(out))
    assert table_page.returncode == 0, table_page.stderr
    edited_drawing = _svg(out.read_text("utf-8"), "Roadmap dependencies")
    edited_titles = _titles(edited_drawing)
    assert {"Export a basket: Not started", "Save a basket: Merged",
            "Show when it was saved: Running", "Share a basket waits for Save a basket"} <= edited_titles
    assert "Share a basket waits for Show when it was saved" not in edited_titles
    assert all("Unknown part" not in title for title in edited_titles)
    assert sum(n.tag.rsplit("}", 1)[-1] == "title" and n.text ==
               "Save a basket: Merged" for n in edited_drawing.iter()) == 1

    # An edited approved plan requires another read before an idle part starts.
    changed = doc.replace("Shoppers can save a basket and come back to it later.",
                          "Shoppers can save a basket and return tomorrow.")
    (story_tree / "plans/SHOP.md").write_text(changed, encoding="utf-8")
    reread = repo.forge("next")
    assert reread.returncode == 0, reread.stderr
    assert "Next: forge read SHOP" in reread.stdout
    assert "Next: forge task start SHOP/EXTRA" not in reread.stdout
    after_change = repo.forge("board", "--json")
    assert after_change.returncode == 0, after_change.stderr
    shop_map = next(m for m in json.loads(after_change.stdout)["dependency_maps"] if m["id"] == "SHOP")
    assert next(p for p in shop_map["parts"] if p["id"] == "SHOP/EXTRA")["status"] == "Not started"
