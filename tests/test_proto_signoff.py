"""Client sign-off is accepted only after a complete product review.

Fixture audit: preserve the real decision command's refusal of app changes before a build request.
A fixture tied to a removed starter screen fails before that assertion; no other setup owns this
existing-screen case. Keep the command-level case and let the test construct its own screen,
without a production test seam.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import StubGh

pytestmark = pytest.mark.platform

STORY = "FORGE-PROTO-1"
PIN = "ce14dcca09b3affb922ddcca11465619e67f5114"
SOL_HIGH = "model: gpt-6.1-sol\nthinking: high\nautoreview done"
MUST = ("Sign-off person", "Demo workflow", "Users and roles", "Existing systems",
        "Sign-in", "Personal data", "Production host")


def _brief_text(answers):
    return ("# Brief\n\n## Summary\nSalespeople keep track of customer orders.\n\n"
            "## Users\n- Salespeople review submitted orders.\n\n"
            "## Things it keeps track of\n- Order: name and status.\n\n" +
            "## Key flows\n- Create an order, then review its status.\n\n" + answers)


def _design_records(top, answers):
    (top / "docs/product").mkdir(parents=True, exist_ok=True)
    (top / "docs/product/BRIEF.md").write_text(_brief_text(answers), encoding="utf-8")
    (top / "DESIGN.md").write_text("# Design\n\nUse a calm, clear order list.\n", encoding="utf-8")
    (top / "PRODUCT.md").write_text(
        "# Order book\n\nSalespeople track customer orders.\n", encoding="utf-8")
    folder = top / "docs/design/prototype"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "order-list.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>Orders</text></svg>\n', encoding="utf-8")
    (folder / "SCREENS.md").write_text(
        "# Screens\n\n## Order list\nImage: order-list.svg\nBuild: now\n"
        "Components: Card, Badge, Button\n"
        "Fields:\n- order name: text, required\n- status: choice, required, options: Open | Submitted\n",
        encoding="utf-8")
    (folder / "CHECKS.md").write_text(
        "## Critique\nNotes: The order list is clear.\nResult: passed\n"
        "## Polish\nNotes: The layout is consistent.\nResult: passed\n"
        "## Emil checklist\nNotes: Buttons have clear feedback.\nResult: passed\n",
        encoding="utf-8")


def _review_tools(repo, tmp_path, monkeypatch):
    helper = tmp_path / "autoreview"
    (helper / "scripts").mkdir(parents=True)
    shutil.copy(Path(__file__).parent / "stubs/autoreview", helper / "scripts/autoreview")
    (helper / ".upstream-sha").write_text(PIN)
    monkeypatch.setenv("AUTOREVIEW", str(helper / "scripts/autoreview"))
    queue = tmp_path / "reviews.json"
    queue.write_text(json.dumps([{"report": {"review_status": "scoped-clean", "findings": []}}]))
    monkeypatch.setenv("AUTOREVIEW_STUB", str(queue))
    codex = tmp_path / "codex-stub"
    codex.write_text(f"#!{sys.executable}\nimport json, pathlib, subprocess, os\n"
                     "tree = pathlib.Path.cwd()\n"
                     "names = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD^', 'HEAD'], cwd=tree, text=True, encoding='utf-8')\n"
                     "pathlib.Path(os.environ['SIGNOFF_DIFF']).write_text(names, encoding='utf-8')\n"
                     "calls = pathlib.Path(os.environ['AUTOREVIEW_STUB']).with_suffix('.calls.jsonl')\n"
                     "args = json.loads(calls.read_text(encoding='utf-8').splitlines()[-1])['args']\n"
                     "base = args[args.index('--base') + 1]\n"
                     "base_files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', base], cwd=tree, text=True, encoding='utf-8')\n"
                     "pathlib.Path(os.environ['SIGNOFF_BASE_FILES']).write_text(base_files, encoding='utf-8')\n"
                     "status = subprocess.check_output(['git', 'diff', '--name-status', base, 'HEAD'], cwd=tree, text=True, encoding='utf-8')\n"
                     "pathlib.Path(os.environ['SIGNOFF_STATUS']).write_text(status, encoding='utf-8')\n"
                     "files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=tree, text=True, encoding='utf-8')\n"
                     "pathlib.Path(os.environ['SIGNOFF_TREE']).write_text(files, encoding='utf-8')\n", encoding="utf-8")
    codex.chmod(0o755)
    if os.name == "nt":
        launcher = tmp_path / "codex-stub.cmd"
        launcher.write_text(f'@"{sys.executable}" "{codex}" %*\n')
        codex = launcher
    monkeypatch.setenv("CODEX_BIN", str(codex))
    monkeypatch.setenv("SIGNOFF_DIFF", str(tmp_path / "reviewed-files.txt"))
    monkeypatch.setenv("SIGNOFF_STATUS", str(tmp_path / "reviewed-status.txt"))
    monkeypatch.setenv("SIGNOFF_BASE_FILES", str(tmp_path / "review-base-files.txt"))
    monkeypatch.setenv("SIGNOFF_TREE", str(tmp_path / "reviewed-tree.txt"))
    return queue


def _green_full_run(repo):
    head = repo.git("rev-parse", "origin/main")
    StubGh(repo.bin).respond(
        "api", f"repos/{{owner}}/{{repo}}/commits/{head}/statuses",
        stdout=json.dumps([{"context": "forge-full-suite", "state": "success"}]))


def _client(repo, tmp_path, monkeypatch, *, working_build=True, design_model=None):
    version = repo.forge("--version").stdout.split()[-1]
    stage = "" if working_build else 'stage = "prototype"\n'
    model = (f'\n[models.design.claude]\nmodel = {json.dumps(design_model[0])}\n'
             f'effort = {json.dumps(design_model[1])}\n' if design_model else "")
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n{stage}{model}')
    sources = {"Demo workflow": "salesperson", "Users and roles": "developer"}
    answers = "## Answers\n" + "".join(
        f"- {topic}: {'Sam Lee, director' if topic == 'Sign-off person' else 'agreed'} "
        f"({sources.get(topic, 'client')}, 2026-09-28)\n" for topic in MUST)
    _design_records(repo.path, answers)
    if working_build:
        repo.write("app.py", "print('prototype')\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Build prototype")
    repo.git("push", "-q", "origin", "main")
    _green_full_run(repo)
    kind = [] if working_build else ["--kind", "mechanical"]
    started = repo.forge("fix", "start", "Record client approval", "--done", "Sign-off recorded",
                         *kind)
    assert started.returncode == 0, started.stderr
    fix = Path(started.stdout.split(" in ")[1].splitlines()[0])
    queue = _review_tools(repo, tmp_path, monkeypatch)
    return fix, answers, queue


def _adopted_client(repo, tmp_path, monkeypatch, *, old_signoff=False, design_model=None):
    fixture = Path(__file__).parent / "fixtures/adopted-v1.2.2/client"
    shutil.copytree(fixture, repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                      encoding="utf-8")
    if design_model:
        text = re.sub(r"(?ms)^\[models\.design\.claude\]\n.*?(?=^\[|\Z)", "", config.read_text("utf-8"))
        config.write_text(text + '\n[models.design.claude]\n'
                          f'model = {json.dumps(design_model[0])}\neffort = {json.dumps(design_model[1])}\n',
                          encoding="utf-8")
    sources = {"Demo workflow": "salesperson", "Users and roles": "developer"}
    answers = "## Answers\n" + "".join(
        f"- {topic}: {'Sam Lee, director' if topic == 'Sign-off person' else 'agreed'} "
        f"({sources.get(topic, 'client')}, 2026-09-28)\n" for topic in MUST)
    if not old_signoff:
        _design_records(repo.path, answers)
    if old_signoff:
        (repo.path / "docs/decisions").mkdir(parents=True, exist_ok=True)
        (repo.path / "docs/decisions/0001-client-signoff.md").write_text(
            "---\nstatus: accepted\ncustomer: Sam Lee, director\napproved_via: email\n"
            "approved_on: 2026-09-28\ndemo: https://demo.example.test\n---\n\n"
            "# Client sign-off\n\n## Context\nThe customer saw the prototype.\n\n"
            "## Decision\nThe customer approved.\n\n## Consequences\nStories may start.\n\n"
            + answers, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Upgrade the adopted client")
    repo.git("push", "-q", "-u", "origin", "main")
    _green_full_run(repo)
    started = repo.forge("fix", "start", "Record client approval", "--done", "Sign-off recorded",
                         "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    fix = Path(started.stdout.split(" in ")[1].splitlines()[0])
    queue = _review_tools(repo, tmp_path, monkeypatch)
    return fix, answers, queue


def _request_build(repo, fix):
    created = repo.forge("decision", "new", "prototype-build", cwd=fix)
    assert created.returncode == 0, created.stderr
    request = next((fix / "docs/decisions").glob("*-prototype-build.md"))
    request.write_text(re.sub(r"<!--.*?-->", "The canvas cannot prove real data speed.",
                              request.read_text("utf-8"), flags=re.S), encoding="utf-8")
    allowed = repo.forge("decision", "accept", "prototype-build", "--by", "Ravi", cwd=fix)
    assert allowed.returncode == 0, allowed.stderr


def _decision(fix, answers, *, customer="Sam Lee, director", via="email",
              on="2026-09-28", demo="https://demo.example.test", quote=None,
              proof="The design shows the key order flow."):
    design_tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD:docs/design/prototype"], cwd=fix, text=True).strip()
    page = fix / "docs/decisions/0001-client-signoff.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    cached = [line for line in page.read_text("utf-8").splitlines()
              if line.startswith(("design_checked:", "brief_checked:"))] if page.exists() else []
    metadata = "".join(f"{line}\n" for line in cached)
    page.write_text(f"---\nstatus: proposed\ncustomer: {customer}\napproved_via: {via}\n"
                    f"approved_on: {on}\ndemo: {demo}\n{metadata}---\n\n# Client sign-off\n\n"
                    "## Context\nThe customer saw the prototype.\n\n"
                    "## Decision\nThe customer approved.\n\n"
                    "## Consequences\nStories may start.\n\n"
                    "## Signed design\n"
                    f"docs/design/prototype/ ({design_tree})\n\n"
                    + ("## Proof\n" + proof + "\n\n" if proof else "")
                    + "## Decisions\nThe approved canvas is the source for production stories.\n\n"
                    + (answers if quote is None else quote), encoding="utf-8")
    return page


def test_7_review_guards_client_signoff(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers)
    reviewed = repo.git("rev-parse", "HEAD", cwd=fix)
    queue.write_text(json.dumps([
        {"say": SOL_HIGH, "report": {"review_status": "findings", "findings": [{
            "priority": "P1", "title": "Prototype fails", "body": "Gain 5, Work 2, Harm 1\nDemo cannot finish",
            "code_location": {"file_path": "app.py", "line": 1}}]}}]))
    blocked = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert blocked.returncode == 1
    assert "Prototype fails" in blocked.stderr
    assert "status: proposed" in page.read_text()
    assert len(queue.with_suffix(".calls.jsonl").read_text().splitlines()) == 1

    queue.write_text(json.dumps([{"say": SOL_HIGH, "report": {"review_status": "findings", "findings": [{
        "priority": "P0", "title": "Prototype exposes data", "body": "Gain 5, Work 2, Harm 4\nDemo leaks records",
        "code_location": {"file_path": "app.py", "line": 1}}]}}]))
    critical = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert critical.returncode == 1
    assert "Prototype exposes data" in critical.stderr
    # A P0 still blocks; its next step now starts one grouped repair fix.
    assert "Next: forge fix start " in critical.stderr
    assert "status: proposed" in page.read_text()
    assert len(queue.with_suffix(".calls.jsonl").read_text().splitlines()) == 2

    # Audit: open and unknown answers no longer gate sign-off, and Forge copies the
    # current brief into the record. The earlier refusal assertions duplicated this
    # gate across answer spellings; the sign-off command is the owning boundary.
    changed = answers.replace("Sign-in: agreed (client, 2026-09-28)",
                              "Sign-in: not known yet (client, 2026-11-02)").replace(
        "Personal data: agreed (client, 2026-09-28)",
        "Personal data: ask the client (client, 2026-11-02)")
    brief = fix / "docs/product/BRIEF.md"
    brief.write_text(_brief_text(changed), encoding="utf-8")
    repo.git("add", "docs/product/BRIEF.md", cwd=fix)
    repo.git("commit", "-qm", "Keep open client answers in the brief", cwd=fix)
    page = _decision(fix, answers, customer="Sam Lee", via="letter", on="", demo="")
    queue.write_text(json.dumps([{"say": SOL_HIGH,
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    accepted_with_open_answers = repo.forge(
        "decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted_with_open_answers.returncode == 0, accepted_with_open_answers.stderr
    saved = page.read_text("utf-8")
    assert "status: accepted" in saved
    assert changed in saved
    assert "approved_via: letter" in saved
    assert "approved_on: " in saved
    assert len(queue.with_suffix(".calls.jsonl").read_text().splitlines()) == 3

    queue.write_text(json.dumps([{"say": SOL_HIGH,
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    repo.git("rm", "--cached", "docs/product/BRIEF.md", cwd=fix)
    dirty = changed.replace("Demo workflow: agreed (client", "Demo workflow: revised (client")
    brief.write_text(_brief_text(dirty), encoding="utf-8")
    _decision(fix, changed, customer="Sam Lee", via="letter", on="")
    unreviewed = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert unreviewed.returncode == 1
    assert "prototype differs from the reviewed commit" in unreviewed.stderr
    assert "commit the changes" in unreviewed.stderr
    assert "status: proposed" in page.read_text()

    brief.write_text(_brief_text(changed), encoding="utf-8")
    repo.git("add", "docs/product/BRIEF.md", cwd=fix)
    page = _decision(fix, changed, customer="Sam Lee", via="letter", on="")

    queue.write_text(json.dumps([{"report": {"review_status": "scoped-clean", "findings": []}}]))
    missing_selection = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert missing_selection.returncode == 0, missing_selection.stderr
    assert "status: accepted" in page.read_text()
    # Test audit: these existing cases own strict external-review failures and
    # model selection. Changed proof makes each reach the reviewer despite reuse;
    # keep every failure assertion and the total call count. No new seam is needed.
    page = _decision(fix, answers, proof="The order flow passes. Check automatic model fallback.")

    queue.write_text(json.dumps([{"say": SOL_HIGH + "\n"
                                   "codex model gpt-6.1-sol is unavailable for this account; "
                                   "retrying with gpt-6-astra",
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    fallback = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert fallback.returncode == 0, fallback.stderr
    assert "status: accepted" in page.read_text()
    page = _decision(fix, answers, proof="The order flow passes. Check alternate effort.")

    queue.write_text(json.dumps([{"say": "model: gpt-6.1-sol\nthinking: xhigh",
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    other_effort = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert other_effort.returncode == 0, other_effort.stderr
    assert "status: accepted" in page.read_text()
    page = _decision(fix, answers, proof="The order flow passes. Check strict review errors.")
    reviewed = repo.git("rev-parse", "HEAD", cwd=fix)

    queue.write_text(json.dumps([{"say": SOL_HIGH, "report": {
        "review_status": "incomplete", "findings": [], "scope_rejected_findings": [{
            "priority": "P2", "title": "Outside scope", "body": "Gain 2, Work 1, Harm 1\nReview did not finish",
            "code_location": {"file_path": "app.py", "line": 1}}]}}]))
    incomplete = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert incomplete.returncode == 1
    assert "incomplete" in incomplete.stderr
    assert "status: proposed" in page.read_text()

    queue.write_text(json.dumps([{"say": SOL_HIGH, "exit": 2, "report": {
        "review_status": "scoped-clean", "findings": [], "scope_rejected_findings": [{
            "priority": "P2", "title": "Outside scope", "body": "Gain 2, Work 1, Harm 1\nReview stopped early",
            "code_location": {"file_path": "app.py", "line": 1}}]}}]))
    unfinished = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert unfinished.returncode == 1
    assert "incomplete" in unfinished.stderr
    assert "status: proposed" in page.read_text()

    queue.write_text(json.dumps([{"say": SOL_HIGH,
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    repo.git("rm", "--cached", "app.py", cwd=fix)
    (fix / "app.py").write_text("print('unreviewed prototype')\n")
    unreviewed_app = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert unreviewed_app.returncode == 1
    assert "prototype differs from the reviewed commit" in unreviewed_app.stderr
    assert "status: proposed" in page.read_text()
    (fix / "app.py").write_text("print('prototype')\n")
    repo.git("add", "app.py", cwd=fix)

    for status in (None, "unknown"):
        report = {"findings": []}
        if status:
            report["review_status"] = status
        queue.write_text(json.dumps([{"say": SOL_HIGH, "report": report}]))
        unfinished_status = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert unfinished_status.returncode == 1
        assert "review did not finish" in unfinished_status.stderr
        assert "Next: check Autoreview" in unfinished_status.stderr
        assert "status: proposed" in page.read_text()

    queue.write_text(json.dumps([{"say": SOL_HIGH,
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stderr
    assert f"reviewed_commit: {reviewed}" in page.read_text()
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text().splitlines()]
    # Uncommitted product changes now stop before either external check.
    assert len(calls) == 11
    options = dict(zip(calls[-1]["args"][::2], calls[-1]["args"][1::2]))
    assert options["--engine"] == "codex"
    assert "--model" not in options and "--thinking" not in options
    prompt = "\n\n".join(calls[-1]["prompt_files"].values())
    assert "Sign-off person" in prompt
    assert "docs/product/BRIEF.md" in prompt
    assert "| Topic | Question | Options (default first) | Ask by |" in prompt
    assert "| Data import | Does data need to come in from today's tools?" in prompt
    # The first attempt reviews the whole product. This retry rechecks earlier
    # findings without replaying unchanged product files (covered by signoff_review_rounds).
    assert not (tmp_path / "reviewed-files.txt").read_text().splitlines()


# Test audit: the command still requires a customer name and demo proof, while it
# no longer validates the name format, reply channel, date, demo URL or copied answers.
# A regression that restores any removed gate is caught by the accepted record below;
# test_4 owns the same Answers copy through a sample-data path. This uses the existing
# command and external reviewer boundary, with no production seam.
def test_8_signoff_needs_a_signer_and_proof_and_copies_current_answers(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    created = repo.forge("decision", "new", "client-signoff", cwd=fix)
    assert created.returncode == 0, created.stderr
    template = (fix / "docs/decisions/0001-client-signoff.md").read_text()
    for field in ("customer: \"\"", "approved_via: \"\"", "approved_on: \"\"",
                  "demo: \"\"", "## Answers", "## Signed design", "## Proof", "## Decisions"):
        assert field in template
    page = _decision(fix, answers, customer="")
    missing_customer = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert missing_customer.returncode == 1
    assert "customer" in missing_customer.stderr.lower()
    assert not queue.with_suffix(".calls.jsonl").exists()

    page = _decision(fix, answers, proof="")
    missing_proof = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert missing_proof.returncode == 1
    assert "Proof" in missing_proof.stderr
    assert not queue.with_suffix(".calls.jsonl").exists()

    stale = answers.replace("agreed", "old answer", 1)
    page = _decision(fix, answers, customer="Sam Lee", via="letter", on="", demo="", quote=stale)
    page.write_text(re.sub(r"(?m)^demo:.*\n", "", page.read_text("utf-8")), encoding="utf-8")
    queue.write_text(json.dumps([{"say": SOL_HIGH,
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi Recorder", cwd=fix)
    assert accepted.returncode == 0, accepted.stderr
    record = page.read_text("utf-8")
    assert "status: accepted" in record
    assert 'confirmed_by: "Ravi Recorder"' in record
    assert "customer: Sam Lee" in record
    assert "approved_via: letter" in record
    assert "approved_on: " in record
    assert "demo:" not in record
    assert answers in record
    assert stale not in record
    assert len(queue.with_suffix(".calls.jsonl").read_text().splitlines()) == 1
