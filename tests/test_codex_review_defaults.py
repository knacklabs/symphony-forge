"""New clients pass their pinned Codex review defaults to Autoreview."""
from pathlib import Path

from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-REVIEW-ON-TERRA-MAX"


def test_1_new_clients_review_on_terra_at_max(env, tmp_path):
    # Contract: init's defaults reach the real close boundary. A missing review
    # pin would silently use Autoreview's defaults instead. The configured-model
    # tests replace init's entries, so cannot catch this. No production seam is needed.
    repo = env.repo
    client, initialized = _fresh_client(repo, env.gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.path = client
    repo.git("push", "-q", "origin", "main")
    repo.write("forge.local.toml", 'tools = "codex"\n')
    started = repo.forge("fix", "start", "Check default review", "--done", "The review uses Terra",
                         "--kind", "backend")
    assert started.returncode == 0, started.stdout + started.stderr
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    env.commit(where, "README.md", "Client guide.\n", "Add client guide")
    env.checks(GREEN)
    closed = env.close("check-default-review")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    [call] = env.review_calls()
    args = call["args"]
    assert args[args.index("--model") + 1] == "codex=gpt-6.1-terra"
    assert args[args.index("--thinking") + 1] == "codex=max"
