"""Sample-data sign-off uses one gap check and never waits on the brief.

Test audit:
1. Tests 1, 4 and 8 protect light sign-off, the non-blocking brief, and design-source fallback.
2. Full-run or whole-source gates, open-answer refusals, and design-read refusals could regress.
3. Existing sign-off tests cover strict review, not this sample mode or its design fallback;
   each contract has one command-level owner here.
4. The tests use Forge's decision command and replace only GitHub and Autoreview at their edges.
"""

from __future__ import annotations

import json
import re

import pytest

from conftest import StubGh
from test_proto_signoff import _adopted_client, _client, _decision, _request_build
from test_open_decisions import _question

STORY = "FORGE-SAMPLE-1"
pytestmark = pytest.mark.platform


def _sample_setup(repo, tmp_path, monkeypatch, *, adopted, sample_data=True, green_full=False):
    make = _adopted_client if adopted else _client
    fix, answers, queue = make(repo, tmp_path, monkeypatch)
    if adopted:
        _request_build(repo, fix)
    config = fix / "forge.toml"
    text = config.read_text("utf-8")
    text = re.sub(r"(?m)^stage = .*\n", "", text)
    first_table = re.search(r"(?m)^\[[^\r\n]+\]\s*$", text)
    root = text[:first_table.start()] if first_table else text
    tables = text[first_table.start():] if first_table else ""
    root = re.sub(r"(?m)^interfaces\s*=.*\n", "", root)
    root = root.rstrip() + '\nstage = "prototype"\n'
    # Sample sign-off now needs the setting on both new and earlier-adopted clients.
    if sample_data:
        root += "sample_data = true\n"
    root += 'interfaces = ["interfaces/**"]\n'
    config.write_text(root + tables, encoding="utf-8")
    repo.git("add", "forge.toml", cwd=fix)
    repo.git("commit", "-qm", "Mark the prototype as sample data", cwd=fix)
    page = _sample_decision(fix, answers, adopted=adopted, sample_data=sample_data)
    head = repo.git("rev-parse", "origin/main", cwd=fix)
    statuses = ([{"context": "forge-full-suite", "state": "success"}]
                if green_full else [])
    StubGh(repo.bin).respond(
        "api", f"repos/{{owner}}/{{repo}}/commits/{head}/statuses", stdout=json.dumps(statuses))
    return fix, answers, queue, page


def _sample_decision(fix, answers, *, adopted, sample_data=True, **fields):
    page = _decision(fix, answers, **fields)
    if adopted and sample_data:
        page.write_text(page.read_text("utf-8").replace(
            "status: proposed", "status: proposed\nsample_data: true"), encoding="utf-8")
    return page


def _sample_review_files(repo, fix):
    files = {
        "apps/web/src/main.tsx": "import { createBrowserRouter } from 'react-router-dom';\n"
                                  "export const router = createBrowserRouter([{ path: '/orders' }]);\n",
        "apps/web/src/router.tsx": "import { createHashRouter } from 'react-router-dom';\n"
                                   "export const router = createHashRouter([{ path: '/archive' }]);\n",
        "apps/web/src/unrelated.tsx": "export const label = 'Order list';\n",
        "interfaces/orders.ts": "export type Order = { id: string };\n",
        "docs/specs/orders.md": "# Orders\n\nThe order route is documented.\n",
        "tests/test_orders.py": "def test_order_route():\n    assert True\n",
    }
    for name, contents in files.items():
        path = fix / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    repo.git("add", *files, cwd=fix)
    repo.git("commit", "-qm", "Add routes and unrelated sample files", cwd=fix)


@pytest.mark.parametrize("adopted,case", [
    (False, "clean"), (True, "clean"), (False, "repair"), (True, "repair"), (False, "lesser"),
    (False, "gain-4"), (False, "gain-5"), (False, "harm-4"), (False, "p0"), (False, "empty-proof"),
    (False, "empty-customer"), (False, "no-switch"),
], ids=["new-clean", "adopted-clean", "new-repair", "adopted-repair", "lesser", "gain-4", "gain-5",
       "harm-4", "p0", "empty-proof", "empty-customer", "no-switch"])
def test_1_a_sample_data_signoff_runs_only_the_gap_check(
        repo, tmp_path, monkeypatch, adopted, case):
    sample_data = case != "no-switch"
    fix, answers, queue, page = _sample_setup(
        repo, tmp_path, monkeypatch, adopted=adopted, sample_data=sample_data)
    if case == "no-switch":
        refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert refused.returncode == 1
        assert "green full test run" in refused.stderr
        assert not queue.with_suffix(".calls.jsonl").exists()
        return
    if case in ("empty-proof", "empty-customer"):
        fields = {"proof": ""} if case == "empty-proof" else {"customer": ""}
        _sample_decision(fix, answers, adopted=False, **fields)
        refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert refused.returncode == 1
        assert ("Proof" if case == "empty-proof" else "customer") in refused.stderr
        assert "status: proposed" in page.read_text("utf-8")
        assert not queue.with_suffix(".calls.jsonl").exists()
        return
    _sample_review_files(repo, fix)
    if case == "clean":
        accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert "status: accepted" in page.read_text("utf-8")
        calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
        assert len(calls) == 1
        prompt = "\n\n".join(calls[0]["prompt_files"].values())
        assert "Sample-data sign-off gap check" in prompt
        assert "whole-source" not in prompt
        assert "## Client prototype sign-off review" not in prompt
        assert "## Test evidence" not in prompt
        assert "Client sign-off checked this result before this review" not in prompt
        assert not (tmp_path / "review-base-files.txt").read_text("utf-8").splitlines()
        reviewed = set((tmp_path / "reviewed-tree.txt").read_text("utf-8").splitlines())
        assert reviewed == {
            "forge-standards.md", "docs/product/BRIEF.md",
            "docs/design/prototype/SCREENS.md", "docs/design/prototype/CHECKS.md",
            "interfaces/orders.ts", "apps/web/src/main.tsx", "apps/web/src/router.tsx",
        }
        statuses = (tmp_path / "reviewed-status.txt").read_text("utf-8").splitlines()
        assert statuses and all(line.startswith("A\t") for line in statuses)
        return
    if case == "repair":
        _sample_decision(fix, answers, adopted=adopted, via="", on="")
        first = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert first.returncode == 0, first.stdout + first.stderr
        assert "status: proposed" in page.read_text("utf-8")
        main = fix / "apps/web/src/main.tsx"
        main.write_text(main.read_text("utf-8").replace("'/orders'", "'/orders-v2'"), encoding="utf-8")
        repo.git("add", "apps/web/src/main.tsx", cwd=fix)
        repo.git("commit", "-qm", "Repair the prototype", cwd=fix)
        queue.write_text(json.dumps([{"report": {"review_status": "scoped-clean", "findings": []}}]))
        second = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert second.returncode == 0, second.stdout + second.stderr
        calls = queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()
        assert len(calls) == 2
        assert "--resolve" not in second.stderr
        statuses = (tmp_path / "reviewed-status.txt").read_text("utf-8").splitlines()
        assert statuses and all(line.startswith("A\t") for line in statuses)
        assert not any(line.startswith("D\t") for line in statuses)
        return

    scores = {"lesser": ("P1", 3, 3), "gain-4": ("P1", 4, 3),
              "gain-5": ("P1", 5, 1), "harm-4": ("P1", 1, 4),
              "p0": ("P0", 2, 2)}[case]
    priority, gain, harm = scores
    title = f"Missing demo behavior: {case}"
    queue.write_text(json.dumps([{"report": {"review_status": "findings", "findings": [{
        "priority": priority, "title": title,
        "body": f"Gain {gain}, Work 1, Harm {harm}\nThe main order route is missing.",
        "code_location": {"file_path": "apps/web/src/main.tsx", "line": 1}}]}}]))
    result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    owner_choice = case in ("gain-5", "harm-4", "p0")
    if owner_choice:
        assert result.returncode == 1, result.stdout + result.stderr
        assert "--resolve <accept|more|split>" in result.stderr
        assert title in result.stderr
        result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi",
                            "--resolve", "accept", "--reason", "The owner accepts this gap", cwd=fix)
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--resolve" not in result.stdout + result.stderr
        assert "forge fix start" not in result.stdout + result.stderr
    board = repo.forge("board", "--json", cwd=fix)
    assert board.returncode == 0, board.stderr
    kept = [entry for entry in json.loads(board.stdout)["known_issues"] if entry["title"] == title]
    assert len(kept) == 1
    assert kept[0]["kept"] != "open"
    if owner_choice:
        assert "The owner accepts this gap" in kept[0]["reason"]


@pytest.mark.parametrize("adopted,sample_data,stale_quote", [
    (False, True, False), (False, True, True), (True, True, False),
    (False, False, False),
], ids=["new-client-empty-quote", "new-client-stale-quote", "earlier-adopted",
       "unmarked-with-green-run"])
def test_4_the_brief_never_blocks_signoff_or_planning(
        repo, tmp_path, monkeypatch, adopted, sample_data, stale_quote):
    fix, answers, queue, page = _sample_setup(
        repo, tmp_path, monkeypatch, adopted=adopted, sample_data=sample_data,
        green_full=not sample_data)
    brief = fix / "docs/product/BRIEF.md"
    open_answers = answers.replace(
        "Sign-in: agreed (client, 2026-09-28)",
        "Sign-in: not known yet (client, 2026-11-02)").replace(
        "Personal data: agreed (client, 2026-09-28)",
        "Personal data: ask the client (client, 2026-11-02)")
    brief.write_text(brief.read_text("utf-8").replace(answers, open_answers), encoding="utf-8")
    question = fix / "docs/decisions/open-questions.md"
    question.parent.mkdir(parents=True, exist_ok=True)
    question.write_text("# Choices\n\n" + _question(
        "Should orders show personal details?", score="Gain 2, Work 1, Harm 1"), encoding="utf-8")
    repo.git("add", "docs/product/BRIEF.md", "docs/decisions/open-questions.md", cwd=fix)
    repo.git("commit", "-qm", "Record open client answers", cwd=fix)
    quote = answers if stale_quote else ""
    _sample_decision(fix, open_answers, adopted=adopted, sample_data=sample_data,
                     customer="Sam Lee", via="letter", on="", demo="", quote=quote)
    page.write_text(re.sub(r"(?m)^demo:.*\n", "", page.read_text("utf-8")), encoding="utf-8")

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    saved = page.read_text("utf-8")
    assert "status: accepted" in saved
    assert open_answers in saved
    assert "approved_via: letter" in saved
    assert "approved_on: " in saved
    assert "demo:" not in saved
    assert len(queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()) == 1
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    prompt = "\n\n".join(calls[0]["prompt_files"].values())
    assert "Decide first" not in prompt


@pytest.mark.parametrize("adopted,source", [
    (False, "linked"), (False, "saved-pages"), (True, "saved-pages"),
    (False, "screen-list"), (False, "none"),
], ids=["linked-without-pages", "new-client-pages", "earlier-adopted-pages",
       "brief-screen-list", "no-design-source"])
def test_8_the_gap_check_reads_the_design_or_says_plainly_that_it_did_not(
        repo, tmp_path, monkeypatch, adopted, source):
    fix, answers, queue, page = _sample_setup(repo, tmp_path, monkeypatch, adopted=adopted)
    brief = fix / "docs/product/BRIEF.md"
    _sample_decision(fix, answers, adopted=adopted)
    text = brief.read_text("utf-8")
    if source == "linked":
        text += "\n## Design\n\n[Order screen](https://design.example.test/orders)\n"
    elif source == "screen-list":
        text += "\n## Design\n\n- Screens: Order list, Order archive\n"
    brief.write_text(text, encoding="utf-8")
    if source in ("linked", "screen-list", "none"):
        repo.git("rm", "-r", "docs/design/prototype", cwd=fix)
    if source != "saved-pages":
        repo.git("add", "docs/product/BRIEF.md", cwd=fix)
        repo.git("commit", "-qm", "Set the available design source", cwd=fix)
    if source == "linked":
        queue.write_text(json.dumps([{"report": {"review_status": "findings", "findings": [{
            "priority": "P2", "title": "Design not read",
            "body": "Gain 2, Work 1, Harm 1\nThe linked design could not be read.",
            "code_location": {"file_path": "docs/product/BRIEF.md", "line": 1}}]}}]))

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    prompt = "\n\n".join(calls[0]["prompt_files"].values())
    assert "Design source" in prompt
    if source == "linked":
        assert "https://design.example.test/orders" in prompt
        assert "The design was not read." in accepted.stdout
        assert "screen list" in accepted.stdout.lower()
    elif source == "saved-pages":
        assert "docs/design/prototype/SCREENS.md" in prompt
        assert "docs/design/prototype/CHECKS.md" in prompt
        assert "The design was not read." not in accepted.stdout
    elif source == "screen-list":
        assert "- Screens: Order list, Order archive" in prompt
        assert "The design was not read." in accepted.stdout
    else:
        assert "No design link, saved pages or screen list." in prompt
        assert "The design was not read." in accepted.stdout
        assert "screen list" in accepted.stdout.lower()
    assert "status: accepted" in page.read_text("utf-8")
