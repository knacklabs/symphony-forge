"""Client sign-off is accepted only after a complete product review."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

STORY = "FORGE-PROTO-1"
PIN = "ce14dcca09b3affb922ddcca11465619e67f5114"
MUST = ("Sign-off person", "Demo workflow", "Users and roles", "Existing systems",
        "Sign-in", "Personal data", "Production host")


def _client(repo, tmp_path, monkeypatch):
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n')
    answers = "## Answers\n" + "".join(
        f"- {topic}: {'Sam Lee, director' if topic == 'Sign-off person' else 'agreed'} "
        "(client, 2026-09-28)\n" for topic in MUST)
    repo.write("docs/product/BRIEF.md", "# Brief\n\n" + answers)
    repo.write("app.py", "print('prototype')\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Build prototype")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Record client approval", "--done", "Sign-off recorded")
    assert started.returncode == 0, started.stderr
    fix = Path(started.stdout.split(" in ")[1].splitlines()[0])
    helper = tmp_path / "autoreview"
    (helper / "scripts").mkdir(parents=True)
    shutil.copy(Path(__file__).parent / "stubs/autoreview", helper / "scripts/autoreview")
    (helper / ".upstream-sha").write_text(PIN)
    monkeypatch.setenv("AUTOREVIEW", str(helper / "scripts/autoreview"))
    queue = tmp_path / "reviews.json"
    queue.write_text(json.dumps([{"report": {"review_status": "complete", "findings": []}}]))
    monkeypatch.setenv("AUTOREVIEW_STUB", str(queue))
    codex = tmp_path / "codex-stub"
    codex.write_text(f"#!{sys.executable}\nimport pathlib, subprocess, os\n"
                     "tree = pathlib.Path.cwd()\n"
                     "names = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD^', 'HEAD'], cwd=tree, text=True)\n"
                     "pathlib.Path(os.environ['SIGNOFF_DIFF']).write_text(names)\n")
    codex.chmod(0o755)
    if os.name == "nt":
        launcher = tmp_path / "codex-stub.cmd"
        launcher.write_text(f'@"{sys.executable}" "{codex}" %*\n')
        codex = launcher
    monkeypatch.setenv("CODEX_BIN", str(codex))
    monkeypatch.setenv("SIGNOFF_DIFF", str(tmp_path / "reviewed-files.txt"))
    return fix, answers, queue


def _decision(fix, answers, *, customer="Sam Lee, director", via="email",
              on="2026-09-28", demo="https://demo.example.test", quote=None):
    page = fix / "docs/decisions/0001-client-signoff.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"---\nstatus: proposed\ncustomer: {customer}\napproved_via: {via}\n"
                    f"approved_on: {on}\ndemo: {demo}\n---\n\n# Client sign-off\n\n"
                    "## Context\nThe customer saw the prototype.\n\n"
                    "## Decision\nThe customer approved.\n\n"
                    "## Consequences\nStories may start.\n\n"
                    + (answers if quote is None else quote), encoding="utf-8")
    return page


def test_7_review_guards_client_signoff(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers)
    reviewed = repo.git("rev-parse", "HEAD", cwd=fix)
    queue.write_text(json.dumps([{"report": {"review_status": "complete", "findings": [{
        "priority": "P1", "title": "Prototype fails", "body": "Demo cannot finish",
        "code_location": {"file_path": "app.py", "line": 1}}]}}]))
    blocked = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert blocked.returncode == 1
    assert "Prototype fails" in blocked.stderr
    assert "status: proposed" in page.read_text()
    assert len(queue.with_suffix(".calls.jsonl").read_text().splitlines()) == 1

    changed = answers.replace("Sign-in: agreed (client", "Sign-in: agreed (our default ")
    (fix / "docs/product/BRIEF.md").write_text("# Brief\n\n" + changed)
    _decision(fix, changed)
    default = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert default.returncode == 1
    assert "Sign-in" in default.stderr
    assert "forge next" in default.stderr
    assert len(queue.with_suffix(".calls.jsonl").read_text().splitlines()) == 1

    open_answer = answers.replace("Sign-in: agreed (client, 2026-09-28)",
                                  "Sign-in: ask the client (Ravi, 2026-09-28)")
    (fix / "docs/product/BRIEF.md").write_text("# Brief\n\n" + open_answer)
    _decision(fix, open_answer)
    open_topic = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert open_topic.returncode == 1
    assert "Sign-in" in open_topic.stderr
    assert "forge next" in open_topic.stderr
    assert len(queue.with_suffix(".calls.jsonl").read_text().splitlines()) == 1

    queue.write_text(json.dumps([{"report": {"review_status": "complete", "findings": []}}]))
    changed = answers.replace("Demo workflow: agreed (client", "Demo workflow: revised (client")
    repo.git("rm", "--cached", "docs/product/BRIEF.md", cwd=fix)
    (fix / "docs/product/BRIEF.md").write_text("# Brief\n\n" + changed)
    _decision(fix, changed)
    unreviewed = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert unreviewed.returncode == 1
    assert "prototype differs from the reviewed commit" in unreviewed.stderr
    assert "commit the changes" in unreviewed.stderr
    assert "status: proposed" in page.read_text()

    (fix / "docs/product/BRIEF.md").write_text("# Brief\n\n" + answers)
    repo.git("add", "docs/product/BRIEF.md", cwd=fix)
    page = _decision(fix, answers)

    # Sign-off used to judge model and effort from progress text. It now pins the
    # requested values in Autoreview's arguments; progress is not an attestation.
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stderr
    assert f"reviewed_commit: {reviewed}" in page.read_text()
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text().splitlines()]
    assert len(calls) == 3
    options = dict(zip(calls[-1]["args"][::2], calls[-1]["args"][1::2]))
    assert options["--model"] == "codex=gpt-6-sol"
    assert options["--thinking"] == "codex=xhigh"
    assert "Sign-off person" in options["--prompt"]
    assert "docs/product/BRIEF.md" in options["--prompt"]
    assert set((tmp_path / "reviewed-files.txt").read_text().splitlines()) == {
        "README.md", "forge.toml", "app.py", "docs/product/BRIEF.md"}


def test_8_signoff_requires_customer_evidence_and_exact_answers(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    created = repo.forge("decision", "new", "client-signoff", cwd=fix)
    assert created.returncode == 0, created.stderr
    template = (fix / "docs/decisions/0001-client-signoff.md").read_text()
    for field in ("customer: \"\"", "approved_via: \"\"", "approved_on: \"\"",
                  "demo: \"\"", "## Answers"):
        assert field in template
    page = _decision(fix, answers, customer="")
    missing = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert missing.returncode == 1
    assert "customer" in missing.stderr.lower()
    assert not queue.with_suffix(".calls.jsonl").exists()

    _decision(fix, answers, quote=answers.replace("agreed", "changed", 1))
    mismatch = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert mismatch.returncode == 1
    assert "answers" in mismatch.stderr.lower()
    assert not queue.with_suffix(".calls.jsonl").exists()
    assert "status: proposed" in page.read_text()

    _decision(fix, answers, customer="Another Person, owner")
    wrong_person = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert wrong_person.returncode == 1
    assert "Sign-off person" in wrong_person.stderr

    for field in ("approved_via", "approved_on", "demo"):
        _decision(fix, answers)
        page.write_text(page.read_text().replace(f"{field}: " + {
            "approved_via": "email", "approved_on": "2026-09-28",
            "demo": "https://demo.example.test"}[field], f"{field}: "))
        refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert refused.returncode == 1
        assert field in refused.stderr
        assert not queue.with_suffix(".calls.jsonl").exists()
