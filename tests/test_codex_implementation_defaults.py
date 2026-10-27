"""New client implementation defaults use Terra; explicit older choices stay owned by clients."""
import tomllib

from test_setup import _fresh_client

STORY = "forge-s-default-codex-implementation-mod"


def test_init_uses_terra_high_for_codex_implementation(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    models = tomllib.loads((client / "forge.toml").read_text("utf-8"))["models"]
    for kind in ("build", "fix", "lite", "explore"):
        chosen = models[kind]["codex"]
        assert (chosen["model"], chosen["effort"]) == ("gpt-6.1-terra", "high"), kind
    for kind in ("lite", "explore"):
        chosen = models[kind]["codex"]
        assert (chosen["subagents"], chosen["subagent_effort"]) == ("gpt-6-luna", "max")
