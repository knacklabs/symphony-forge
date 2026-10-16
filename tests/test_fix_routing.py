"""Fix kind in src/forge/task.py stays the same across worker tools and repeat rounds."""
import json
import shutil

import pytest

from test_close import env  # noqa: F401
from test_codex_worker import ROOT, _codex_repo, _sent, sdk_data  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_setup import _fresh_client
from test_worker import calls, install_claude

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
