"""Sample-data prototypes skip tests until the setting is turned off.

Test audit:
1. Protect init/sync, close, merge, next and worker-brief behavior for sample-data mode,
   including an earlier-adopted repo.
2. A setting rejection, test run, generated workflow, or GitHub check in sample mode is a
   credible regression; a no-switch conversion must still run its configured test command.
3. No existing test owns this setting's command behavior; these cases use real Forge commands
   and fake only review and GitHub at their edges.
4. No production seam is needed.

An unfinished round must keep the same sample-data proof in its commit reminder.
Normal reminder coverage does not exercise a sample-data repo. The worker stub
deliberately leaves work unfinished so the real reminder path sends the second prompt.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_close import CLEAN, GREEN, env  # noqa: F401
from test_merge_command import _merge_at_github
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "FORGE-SAMPLE-1"
ADOPTED = ROOT / "tests/fixtures/adopted-v1.2.2/client"


def _settings(path: Path, **values: object) -> None:
    """Write root-level TOML settings before any table in the file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    table = next((i for i, line in enumerate(lines) if line.startswith("[")), len(lines))
    root, tail = lines[:table], lines[table:]
    for key, value in values.items():
        found = next((i for i, line in enumerate(root) if line.startswith(f"{key} = ")), None)
        rendered = json.dumps(value)
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        if found is None:
            root.append(f"{key} = {rendered}")
        else:
            root[found] = f"{key} = {rendered}"
    path.write_text("\n".join([*root, *tail]).rstrip() + "\n", encoding="utf-8")


def _prepared_client(repo, gh, tmp_path, case: str, test_marker: Path,
                     test_place: str = "local"):
    if case == "new client":
        top, initialized = _fresh_client(repo, gh, tmp_path, "--actions", "no")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = top
    else:
        shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
        top = repo.path

    version = repo.forge("--version").stdout.split()[-1]
    config = top / "forge.toml"
    if case == "earlier adopted":
        config.write_text(config.read_text(encoding="utf-8").replace('"v1.2.2"',
                            json.dumps(version)), encoding="utf-8")
    command_code = (f"from pathlib import Path; Path({json.dumps(test_marker.as_posix())})"
                    ".write_text('ran')")
    command = f"{json.dumps(Path(sys.executable).as_posix())} -c {json.dumps(command_code)}"
    _settings(config, repo="client", stage="prototype", workers="claude", sample_data=True,
              test=command, fast_test=command, checks=["tests", "forge-pr-check"],
              test_place=test_place)
    return top, config


@pytest.mark.parametrize("case,test_place", [
    ("new client", "local"), ("new client", "ci"), ("earlier adopted", "ci"),
], ids=["new-client-local", "new-client-ci", "earlier-adopted-ci"])
def test_2_a_sample_data_repo_runs_no_tests_or_ci_until_its_first_build_step(
        env, tmp_path, monkeypatch, case, test_place):
    # Audit: sample mode must bypass local tests and PR checks through real start/close/merge;
    # sync must keep existing workflows, and the accepted sign-off controls the next step.
    repo, gh = env.repo, env.gh
    marker = tmp_path / "sample-test-ran"
    top, config = _prepared_client(repo, gh, tmp_path, case, marker, test_place)
    workflow = top / ".github/workflows/forge.yml"
    if case == "earlier adopted":
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text("name: client's existing checks\n", encoding="utf-8")
    workflow_before = workflow.read_bytes() if workflow.exists() else None
    if case == "earlier adopted":
        # Upgrade generated files on a branch, as an earlier client's real sync requires.
        repo.git("switch", "-qc", "fix/sample-setup")

    _settings(config, sample_data="true")
    invalid = repo.forge("sync")
    assert invalid.returncode != 0
    assert "sample_data" in invalid.stderr and "true or false" in invalid.stderr
    _settings(config, sample_data=True)
    synced = repo.forge("sync")

    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert (workflow.read_bytes() if workflow.exists() else None) == workflow_before
    for host in (".claude", ".codex"):
        skill = (top / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
        assert "coordinator set `sample_data = true` in `forge.toml`" in skill
    assert not marker.exists()
    before_signoff = repo.forge("next")
    assert before_signoff.returncode == 0, before_signoff.stderr
    assert "set up tests" not in before_signoff.stdout

    # General build admission has its own owner; this fixture records that earlier approval.
    repo.write("docs/decisions/0000-prototype-build.md",
               '---\nstatus: accepted\nconfirmed_by: "Owner"\n---\n# Build the sample demo\n')
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Enable the sample-data prototype")
    if case == "earlier adopted":
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/sample-setup")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Tidy readme", "--done", "The readme is ready",
                         "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    item = "tidy-readme"
    where = Path(re.search(r" in (.+)\n", started.stdout)[1])
    original = (where / "forge.toml").read_bytes()
    head = repo.git("rev-parse", "HEAD", cwd=where)
    _settings(where / "forge.toml", sample_data=False)
    repo.git("add", "forge.toml", cwd=where)
    with monkeypatch.context() as worker:
        worker.setenv("FORGE_WORKER", "1")
        refused = subprocess.run(["git", "commit", "-qm", "Change the sample setting"],
                                 cwd=where, capture_output=True, text=True, encoding="utf-8")
    assert refused.returncode != 0
    assert "Workers leave forge.toml to the coordinator" in refused.stderr
    assert "Next: report the needed settings change in your last message." in refused.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == head
    repo.git("restore", "--staged", "--", "forge.toml", cwd=where)
    (where / "forge.toml").write_bytes(original)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "app.py")
    log = install_claude(repo)
    built = repo.forge("work", item)
    assert built.returncode == 0, built.stdout + built.stderr
    prompts = calls(log)
    assert len(prompts) == 2  # The initial brief and the real unfinished-round reminder.
    for sent in prompts:
        prompt = sent["brief"]
        assert "## Sample-data proof" in prompt
        assert "walk each demo step in a browser" in prompt
        assert "Do not add or run automated tests or CI." in prompt
        assert "The full run on main must be green." not in prompt
        assert "run the change's related tests through `forge test`" not in prompt
    env.commit(where, "app.py", "print('sample demo path')\n", "Add a sample demo path")

    env.reviews(CLEAN)
    env.open_pr("")
    env.checks(GREEN)
    calls_before_close = len(env.gh.calls())
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "no tests or CI in sample-data mode" in closed.stdout
    assert "Sample-data mode skips tests and CI." in closed.stdout
    assert "its tests passed on this machine" not in closed.stdout
    assert not marker.exists()

    # GitHub merges the already-reviewed pull request; Forge must not wait for PR checks.
    origin = Path(repo.git("remote", "get-url", "origin", cwd=top))
    merge_area = tmp_path / "sample-merge"
    merge_area.mkdir()
    shutil.move(str(origin), merge_area / "remote.git")
    repo.git("remote", "set-url", "origin", str(merge_area / "remote.git"), cwd=top)
    env.tmp = merge_area
    gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main",
        "headRefName": "fix/tidy-readme", "headRefOid": repo.git("rev-parse", "HEAD", cwd=where),
        "title": "Tidy readme", "isDraft": False, "body": ""}))
    _merge_at_github(env)
    merged = repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert not marker.exists()
    sample_calls = env.gh.calls()[calls_before_close:]
    assert not [call for call in sample_calls if call[:2] == ["pr", "checks"]]
    # Timing history reads use filter=all. CI waits query the current head's check runs.
    assert not [call for call in sample_calls if "filter=all" not in call
                and any("/check-runs" in arg for arg in call)]
    (repo.bin / "github-merged").unlink(missing_ok=True)
    gh.respond("pr", "view", stdout="{}")

    repo.git("checkout", "main", cwd=top)
    repo.git("pull", "--ff-only", "origin", "main", cwd=top)
    signoff = top / "docs/decisions/0001-client-signoff.md"
    signoff.parent.mkdir(parents=True, exist_ok=True)
    signoff.write_text("---\nstatus: accepted\n---\n", encoding="utf-8")
    repo.git("add", "docs/decisions/0001-client-signoff.md", cwd=top)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Record accepted client sign-off", cwd=top)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main", cwd=top)
    after_signoff = repo.forge("next")
    assert after_signoff.returncode == 0, after_signoff.stderr
    assert after_signoff.stdout.splitlines()[0] == "Step 5 of 7: set up tests."

    # Without the switch, Forge keeps the normal prototype proof and runs the configured test.
    brief = top / "docs/product/BRIEF.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("# Product brief\n\n## Answers\n"
                     "- Personal data: none (client, 2026-11-02)\n", encoding="utf-8")
    config.write_text(re.sub(r"(?m)^sample_data = true\n", "", config.read_text("utf-8")),
                      encoding="utf-8")
    _settings(config, test_place="local", checks=[])
    repo.git("add", "-A", cwd=top)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Remove the sample-data setting", cwd=top)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main", cwd=top)
    no_switch = repo.forge("next")
    assert no_switch.returncode == 0, no_switch.stderr
    assert "set up tests" not in no_switch.stdout
    started = repo.forge("fix", "start", "Tidy app", "--done", "The app is tidy",
                         "--kind", "mechanical", cwd=top)
    assert started.returncode == 0, started.stdout + started.stderr
    item = "tidy-app"
    where = Path(re.search(r" in (.+)\n", started.stdout)[1])
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "app.py")
    previous_calls = len(calls(log))
    normal_worker = repo.forge("work", item)
    assert normal_worker.returncode == 0, normal_worker.stdout + normal_worker.stderr
    prompt = calls(log)[previous_calls]["brief"]
    assert "Run any test command you start in the foreground and wait for it to finish." in prompt
    assert "## Sample-data proof" not in prompt
    reminder = calls(log)[-1]["brief"]
    assert "run the change's related tests through `forge test`" in reminder
    assert "## Sample-data proof" not in reminder
    env.commit(where, "app.py", "print('prototype')\n", "Keep the prototype working")
    env.reviews(CLEAN)
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert marker.exists()


@pytest.mark.parametrize("case,transition", [
    ("new client", "false"), ("new client", "removed"), ("earlier adopted", "false"),
], ids=["new-client-false", "new-client-removed", "earlier-adopted-false"])
def test_7_turning_sample_data_off_needs_a_settled_personal_data_answer(
        env, tmp_path, case, transition):
    repo = env.repo
    marker = tmp_path / "sample-test-ran"
    top, config = _prepared_client(repo, env.gh, tmp_path, case, marker)
    brief = top / "docs/product/BRIEF.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(
        "# Product brief\n\n## Summary\nShoppers save baskets.\n\n"
        "## Users\nShoppers use the app.\n\n## Things it keeps track of\nBasket: name.\n\n"
        "## Answers\n- Personal data: ask the client\n", encoding="utf-8")
    signoff = top / "docs/decisions/0001-client-signoff.md"
    signoff.parent.mkdir(parents=True, exist_ok=True)
    legacy = case == "earlier adopted"
    frontmatter = ("---\nstatus: accepted\nsample_data: true\n---\n" if legacy else
                  "---\nstatus: accepted\n---\n")
    signoff.write_text(frontmatter + "\n# Client sign-off\n", encoding="utf-8")
    _settings(config, repo="client", stage="prototype", test_place="local")
    if legacy:
        config.write_text(re.sub(r"(?m)^sample_data = true\n", "",
                                 config.read_text(encoding="utf-8")), encoding="utf-8")
    repo.git("add", "-A", cwd=top)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Prepare a sample-data prototype", cwd=top)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main", cwd=top)

    # The sample declaration leaves the open answer out of the app-constitution decision.
    started = repo.forge("fix", "start", "Approve app constitution", "--done",
                         "The app constitution is accepted", "--kind", "mechanical", cwd=top)
    assert started.returncode == 0, started.stdout + started.stderr
    decision_fix = Path(re.search(r" in (.+)\n", started.stdout)[1])
    created = repo.forge("decision", "new", "app-constitution", cwd=decision_fix)
    assert created.returncode == 0, created.stdout + created.stderr
    app_record = next((decision_fix / "docs/decisions").glob("*-app-constitution.md"))
    app_record.write_text(
        "---\nstatus: proposed\n---\n\n# App constitution\n\n"
        "## Context\nShoppers need a clear set of app rules.\n\n"
        "## Decision\nApprove the app constitution.\n\n"
        "## Consequences\nThe app follows its approved rules.\n", encoding="utf-8")
    constitution = decision_fix / "docs/product/CONSTITUTION.md"
    constitution.parent.mkdir(parents=True, exist_ok=True)
    constitution.write_text(
        "# App constitution\n\n## Defaults\nUse secure defaults.\n\n"
        "## Roles\nAdmin: all actions. Member: view and create.\n\n"
        "## Architecture choices\nUse Postgres for the basket.\n", encoding="utf-8")
    accepted = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi",
                          cwd=decision_fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    plan_created = repo.forge("decision", "new", "prototype-plan", cwd=decision_fix)
    assert plan_created.returncode == 0, plan_created.stdout + plan_created.stderr
    plan = next((decision_fix / "docs/decisions").glob("*-prototype-plan.md"))
    plan.write_text(plan.read_text(encoding="utf-8") +
                    "1. Save a basket.\n2. Find the basket.\n", encoding="utf-8")
    plan_accepted = repo.forge("decision", "accept", "prototype-plan", "--by", "Ravi",
                               cwd=decision_fix)
    assert plan_accepted.returncode == 0, plan_accepted.stdout + plan_accepted.stderr
    repo.git("add", "-A", cwd=decision_fix)
    repo.git("commit", "-q", "-m", "Accept the app constitution", cwd=decision_fix)
    decision_branch = repo.git("branch", "--show-current", cwd=decision_fix)
    repo.git("merge", "--ff-only", decision_branch, cwd=top)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main", cwd=top)
    story = repo.forge("story", "new", "SHOP", "Shoppers can save baskets", cwd=top)
    assert story.returncode == 0, story.stdout + story.stderr

    # An unrelated settings change does not trigger the Personal data refusal while the switch
    # remains on.
    started = repo.forge("fix", "start", "Adjust sample worker", "--done",
                         "forge.toml changes the worker setting", "--kind", "mechanical", cwd=top)
    assert started.returncode == 0, started.stdout + started.stderr
    unrelated = Path(re.search(r" in (.+)\n", started.stdout)[1])
    _settings(unrelated / "forge.toml", workers="codex")
    (unrelated / "app.py").write_text("print('sample data')\n", encoding="utf-8")
    repo.git("add", "-A", cwd=unrelated)
    repo.git("commit", "-q", "-m", "Adjust the sample worker", cwd=unrelated)
    env.reviews(CLEAN)
    env.open_pr("")
    env.checks(GREEN)
    unchanged_switch = env.close("adjust-sample-worker")
    assert unchanged_switch.returncode == 0, unchanged_switch.stdout + unchanged_switch.stderr
    assert "Personal data" not in unchanged_switch.stderr
    assert not marker.exists()

    # Close sees both false and removed settings as the same real-data transition.
    started = repo.forge("fix", "start", "Set up tests", "--done",
                         "forge.toml turns sample_data off", "--kind", "mechanical", cwd=top)
    assert started.returncode == 0, started.stdout + started.stderr
    item = "set-up-tests"
    where = Path(re.search(r" in (.+)\n", started.stdout)[1])
    if transition == "false":
        _settings(where / "forge.toml", sample_data=False)
    else:
        changed = (where / "forge.toml").read_text(encoding="utf-8")
        (where / "forge.toml").write_text(
            re.sub(r"(?m)^sample_data = true\n", "", changed), encoding="utf-8")
    (where / "app.py").write_text("print('real data starts here')\n", encoding="utf-8")
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-q", "-m", "Turn off sample data", cwd=where)
    env.reviews(CLEAN)
    env.open_pr("")
    env.checks(GREEN)

    for answer in ("not known yet (client, 2026-11-02)",
                   "no private or regulated data (client, 2026-11-02)"):
        refused = env.close(item)
        assert refused.returncode == 1, refused.stdout + refused.stderr
        assert "Personal data needs a settled answer before sample_data turns off." in refused.stderr
        assert f"write and commit the Personal data answer in docs/product/BRIEF.md, then forge close {item}" in refused.stderr
        brief = where / "docs/product/BRIEF.md"
        brief.write_text(re.sub(r"(?m)^- Personal data:.*$", f"- Personal data: {answer}",
                                brief.read_text(encoding="utf-8")), encoding="utf-8")
        repo.git("add", "docs/product/BRIEF.md", cwd=where)
        repo.git("commit", "-q", "-m", "Update the Personal data answer", cwd=where)

    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert marker.exists()
