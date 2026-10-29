"""Low defaults reach new clients without changing an earlier client's model pins."""
import json
import tomllib

from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import (RELEASE, _repo_adopted_on_the_previous_release,
                                 unsynced_up)  # noqa: F401
from test_worker import install_claude

STORY = "FORGE-EFFORT-1"


def test_2_new_repos_start_low(env, tmp_path):
    repo = env.repo
    client, initialized = _fresh_client(repo, env.gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    settings = client / "forge.toml"
    models = tomllib.loads(settings.read_text("utf-8"))["models"]
    # Old defaults were medium for Codex and xhigh for Claude. Only these three
    # implementation kinds now start low; read and review pins are explicit.
    for kind in ("build", "fix", "lite"):
        for family, model in (("codex", "gpt-6.1-sol"), ("claude", "claude-sonnet-5-5")):
            assert models[kind][family]["model"] == model
            assert models[kind][family]["effort"] == "low"
    for kind in ("grill", "review"):
        assert models[kind]["claude"] == {"model": "claude-sonnet-5-5", "effort": "high"}
    repo.path = client
    # Select the test's tool through the clone-local override. Keep init's actual
    # defaults in forge.toml and avoid a settings commit on an unregistered branch.
    repo.write("forge.local.toml", 'tools = "claude"\nworkers = "claude"\n')
    install_claude(repo)
    item, _ = env.start_fix()
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    events = [json.loads(line) for line in
              (client / ".git/forge/events.jsonl").read_text("utf-8").splitlines()]
    first = next(row for row in events if row["event"] == "run start"
                 and row.get("kind") == "worker")
    assert (first["model"], first["effort"]) == ("claude-sonnet-5-5", "low")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    [call] = env.review_calls()
    args = call["args"]
    assert args[args.index("--model") + 1] == "claude=claude-sonnet-5-5"
    assert args[args.index("--thinking") + 1] == "claude=high"


def test_2_existing_forge_toml_is_not_changed(unsynced_up):
    up = unsynced_up
    original = (up.repo.path / "forge.toml")
    # Upgrade a real earlier-adopted fixture, not current init with an old pin.
    _repo_adopted_on_the_previous_release(up)
    earlier = original.read_bytes()
    upgraded = up.folder / "forge.toml"
    assert upgraded.read_bytes() == earlier.replace(b'"v1.2.2"', f'"{RELEASE}"'.encode())
    before = upgraded.read_bytes()
    synced = up.repo.forge("sync", cwd=up.folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert upgraded.read_bytes() == before
    # This release wrote Codex-only implementation pins. Claude's omitted entries
    # use the new fallback, while the explicit Codex pins stay byte for byte.
    install_claude(up.repo)
    up.repo.write("forge.local.toml", 'workers = "claude"\n')
    for kind in ("backend", "mechanical"):
        started = up.repo.forge("fix", "start", f"Check {kind} default", "--done",
                                "The default applies", "--kind", kind, cwd=up.folder)
        assert started.returncode == 0, started.stdout + started.stderr
        item = f"check-{kind}-default"
        worked = up.repo.forge("work", item, cwd=up.folder)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        assert "(claude-sonnet-5-5, low)" in worked.stdout
    assert upgraded.read_bytes() == before
