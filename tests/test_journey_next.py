"""`forge next` names the repository journey step and each wait from recorded facts.

Test audit:
1. Protect the text command's step and wait lines while keeping JSON's existing line unchanged.
2. A regression could omit a step, misclassify a journey state, hide a live wait, or add waits to JSON.
3. No existing command test covers the repository-level step; existing worker, review, CI and read
   tests do not own the combined plain-text contract or capacity retry timestamp.
4. These tests use Forge commands and real git/run records; no production-only seam is needed.
5. Session-held rounds have a separate machine-entry lifecycle, so the existing read and build
   session tests check those inserted lines at their own command boundary.
"""
from __future__ import annotations

import base64
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client as _adopted_client
from test_board_status_and_times import _fix, _live_work_lock, _records
from test_codex_worker import _codex_repo, sdk_data  # noqa: F401
from test_machine_views import github, pull
from test_setup import _fresh_client
from test_story import DOC, approved_constitution

STORY = "FORGE-JOURNEY-1"
NOW = "2026-10-09T12:00:00+00:00"

pytestmark = pytest.mark.platform


def _publish(repo, client: Path, message: str) -> None:
    # These fixture commits represent changes that reached main through a merge elsewhere.
    no_hooks = client.parent / "fixture-no-hooks"
    no_hooks.mkdir(exist_ok=True)
    hook_setting = f"core.hooksPath={no_hooks.as_posix()}"
    repo.git("add", "-A", cwd=client)
    repo.git("-c", hook_setting, "commit", "-q", "-m", message, cwd=client)
    repo.git("-c", hook_setting, "push", "-q", "origin", "main", cwd=client)


def _step(repo, client: Path, number: int, name: str) -> str:
    result = repo.forge("next", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = f"Step {number} of 7: {name}."
    assert result.stdout.splitlines()[0] == expected
    return result.stdout


def _png() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jc8sAAAAASUVORK5CYII=")


@pytest.mark.timeout(600)
def test_3_forge_next_names_the_journey_step(repo, gh, tmp_path):
    without_config = repo.forge("next")
    assert without_config.returncode == 0, without_config.stderr
    assert not without_config.stdout.splitlines()[0].startswith("Step ")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Identify the Forge source repo")
    repo.git("push", "-q", "origin", "main")
    source = repo.forge("next")
    assert source.returncode == 0, source.stderr
    assert source.stdout.splitlines()[0] == "Step 5 of 7: build."

    _adopted_client(repo, gh, tmp_path, "adopted-v1.2.2")
    adopted = repo.forge("next")
    assert adopted.returncode == 0, adopted.stderr
    assert adopted.stdout.splitlines()[0] == "Step 5 of 7: build."

    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert _step(repo, client, 1, "ideas and client notes")

    machine = repo.forge("next", "--json", cwd=client)
    assert machine.returncode == 0, machine.stderr
    assert not json.loads(machine.stdout)["next"]["line"].startswith("Step ")
    context = repo.forge("hook", "context", cwd=client)
    assert context.returncode == 0, context.stderr
    assert context.stdout.splitlines()[0] == "Step 1 of 7: ideas and client notes."

    (client / "docs/context/notes.md").parent.mkdir(parents=True, exist_ok=True)
    (client / "docs/context/notes.md").write_text("The client needs a simple order list.\n", "utf-8")
    _step(repo, client, 1, "ideas and client notes")
    _publish(repo, client, "Record client notes")
    _step(repo, client, 2, "brief")

    brief_path = client / "docs/product/BRIEF.md"
    brief_path.write_text(
        "# Brief\n\n## Summary\nSalespeople track customer orders.\n\n"
        "## Users\n- Salespeople review orders.\n\n"
        "## Things it keeps track of\n- Order: customer and status.\n",
        encoding="utf-8")
    _publish(repo, client, "Write the client brief")
    _step(repo, client, 3, "canvas design")

    prototype = client / "docs/design/prototype"
    prototype.mkdir(parents=True)
    (prototype / "screen.png").write_bytes(_png())
    (client / "PRODUCT.md").write_text("# Order book\n\nSalespeople track orders.\n", "utf-8")
    _publish(repo, client, "Save the prototype canvas")
    design_tree = repo.git("rev-parse", "HEAD:docs/design/prototype", cwd=client)
    (client / "docs/decisions/0001-prototype-design.md").write_text(
        f"---\nstatus: accepted\ndesign_tree: {design_tree}\n---\n\n# Prototype design\n",
        encoding="utf-8")
    _publish(repo, client, "Approve the prototype canvas")
    _step(repo, client, 4, "sign-off")

    (client / "docs/decisions/0002-client-signoff.md").write_text(
        "---\nstatus: accepted\n---\n\n# Client sign-off\n", encoding="utf-8")
    _publish(repo, client, "Record client sign-off")
    _step(repo, client, 5, "build")

    # A client can start its first story after sign-off and the app constitution are accepted.
    approved_constitution(repo, client)
    (client / "plans/roadmap.json").write_text(
        json.dumps({"items": [{"key": "JOURNEY"}]}, indent=2) + "\n", "utf-8")
    _publish(repo, client, "Plan the first story")
    started = repo.forge("story", "new", "JOURNEY", "Track client progress", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    worktrees = repo.git("worktree", "list", "--porcelain", cwd=client)
    story_tree = next(Path(line.removeprefix("worktree ")) for block in worktrees.split("\n\n")
                      if "branch refs/heads/story/JOURNEY" in block
                      for line in block.splitlines() if line.startswith("worktree "))
    state_path = story_tree / ".factory/stories/JOURNEY/story.json"
    done = json.loads(state_path.read_text("utf-8"))
    done["status"] = "done"
    main_state = client / ".factory/stories/JOURNEY/story.json"
    main_state.parent.mkdir(parents=True, exist_ok=True)
    main_state.write_text(json.dumps(done, indent=2) + "\n", encoding="utf-8")
    _publish(repo, client, "Record the finished first story")
    _step(repo, client, 6, "deploy on Mainline")

    brief = brief_path.read_text("utf-8").rstrip()
    brief_path.write_text(brief + "\n\n## Demo\n- Address: https://demo.example\n", "utf-8")
    _publish(repo, client, "Record the live demo address")
    _step(repo, client, 7, "run and improve")
    started_fix = repo.forge("fix", "start", "Keep the journey current", "--done",
                             "The journey line stays useful", "--kind", "mechanical",
                             "--slug", "journey-step", cwd=client)
    assert started_fix.returncode == 0, started_fix.stdout + started_fix.stderr
    _step(repo, client, 5, "build")


def _state(folder: Path, slug: str, **updates) -> Path:
    path = folder / f".factory/fixes/{slug}.json"
    state = json.loads(path.read_text("utf-8"))
    state.update(updates)
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def _pr(repo, number: int, slug: str, status: str, *, started: str | None = None,
        created: str | None = None):
    result = pull(number, f"fix/{slug}", None, None)
    result["headRefOid"] = repo.git("rev-parse", f"fix/{slug}")
    check = result["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][0]
    check.update(status=status, conclusion=None)
    check.pop("startedAt", None)
    check.pop("createdAt", None)
    if started:
        check["startedAt"] = started
    if created:
        check["createdAt"] = created
    return result


def _install_prs(gh, prs) -> None:
    github(gh, prs)
    listing = [{**pr, "state": "OPEN"} for pr in prs]
    gh.respond("pr", "list", "--state", "all", stdout=json.dumps(listing))
    gh.respond("pr", "list", "--state", "open", stdout=json.dumps(listing))


@pytest.mark.timeout(600)
def test_4_forge_next_says_what_each_running_item_waits_on(
        repo, gh, tmp_path, monkeypatch, sdk_data, claude_session):
    original = repo.path
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.path = client
    monkeypatch.setenv("FORGE_NOW", NOW)
    gh.respond("pr", "list", "--state", "all", stdout="[]")
    gh.respond("pr", "list", "--state", "open", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps(
        {"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    (client / "docs/decisions/0001-client-signoff.md").write_text(
        "---\nstatus: accepted\n---\n\n# Client sign-off\n", encoding="utf-8")
    _publish(repo, client, "Record client sign-off")
    approved_constitution(repo, client)

    review_folder = _fix(repo, slug="a-review", status="fixing", round=1)
    findings = [{"priority": "P1", "title": title, "file": "src/app.py", "line": 1,
                 "required_done_when": "The visible wait explains its reason."}
                for title in ("A", "B")]
    _state(review_folder, "a-review", review={"blocking_level": "P1", "findings": findings,
                                               "dismissals": []},
           steps=[{"step": "review", "at": "2026-10-09T11:50:00Z"}])
    _records(repo, "events.jsonl", [
        {"event": "run start", "id": "review-run", "item": "a-review", "kind": "work",
         "round": 1, "at": "2026-10-09T11:54:00Z"}])
    review_lock = _live_work_lock(repo, "a-review")

    output = repo.forge("next").stdout.splitlines()
    review_status = "A worker is building The fix a-review."
    review_index = output.index(review_status)
    assert output[review_index + 1] == (
        "Review round 1: 2 problems found (A; B). The worker is fixing them, 6 minutes so far.")
    machine = repo.forge("next", "--json")
    assert machine.returncode == 0, machine.stderr
    assert json.loads(machine.stdout)["next"]["line"] == review_status

    _fix(repo, slug="b-worker", status="working", round=1)
    _records(repo, "events.jsonl", [
        {"event": "run start", "id": "review-run", "item": "a-review", "kind": "work",
         "round": 1, "at": "2026-10-09T11:54:00Z"},
        {"event": "run start", "id": "worker-run", "item": "b-worker", "kind": "work",
         "round": 1, "at": "2026-10-09T11:54:00Z"}])
    _live_work_lock(repo, "b-worker")
    worker_lines = repo.forge("next").stdout.splitlines()
    worker_status = "A worker is building The fix b-worker."
    assert worker_lines[worker_lines.index(worker_status) + 1] == (
        "The worker is building it, 6 minutes so far.")

    # Review text names the first three problems and says how many more remain.
    _state(review_folder, "a-review", review={"blocking_level": "P1", "findings": [
        {**findings[0], "title": title} for title in ("A", "B", "C", "D")],
        "dismissals": []})
    review_lock.unlink()
    truncated = repo.forge("next").stdout.splitlines()
    truncated_status = truncated.index("Close stopped on The fix a-review: A; B; C; D.")
    assert truncated[truncated_status + 1] == "Review round 1: 4 problems found (A; B; C; and 1 more)."

    _fix(repo, slug="c-queued", status="waiting for checks")
    _fix(repo, slug="d-running", status="waiting for checks")
    _fix(repo, slug="e-unknown-time", status="waiting for checks")
    prs = [
        _pr(repo, 1, "c-queued", "QUEUED", created="2026-10-09T11:48:00Z"),
        _pr(repo, 2, "d-running", "IN_PROGRESS", started="2026-10-09T11:48:00Z",
            created="2026-10-09T11:40:00Z"),
        _pr(repo, 3, "e-unknown-time", "QUEUED"),
    ]
    _install_prs(gh, prs)
    ci = repo.forge("next")
    assert ci.returncode == 0, ci.stderr
    lines = ci.stdout.splitlines()
    assert lines[lines.index("The fix c-queued is waiting for its checks.") + 1] == (
        "Waiting for a CI runner: queued 12 minutes.")
    assert lines[lines.index("The fix d-running is waiting for its checks.") + 1] == (
        "CI checks are running, 12 minutes so far.")
    assert lines[lines.index("The fix e-unknown-time is waiting for its checks.") + 1] == (
        "Waiting for a CI runner: queued.")

    _fix(repo, slug="z-empty", status="started")
    no_wait = repo.forge("next").stdout.splitlines()
    empty_status = "The fix z-empty is started; its worker hasn't run yet."
    assert no_wait[no_wait.index(empty_status) + 1] == "Next: forge work z-empty"

    # Three real reader notes remain to answer on the default branch.
    read_doc = DOC.replace(
        re.search(r"Design: docs/design/baskets/ \([^)]+\)", DOC)[0],
        "Design: none (the plan changes no screens)").replace(
            "| SHOW | Show the saved time | The page shows the time | 2 | `src/page.py` | `tests/test_page.py` | SAVE | yes |",
            "| SHOW | Show the saved time | The page shows the time | 2 | `src/page.py` | `tests/test_page.py` | SAVE | no |")
    (client / "plans/SHOP.md").write_text(read_doc, encoding="utf-8")
    (client / ".factory/stories/SHOP/story.json").parent.mkdir(parents=True, exist_ok=True)
    (client / ".factory/stories/SHOP/story.json").write_text(
        json.dumps({"status": "planning", "title": "Shoppers can save a basket"}), "utf-8")
    (client / "plans/SHOP.read.md").write_text(
        "---\nround: 1\npassed: no\n---\n\n## Round 1\n\n"
        "1. Saving needs sign-in first.\n2. The page time has no format.\n3. The list hides the total.\n",
        encoding="utf-8")
    _publish(repo, client, "Record the cold read notes")
    cold = repo.forge("next")
    assert cold.returncode == 0, cold.stderr
    cold_lines = cold.stdout.splitlines()
    finding = next(i for i, line in enumerate(cold_lines)
                   if line.startswith("Planning Shoppers can save a basket: round 1"))
    assert cold_lines[finding + 1] == "Cold read round 1 of 2: 3 notes to answer."

    # An earlier-adopted client follows the same CI wait path with its own recorded check.
    repo.path = original
    _adopted_client(repo, gh, tmp_path, "adopted-v1.2.2")
    monkeypatch.setenv("FORGE_NOW", NOW)
    _fix(repo, slug="adopted-checks", status="waiting for checks")
    pr = _pr(repo, 4, "adopted-checks", "QUEUED", created="2026-10-09T11:48:00Z")
    _install_prs(gh, [pr])
    adopted = repo.forge("next")
    assert adopted.returncode == 0, adopted.stderr
    assert "Waiting for a CI runner: queued 12 minutes." in adopted.stdout

    # Codex's own retry record drives the capacity line only until its recorded retry time.
    repo.path = original
    approved_constitution(repo)
    no_hooks = original.parent / "fixture-no-hooks"
    no_hooks.mkdir(exist_ok=True)
    repo.git("config", "core.hooksPath", no_hooks.as_posix(), cwd=original)
    _codex_repo(repo, monkeypatch, sdk_data, client=True)
    monkeypatch.setenv("FORGE_NOW", NOW)
    monkeypatch.setenv("STUB_CODEX_OVERLOADED", "1")
    # Keep the real retry pending while even slow Windows commands inspect it; cleanup ends it.
    monkeypatch.setenv("FORGE_CODEX_RETRY_WAIT", "600")
    child = subprocess.Popen([sys.executable, "-u", str(repo.bin / "forge"), "work", "BOARD/PAGE"],
                             cwd=repo.path, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    try:
        assert child.stdout is not None
        received = []
        for line in child.stdout:
            received.append(line)
            if "Codex is at capacity" in line:
                break
        assert any("Codex is at capacity" in line for line in received), "\n".join(received)
        before_retry = repo.forge("next")
        assert before_retry.returncode == 0, before_retry.stderr
        assert "Codex is at capacity; Forge sends the turn again at 12:10." in before_retry.stdout
        monkeypatch.setenv("FORGE_NOW", "2026-10-09T12:11:00+00:00")
        after_retry = repo.forge("next")
        assert after_retry.returncode == 0, after_retry.stderr
        assert "Codex is at capacity" not in after_retry.stdout
    finally:
        if child.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(child.pid)],
                               capture_output=True, check=False)
            else:
                child.send_signal(signal.SIGINT)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
