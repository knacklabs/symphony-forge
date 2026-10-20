"""Fix kind in src/forge/task.py stays the same across worker tools and repeat rounds."""
import json
import shlex
import shutil
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_codex_worker import ROOT, _codex_repo, _sent, sdk_data  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_setup import _fresh_client
from test_worker import calls, install_claude
from test_next_names_a_failed_scheduled_run import RUNS, LOG, runs
from test_spotted import entry, LIST
from test_measure import SPEC
from test_story import prototype_design

pytestmark = pytest.mark.platform

STORY = "FORGE-PACE-1"


@pytest.mark.parametrize("family", ["codex", "claude"])
@pytest.mark.parametrize("kind,model_kind", [("ui", "design"), ("backend", "build"),
                                            ("mechanical", "lite")])
@pytest.mark.parametrize("adopted", [False, True], ids=["new-prototype", "upgraded-client"])
def test_2_fix_kind_selects_the_same_worker_on_every_round(repo, gh, tmp_path, monkeypatch, sdk_data,
                                                         family, kind, model_kind, adopted):
    # The old contract forced all prototype fixes to design and changed Codex's second round
    # to models.fix. Distinct settings expose either mistake at the worker process edge.
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        repo.path = client
    repo.git("switch", "-qc", "fix/worker-settings")
    repo.write(".factory/fixes/worker-settings.json", json.dumps({
        "kind": "fix", "branch": "fix/worker-settings", "why": "Choose worker settings",
        "done_when": "The workers have distinct models"}))
    _, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True, start_task=False)
    # Both tools use their real kit here, with only their third-party executables stubbed.
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    claude_log = install_claude(repo)
    config = repo.path / "forge.toml"
    head = config.read_text("utf-8").split("\n[", 1)[0]
    head = head.replace('workers = "codex"', f'workers = "{family}"')
    if not adopted:
        head += '\nstage = "prototype"\n'
    for name, effort in (("build", "medium"), ("fix", "high"), ("lite", "low"),
                         ("design", "xhigh")):
        model = f"gpt-6-{name}" if family == "codex" else f"claude-{name}"
        head += f'\n[models.{name}.{family}]\nmodel = "{model}"\neffort = "{effort}"\n'
    config.write_text(head, encoding="utf-8")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    prototype_design(repo)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set distinct worker models")
    _publish_default(repo, repo.git("remote", "get-url", "origin"))
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/worker-settings")
    # Live repos keep their short command; its default is the mechanical worker.
    flags = [] if adopted and kind == "mechanical" else ["--kind", kind]
    started = repo.forge("fix", "start", "Repair the app", "--done", "The app works", *flags)
    assert started.returncode == 0, started.stdout + started.stderr
    folder = repo.path.parent / f"{repo.path.name}-fix-repair-the-app"
    (repo.path / "forge.local.toml").write_text(f'workers = "{family}"\n', encoding="utf-8")
    shown = repo.forge("next", cwd=folder)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    line = next(line for line in shown.stdout.splitlines()
                if line.startswith("Next: forge work repair-the-app"))
    assert f"{family.title()} builds it" in line and f"models.{model_kind}" in line, line
    # Changing the allowance must not change the kind the start command recorded.
    for round_number in range(2):
        if round_number:
            state_file = folder / ".factory/fixes/repair-the-app.json"
            state = json.loads(state_file.read_text("utf-8"))
            state["allow_large"] = "Owner permits this change"
            state_file.write_text(json.dumps(state), encoding="utf-8")
            repo.git("commit", "-qam", "Record the allowance", cwd=folder)
        worked = repo.forge("work", "repair-the-app")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        expected = f"gpt-6-{model_kind}" if family == "codex" else f"claude-{model_kind}"
        assert expected in worked.stdout
        if family == "codex":
            sent = _sent(codex_log, "thread/start") + _sent(codex_log, "thread/resume")
            assert sent[-1]["config"]["model"] == expected
        else:
            assert calls(claude_log)[-1]["options"]["model"] == expected


@pytest.mark.parametrize("kind,path,warns", [("backend", "web/page.html", True),
    ("ui", "src/server.py", True), ("mechanical", "src/server.py", True),
    ("backend", "src/server.py", False), ("ui", "web/page.html", False),
    ("mechanical", "docs/readme.md", False), ("mechanical", "src/test_server.py", False)])
def test_21_close_warns_about_a_kind_mismatch_without_blocking(env, kind, path, warns):
    repo = env.repo
    started = repo.forge("fix", "start", "Repair the app", "--done", "The app works",
                         "--kind", kind)
    assert started.returncode == 0, started.stdout + started.stderr
    folder = repo.path.parent / "repo-fix-repair-the-app"
    env.commit(folder, path, "# app\n")
    closed = env.close("repair-the-app")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert ("Warning: The changed files do not match this fix's worker kind" in closed.stdout) == warns
    assert env.review_calls(), "The warning must still allow review"


def test_22_prototype_fixes_require_a_kind_before_a_checkout_exists(repo):
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\nstage = "prototype"\n')
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Start a prototype")
    repo.git("push", "-q", "origin", "main")
    refused = repo.forge("fix", "start", "Repair the app", "--done", "The app works")
    assert refused.returncode == 1
    assert refused.stderr == (
        "A prototype fix needs --kind ui, backend or mechanical.\n"
        'Next: forge fix start "<why>" --done "<done when>" --kind <kind>\n')
    assert not repo.git("branch", "--list", "fix/repair-the-app")
    assert not (repo.path.parent / "repo-fix-repair-the-app").exists()
    invalid = repo.forge("fix", "start", "Repair the app", "--done", "The app works",
                         "--kind", "other")
    assert invalid.returncode == 1
    assert "invalid choice" in invalid.stderr
    assert not repo.git("branch", "--list", "fix/repair-the-app")


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption"])
@pytest.mark.parametrize("case,path,kind,match", [
    ("idle", None, "mechanical", '"Find the problem to solve"'),
    ("roadmap", None, "mechanical", '"<why>"'),
    ("schedule", None, "mechanical", '"The scheduled'),
    ("hotspot", "src/server.py", "backend", '"Simplify src/server.py:'),
    ("hotspot", "web/page.html", "ui", '"Simplify web/page.html:'),
    ("hotspot", "src/components/page.ts", "ui", '"Simplify src/components/page.ts:'),
    ("hotspot", "docs/guide.md", "mechanical", '"Simplify docs/guide.md:'),
    ("refresh", None, "mechanical", '--slug refresh-dependencies'),
    ("measure", None, "mechanical", '"Record the invoices success result"'),
])
def test_23_prototype_next_fix_commands_run_as_printed(repo, gh, tmp_path, monkeypatch,
                                                      adopted, case, path, kind, match):
    # Direct fix-start tests cannot catch missing options in the preceding guidance command.
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        repo.path, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    repo.git("switch", "-qc", "fix/next-settings")
    version = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8")
    if adopted:
        repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"')
                   .replace('stage = "live"', 'stage = "prototype"'))
    repo.write(".factory/fixes/next-settings.json", json.dumps({
        "kind": "fix", "branch": "fix/next-settings", "why": "Prepare next guidance",
        "done_when": "The guidance has its input files"}))
    if case == "roadmap":
        repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "PENDING"}]}))
    elif case == "hotspot":
        repo.write(path, "Sample\n")
        repo.write(LIST, json.dumps({"items": [entry("bug", path, 1, text, "worker")
                                               for text in ("First", "Second", "Third")]}))
    elif case == "schedule":
        repo.write(".github/workflows/forge-next-1.yml", "name: forge-next\n")
        gh.respond(*RUNS, stdout=runs((7, 1, "forge-next", "failure")))
        gh.respond("run", "view", "7", "--log-failed", stdout=LOG)
    elif case == "refresh":
        repo.write("uv.lock", "version = 1\n")
    elif case == "measure":
        repo.write("docs/specs/invoices.md", "---\nstatus: confirmed\n---\n" + SPEC)
        repo.write("plans/roadmap.json", json.dumps({"items": [
            {"key": "INV-1", "spec": "docs/specs/invoices.md"}]}))
        repo.write(".factory/stories/INV-1/story.json", json.dumps({"status": "done"}))
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-09-01T10:00:00+00:00")
    prototype_design(repo)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Prepare guidance inputs")
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    _publish_default(repo, repo.git("remote", "get-url", "origin"))
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/next-settings")
    monkeypatch.setenv("FORGE_NOW", "2030-02-01T10:00:00+00:00")
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    command = next(line for line in shown.stdout.splitlines()
                   if line.startswith("Next: forge fix start ") and match in line)
    words = shlex.split(command.removeprefix("Next: forge "))
    started = repo.forge(*words)
    assert started.returncode == 0, started.stdout + started.stderr
    assert words[words.index("--kind") + 1] == kind
    checkout = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    assert checkout.is_dir()
