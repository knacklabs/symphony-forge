"""Close distinguishes Forge's prototype allowance from agent-recorded allowances.

The former covers size and interfaces; the latter still needs a diff check.
The regression reaches the reviewer prompt through real init/sync, fix start and close.
Only GitHub and the external reviewer are faked, not the allowance or prompt.
"""
import json
import shutil
from pathlib import Path

import pytest

import conftest
from test_close import env  # noqa: F401
from test_setup import _fresh_client
from test_story import worktree

STORY = "prototype-allowance-review"


@pytest.mark.parametrize("adoption", ["new", "earlier release"])
def test_1_prototype_allowance_covers_size_and_interfaces_without_diff_check(env, tmp_path, adoption):
    repo = env.repo
    config = ((repo.path / "forge.toml").read_text("utf-8")
              + '\nrepo = "client"\nstage = "prototype"\n')
    if adoption == "new":
        client, made = _fresh_client(repo, env.gh, tmp_path)
        assert made.returncode == 0, made.stderr
        repo = env.repo = conftest.Repo(client, repo.bin)
    else:
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        assert 'version = "v1.2.2"' in (repo.path / "forge.toml").read_text("utf-8")
    repo.git("switch", "-q", "-c", "fix/refresh-client")
    repo.write(".factory/fixes/refresh-client.json", json.dumps({
        "kind": "fix", "status": "working", "branch": "fix/refresh-client",
        "why": "Refresh the client", "done_when": "The client uses current Forge"}))
    repo.write("forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Refresh the client")
    repo.git("push", "-q", "origin", "HEAD:refs/heads/refreshed")
    remote = Path(repo.git("remote", "get-url", "origin"))
    repo.git("update-ref", "refs/heads/main", repo.git("rev-parse", "HEAD"), cwd=remote)
    repo.git("fetch", "-q", "origin", "main")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/refresh-client")

    started = repo.forge("fix", "start", "Show a prototype", "--done", "The prototype shows",
                         "--kind", "ui")
    assert started.returncode == 0, started.stderr
    folder = worktree(repo, "fix/show-a-prototype")
    # More than five code files, including an interface, need no agent allowance.
    for n in range(6):
        env.commit(folder, f"app/routes/view{n}.py", "print('prototype')\n")
    closed = env.close("show-a-prototype")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = " ".join(env.prompt().split())
    assert "Recorded allowance: Prototype before sign-off" in prompt
    assert ('Forge records the "Prototype before sign-off" allowance. It covers any size and '
            'interface changes. Do not check this allowance against the diff.') in prompt
    assert ("For other agent-recorded allowances to correct one kind of problem everywhere "
            "without changing an interface, check the reason against the whole diff.") in prompt
    assert ("Report as P1 an allowance whose reason doesn't match the diff: more than one kind "
            "of problem, or an interface change") in prompt
