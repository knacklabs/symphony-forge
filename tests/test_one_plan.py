"""One plan approval opens the prototype gates and sign-off checks its ticks."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_close import GREEN, env  # noqa: F401
from test_proto_signoff import _client, _decision, _request_build
from test_setup import _fresh_client

STORY = "FORGE-ONEPLAN-1"


@pytest.mark.parametrize("case", ["new prototype", "adopted live app"])
def test_1_one_plan_approval_opens_the_prototype_gates(env, tmp_path, case):
    # Audit: the real decision, UI-fix, close and story commands own the gates.
    # Separate legacy-approval tests cannot detect a plan that opens only one gate.
    # Only GitHub and review tools are faked; this adds no production test seam.
    repo = env.repo
    if case == "new prototype":
        top, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = top
        config = top / "forge.toml"
        command = f'{json.dumps(Path(sys.executable).as_posix())} -c "print(123)"'
        text = re.sub(r"(?m)^test = .*", lambda _: "test = " + json.dumps(command),
                      config.read_text("utf-8"))
        config.write_text(text, encoding="utf-8")
    else:
        top = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", top, dirs_exist_ok=True)
        config = top / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        repo.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-qm", "Prepare the client")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    env.checks(GREEN)
    if case == "adopted live app":
        refused = repo.forge("story", "new", "SHOP", "Shoppers save baskets")
        assert refused.returncode == 1
        assert "Write the prototype plan" in refused.stderr
        assert "Write the prototype plan" in repo.forge("next").stdout
    started = repo.forge("fix", "start", "Write the prototype plan", "--done",
                         "The owner approved the prototype plan", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    fix = Path(re.search(r" in (.+)\n", started.stdout)[1])

    created = repo.forge("decision", "new", "prototype-plan", cwd=fix)

    assert created.returncode == 0, created.stdout + created.stderr
    [plan] = (fix / "docs/decisions").glob("*-prototype-plan.md")
    content = plan.read_text("utf-8")
    assert "## Demo steps" in content
    assert not re.search(r"(?m)^design_tree:", content)
    brief = fix / "docs/product/BRIEF.md"
    constitution = fix / "docs/product/CONSTITUTION.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("# Brief\n", encoding="utf-8")
    constitution.write_text("# Constitution\n", encoding="utf-8")
    refused = repo.forge("decision", "accept", "prototype-plan", "--by", "Owner", cwd=fix)
    assert refused.returncode == 1
    expected = ["## Defaults", "## Roles", "## Architecture choices", "## Summary",
                "## Users", "## Things it keeps track of"]
    if case == "new prototype":
        expected.append("## Demo steps")
    for gap in expected:
        assert any(gap in line and "Next:" in line for line in refused.stderr.splitlines())
    brief.write_text(
        "# Brief\n\n## Summary\nShoppers save baskets.\n\n## Users\nShoppers.\n\n"
        "## Things it keeps track of\nBasket: name:text.\n\n## Answers\n"
        "- Personal data: ask the client\n", encoding="utf-8")
    constitution.write_text(
        "# Constitution\n\n## Defaults\nUse the secure defaults.\n\n"
        "## Roles\nAdmin: all five. Member: view and create.\n\n"
        "## Architecture choices\n- Postgres because baskets need durable storage.\n",
        encoding="utf-8")
    if case == "new prototype":
        plan.write_text(content + "\n".join(f"{n}. Demo step {n}." for n in range(1, 8)) + "\n",
                        encoding="utf-8")
        too_many = repo.forge("decision", "accept", "prototype-plan", "--by", "Owner", cwd=fix)
        assert too_many.returncode == 1
        assert "## Demo steps" in too_many.stderr
        plan.write_text(content + "1. Save a basket.\n2. Find the basket.\n", encoding="utf-8")
    else:
        # A live app needs no demo steps, but keeps the personal-data question.
        plan.write_text(content.split("## Demo steps")[0], encoding="utf-8")
        personal = repo.forge("decision", "accept", "prototype-plan", "--by", "Owner", cwd=fix)
        assert personal.returncode == 1
        assert "Personal data" in personal.stderr and "docs/product/BRIEF.md" in personal.stderr
        brief.write_text(brief.read_text("utf-8").replace(
            "ask the client", "no private or regulated data (client, 2026-11-02)"), encoding="utf-8")
    accepted = repo.forge("decision", "accept", "prototype-plan", "--by", "Owner", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert not re.search(r"(?m)^design_tree:", plan.read_text("utf-8"))
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-qm", "Complete the prototype plan", cwd=fix)
    branch = repo.git("branch", "--show-current", cwd=fix)
    repo.git("merge", "--ff-only", branch, cwd=top)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "Write the prototype plan" not in shown.stdout
    if case == "adopted live app":
        started = repo.forge("story", "new", "SHOP", "Shoppers save baskets")
        assert started.returncode == 0, started.stdout + started.stderr
        return
    ui = repo.forge("fix", "start", "Build basket entry", "--done", "A shopper saves a basket",
                    "--kind", "ui")
    assert ui.returncode == 0, ui.stdout + ui.stderr
    where = Path(re.search(r" in (.+)\n", ui.stdout)[1])
    env.commit(where, "app.py", "print('basket saved')\n", "Build basket entry")
    closed = env.close("build-basket-entry")
    assert closed.returncode == 0, closed.stdout + closed.stderr


@pytest.mark.parametrize("case", ["new prototype", "earlier approvals"], ids=[
    "new-prototype", "earlier-approvals",
])
def test_4_signoff_needs_every_demo_step_ticked(repo, tmp_path, monkeypatch, case):
    # Audit: sign-off must refuse an unticked step, while the review-only first
    # pass and earlier approvals retain their contracts. The old sign-off suite
    # has no plan ticks. Only external reviews/GitHub are faked, with no new seam.
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    if case == "earlier approvals":
        _request_build(repo, fix)
        page = _decision(fix, answers, proof="The order flow passed its test.")
        accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert "status: accepted" in page.read_text("utf-8")
        return

    plan = fix / "docs/decisions/0002-prototype-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "---\nstatus: accepted\n---\n\n# Prototype plan\n\n"
        "## Decision\nThe owner approves the prototype plan as shown.\n\n"
        "## Demo steps\n1. Create an order.\n2. Find an order.\n",
        encoding="utf-8")
    page = _decision(fix, answers,
                     proof="- [x] 1. Create an order — tests/test_orders.py\n"
                     "- [ ] 2. Find an order — tests/test_orders.py")

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "Demo step 2 is not ticked" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    assert not queue.with_suffix(".calls.jsonl").exists()
    page = _decision(fix, answers, via="", on="",
                     proof="- [ ] 1. Create an order — tests/test_orders.py\n"
                     "- [ ] 2. Find an order — tests/test_orders.py")
    checked = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "you can now ask the customer's named person" in checked.stdout
    assert "status: proposed" in page.read_text("utf-8")
    page = _decision(fix, answers,
                     proof="- [x] 1. Create an order — tests/test_orders.py\n"
                     "- [x] 2. Find an order — tests/test_orders.py")
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
