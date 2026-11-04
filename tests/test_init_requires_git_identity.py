"""Init refuses an unusable Git identity before it changes a repository."""
import pytest

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_live_adopt import ANSWERS

STORY = "FIX-INIT-CHECKS-GIT-IDENTITY"


@pytest.mark.parametrize("existing", [False, True], ids=["new-repo", "existing-repo"])
def test_1_init_refuses_before_writes_and_names_git_config(repo, gh, tmp_path, monkeypatch, existing):
    client = repo.path if existing else _new_repo(repo, gh, tmp_path)
    # Empty values prevent Git from guessing an identity from the machine account.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    for index, key in enumerate(("user.name", "user.email")):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{index}", key)
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{index}", "")
    before = {p.relative_to(client).as_posix(): p.read_bytes()
              for p in client.rglob("*") if p.is_file() and ".git" not in p.relative_to(client).parts}
    branches = repo.git("for-each-ref", cwd=client)
    worktrees = repo.git("worktree", "list", "--porcelain", cwd=client)

    done = repo.forge("init", *(ANSWERS if existing else ("--actions", "yes")), cwd=client)

    assert done.returncode != 0, done.stdout + done.stderr
    after = {p.relative_to(client).as_posix(): p.read_bytes()
             for p in client.rglob("*") if p.is_file() and ".git" not in p.relative_to(client).parts}
    assert after == before
    assert repo.git("for-each-ref", cwd=client) == branches
    assert repo.git("worktree", "list", "--porcelain", cwd=client) == worktrees
    output = done.stdout + done.stderr
    assert 'git config user.name "Your Name"' in output
    assert 'git config user.email "you@example.com"' in output
    assert "doctor" not in output.lower()
