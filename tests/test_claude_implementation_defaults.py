"""Claude defaults change for new settings and omitted entries, never explicit old pins.

Real Forge commands own the assertions; Claude, uv and GitHub are faked at their edges.
"""
import tomllib

from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only
from test_setup import _fresh_client
from test_story import DOC, GRILL, new_story, setup
from test_worker import calls, install_claude
from test_upgrade_command import (_repo_adopted_on_the_previous_release,
                                 unsynced_up)  # noqa: F401
from test_close import env  # noqa: F401

STORY = "FIX-CLAUDE-SONNET-DEFAULT"
SONNET = {"model": "claude-sonnet-5-5", "effort": "xhigh"}
OPUS = {"model": "claude-opus-5-5", "effort": "high"}


def test_init_claude_only_repo_uses_sonnet_implementation_and_opus_reads(repo, gh, tmp_path):
    client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    settings = client / "forge.toml"
    # Init writes both hosts. Choose Claude for this new client through its existing setting.
    settings.write_text(settings.read_text("utf-8").replace('workers = "split"',
                                                          'workers = "claude"'), "utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    config = tomllib.loads(settings.read_text("utf-8"))
    assert config["workers"] == "claude"
    models = config["models"]
    for kind in ("build", "fix", "lite", "design"):
        assert models[kind]["claude"] == SONNET
    assert models["grill"]["claude"] == OPUS
    assert "review" not in models  # Autoreview owns its model and effort defaults.
    frontend = (client / ".claude/agents/frontend.md").read_text("utf-8")
    assert 'model: "claude-sonnet-5-5"' in frontend and 'effort: "xhigh"' in frontend
    guide = (client / ".codex/skills/forge/SKILL.md").read_text("utf-8")
    assert "claude-sonnet-5-5" in guide and "xhigh" in guide
    assert "claude-opus-5-5" in guide and "high" in guide


def test_earlier_adopted_repo_keeps_model_pins_on_upgrade_and_gets_opt_in_notes(unsynced_up):
    up = unsynced_up
    _repo_adopted_on_the_previous_release(up)
    models = tomllib.loads(up.show("forge.toml"))["models"]
    assert models["grill"]["claude"] == {"model": "opus", "effort": "high"}
    assert models["design"]["claude"] == {"model": "claude-opus-5-5", "effort": "high"}
    for host in (".claude", ".codex"):
        notes = up.show(f"{host}/skills/forge/SKILL.md")
        assert "claude-sonnet-5-5" in notes and "xhigh" in notes
        assert 'model = "claude-sonnet-5-5", effort = "xhigh"' in notes
        assert 'model = "claude-opus-5-5", effort = "high"' in notes
        assert "Existing model entries stay unchanged" in notes


def test_plan_read_with_no_claude_entry_uses_builtin_opus_high(repo, tmp_path, monkeypatch):
    setup(repo)
    shop = new_story(repo, "SHOP")
    toml = shop / "forge.toml"
    toml.write_text(toml.read_text("utf-8").replace(GRILL, 'workers = "claude"\n'), "utf-8")
    (shop / "plans/SHOP.md").write_text(DOC, "utf-8")
    log = install_claude(repo)
    _claude_only(tmp_path, monkeypatch, repo.bin)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    result = repo.forge("read", "SHOP")
    assert result.returncode == 0, result.stdout + result.stderr
    assert calls(log)[-1]["args"][:5] == ["-p", "--model", "claude-opus-5-5", "--effort", "high"]
    assert "reader: claude (claude-opus-5-5)" in (shop / "plans/SHOP.read.md").read_text("utf-8")


def test_lite_and_fix_with_no_claude_entries_use_builtin_sonnet_xhigh(repo):
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Configure Claude workers")
    repo.git("push", "-q", "origin", "main")
    log = install_claude(repo)
    started = repo.forge("fix", "start", "Correct greeting", "--done", "Greeting is correct")
    assert started.returncode == 0, started.stdout + started.stderr
    for _ in range(2):
        result = repo.forge("work", "correct-greeting")
        assert result.returncode == 0, result.stdout + result.stderr
        assert calls(log)[-1]["args"][:5] == ["-p", "--model", "claude-sonnet-5-5", "--effort", "xhigh"]
