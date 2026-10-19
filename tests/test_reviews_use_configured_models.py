"""Review settings reach Autoreview for new and earlier-adopted clients."""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-HONOUR-REVIEW-MODEL"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
@pytest.mark.parametrize("family,entry,model,effort", [
    ("codex", "", "", ""),
    ("codex", "review", "gpt-6-astra", "max"),
    ("codex", "review", "gpt-6.1-sol", ""),
    ("codex", "review.codex", "gpt-6.1-sol", "high"),
    ("claude", "review.claude", "claude-sonnet-5-5", "low"),
])
def test_1_reviews_use_configured_model_and_effort_or_tool_defaults(
        env, tmp_path, adopted, family, entry, model, effort):
    # Protect the real close -> external reviewer boundary: the stub only records argv
    # and returns a clean report; it never selects the model or effort for Forge.
    repo = env.repo
    if adopted:
        client = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client,
                        dirs_exist_ok=True)
        config = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(re.sub(r'^version = .*$', f'version = "{version}"',
                                config.read_text("utf-8"), flags=re.M), "utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
    else:
        client, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Review settings", "--done", "Reviews use settings",
                         "--kind", "backend")
    assert started.returncode == 0, started.stdout + started.stderr
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    config = where / "forge.toml"
    text = config.read_text("utf-8")
    # The earlier release included a review pin. Removing it must restore tool defaults.
    text = re.sub(r'\n\[models\.review(?:\.[^\]]+)?\][^\[]*', '', text)
    text = f'tools = "{family}"\n' + text
    if entry:
        text += f'\n[models.{entry}]\nmodel = "{model}"\n'
        if effort:
            text += f'effort = "{effort}"\n'
    env.commit(where, "forge.toml", text, "Choose review settings")
    env.checks(GREEN)
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "--allow-empty", "-qm", "Sync client files", cwd=where)
    result = env.close("review-settings")
    assert result.returncode == 0, result.stdout + result.stderr
    [call] = env.review_calls()
    args = call["args"]
    assert args[args.index("--engine") + 1] == family
    for flag, value in (("--model", model), ("--thinking", effort)):
        if value:
            assert args[args.index(flag) + 1] == f"{family}={value}"
        else:
            assert flag not in args
