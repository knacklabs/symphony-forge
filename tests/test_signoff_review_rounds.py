"""Bound sign-off retries at the real decision command.

Test audit: protects reviewer input, the durable owner stop and the owning item's
public Known issues. A changed-files-only retry drops an unresolved finding in an
unchanged file. A misplaced accepted finding disappears from the owner's item.
This is the command-level owner of those contracts, with no production test seam.
Only Autoreview is faked at its external edge; the real CLI, git snapshots and
board output own the observed behavior.
The earlier revision must remain an ancestor of the comparison base. Image
exclusion can create a child snapshot, so exact base commit identity is not
the contract; the earlier app contents and ancestry are.
"""
import json

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "client-sign-off-never-finishes-every-att"
pytestmark = pytest.mark.platform


def _report(priority):
    return {"report": {"review_status": "findings", "findings": [{
        "priority": priority, "title": "Order submission fails",
        "body": "Gain 5, Work 2, Harm 4\nThe normal order path fails.",
        "code_location": {"file_path": "app.py", "line": 1}}]}}


@pytest.mark.parametrize("setup,priority,choice", [
    (_client, "P1", "accept"), (_client, "P1", "more"),
    (_client, "P1", "split"), (_client, "P0", None),
    (_adopted_client, "P1", "accept"),
], ids=["new-accept", "new-more", "new-split", "new-critical", "adopted-accept"])
def test_1_signoff_reviews_changes_and_bounds_rounds(repo, tmp_path, monkeypatch, setup, priority, choice):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    recorder = tmp_path / "codex-stub"
    recorder.write_text(recorder.read_text("utf-8") +
                        "base = subprocess.check_output(['git', 'ls-tree', 'HEAD^', '--', 'app.py'], cwd=tree, text=True)\n"
                        "pathlib.Path(os.environ['SIGNOFF_DIFF'] + '.base').write_text(base, encoding='utf-8')\n"
                        "commit = subprocess.check_output(['git', 'rev-list', 'HEAD^'], cwd=tree, text=True)\n"
                        "pathlib.Path(os.environ['SIGNOFF_DIFF'] + '.commit').write_text(commit, encoding='utf-8')\n",
                        encoding="utf-8")
    if setup is _adopted_client:
        _request_build(repo, fix)
        (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-q", "-m", "Build the adopted prototype", cwd=fix)
    page = _decision(fix, answers)
    previous_app = repo.git("ls-tree", "HEAD", "--", "app.py", cwd=fix)
    previous_commit = repo.git("rev-parse", "HEAD", cwd=fix)
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, _report(priority)]))

    def accept(*args):
        return repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", *args, cwd=fix)

    first = accept()
    assert first.returncode == 1, first.stdout + first.stderr
    assert "Order submission fails" in first.stderr
    original = set((tmp_path / "reviewed-files.txt").read_text().splitlines())
    assert {"README.md", "forge.toml", "docs/product/BRIEF.md"} <= original
    changed = "README.md" if priority == "P0" else "app.py"
    with (fix / changed).open("a", encoding="utf-8") as page_change:
        page_change.write("\n# Explain the order path\n")
    repo.git("add", changed, cwd=fix)
    repo.git("commit", "-q", "-m", "Explain the order path", cwd=fix)
    # The product edit also invalidates the separate canvas completeness check.
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, _report(priority)]))
    second = accept()
    assert second.returncode == 1, second.stdout + second.stderr
    # The earlier finding's file remains a review target even when only the
    # README changed. Unrelated unchanged files stay outside that target.
    assert set((tmp_path / "reviewed-files.txt").read_text().splitlines()) == {changed, "app.py"}
    # The review's actual base contains the last reviewed app revision, not
    # an empty tree or the current app. Open unchanged files are removed only
    # to recheck them (the P0 case), so they still appear in the diff above.
    assert (tmp_path / "reviewed-files.txt.base").read_text("utf-8").strip() == (
        "" if priority == "P0" else previous_app)
    if priority != "P0":
        assert previous_commit in (tmp_path / "reviewed-files.txt.commit").read_text("utf-8").splitlines()
    calls = queue.with_suffix(".calls.jsonl")
    prior = [json.loads(line) for line in calls.read_text().splitlines()]
    prompt = "\n".join(prior[-1]["prompt_files"].values())
    assert "Order submission fails" in prompt
    third = accept()
    assert third.returncode == 1, third.stdout + third.stderr
    if priority == "P0":
        assert set((tmp_path / "reviewed-files.txt").read_text().splitlines()) == {"app.py"}
        assert "Order submission fails" in third.stderr
        # A P0 still needs repair after the round limit, through one grouped fix.
        assert "Next: forge fix start " in third.stderr
        assert len(calls.read_text().splitlines()) == len(prior) + 1
        return
    assert "One more round, split or accept?" in third.stderr
    assert "--resolve" in third.stderr
    assert len(calls.read_text().splitlines()) == len(prior)
    resolved = accept("--resolve", choice, "--reason", "The owner chose this outcome")
    if choice == "more":
        assert len(calls.read_text().splitlines()) == len(prior) + 1
        assert "Order submission fails" in resolved.stderr
    else:
        assert resolved.returncode == 0, resolved.stdout + resolved.stderr
        assert "status: accepted" in page.read_text()
        assert len(calls.read_text().splitlines()) == len(prior)
        shown = repo.forge("board", "--json", cwd=fix)
        assert shown.returncode == 0, shown.stdout + shown.stderr
        board = json.loads(shown.stdout)
        item = repo.git("branch", "--show-current", cwd=fix).removeprefix("fix/")
        kept = [entry for entry in board["known_issues"] if entry["title"] == "Order submission fails"]
        assert len(kept) == 1
        assert kept[0]["item"] == item
        assert kept[0]["kept"] == "follow-up"
        assert "The owner chose this outcome" in kept[0]["reason"]
        if choice == "split":
            assert any(entry["id"] != item and "order submission fails" in entry["title"].lower()
                       for entry in board["items"])


# Test audit: acceptance survives reviews of another file and Forge sync, but
# expires on edits to its file and never hides P0. Existing coverage ends at
# acceptance. Drive the real command and git; no production seam is needed.
@pytest.mark.parametrize("setup,change,priority", [
    (_client, "other", "P1"), (_client, "same", "P1"),
    (_client, "other", "P0"), (_client, "sync", "P1"),
    (_adopted_client, "other", "P1"),
], ids=["reworded", "edited", "critical", "generated", "adopted"])
def test_2_accepted_signoff_survives_only_unchanged_files(
        repo, tmp_path, monkeypatch, setup, change, priority):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    if setup is _adopted_client:
        _request_build(repo, fix)
    (fix / "src").mkdir(exist_ok=True)
    (fix / "src/orders.py").write_text("print('orders')\n", encoding="utf-8")
    repo.git("add", "src/orders.py", cwd=fix)
    repo.git("commit", "-qm", "Build order flow", cwd=fix)
    _decision(fix, answers)
    report = _report("P1")
    report["report"]["findings"][0]["code_location"]["file_path"] = "src\\orders.py"

    def accept(*args):
        return repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", *args, cwd=fix)

    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, report]), encoding="utf-8")
    assert accept().returncode == 1
    assert accept().returncode == 1
    assert set((tmp_path / "reviewed-files.txt").read_text("utf-8").splitlines()) == {"src/orders.py"}
    calls = queue.with_suffix(".calls.jsonl")
    before = len(calls.read_text("utf-8").splitlines())
    if change == "sync":
        synced = repo.forge("sync", cwd=fix)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("add", "-A", cwd=fix)
        repo.git("commit", "-qm", "Refresh generated Forge files", cwd=fix)
    resolved = accept("--resolve", "accept", "--reason", "The owner accepts this limitation")
    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    assert len(calls.read_text("utf-8").splitlines()) == before
    if change == "sync":
        return
    target = "src/orders.py" if change == "same" else "README.md"
    with (fix / target).open("a", encoding="utf-8") as out:
        out.write("\n# Changed after acceptance\n")
    repo.git("add", target, cwd=fix)
    repo.git("commit", "-qm", "Update the prototype", cwd=fix)
    finding = report["report"]["findings"][0]
    finding.update(priority=priority, title=("Order submission fails" if priority == "P0"
                                           else "Submitting an order still fails"))
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, report]), encoding="utf-8")
    retried = accept()
    assert retried.returncode == (0 if change == "other" and priority == "P1" else 1), retried.stdout + retried.stderr
    assert set((tmp_path / "reviewed-files.txt").read_text("utf-8").splitlines()) == {target}
