"""forge close runs the repo's test command and hands its result to the reviewer."""
from __future__ import annotations

import subprocess
import sys

from test_close import env  # noqa: F401

STORY = "FIX-REVIEWERS-CAN-T-SEE-TESTS-THAT-ONLY-RUN"

SUITE = '''import pytest


def test_greets():
    assert True


@pytest.mark.skipif(True, reason="needs a service outside the sandbox")
def test_outside():
    assert True
'''


def _with_test_command(env, suite: str) -> None:
    toml = env.repo.path / "forge.toml"
    command = f"{sys.executable} -m pytest -q -p no:cacheprovider checks"
    env.commit(env.repo.path, "forge.toml",
               toml.read_text("utf-8") + f"test = {command!r}\n".replace("'", '"')
               + f"fast_test = {command!r}\n".replace("'", '"'))
    env.commit(env.repo.path, "checks/test_suite.py", suite)
    env.repo.git("push", "-q", "origin", "main")


def test_1_close_runs_a_passing_test_command_and_shows_the_reviewer(env):
    _with_test_command(env, SUITE.split("\n\n@pytest")[0] + "\n")
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    result = env.prompt().split("## Tests on the close run", 1)[1].split("\n## ", 1)[0]
    assert "passed" in result
    assert "1 passed" in result


def test_2_close_lists_skipped_tests_with_their_reason(env):
    _with_test_command(env, SUITE)
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    result = env.prompt().split("## Tests on the close run", 1)[1].split("\n## ", 1)[0]
    assert "1 passed, 1 skipped" in result
    assert "needs a service outside the sandbox" in result


def test_3_brief_says_close_run_skips_and_deletion_tests_count(env):
    _with_test_command(env, SUITE)
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    prompt = " ".join(env.prompt().split())
    assert "A test skipped in your sandbox that the close run passed is not a missing test" in prompt
    assert "a pure deletion" in prompt
    assert "old input is now refused is enough" in prompt


# What `go test -v ./...` prints for a skipped test; the passing tests after it push the skip out
# of the output's last 30 lines.
GO_STYLE = '''print("=== RUN   TestOutside")
print("    outside_test.go:9: needs a service outside the sandbox")
print("--- SKIP: TestOutside (0.00s)")
for n in range(40):
    print(f"=== RUN   TestGreets{n}")
    print(f"--- PASS: TestGreets{n} (0.00s)")
print("PASS")
print("ok  \texample.com/app\t0.01s")
'''


def test_4_close_shows_a_go_style_skip_and_its_reason(env):
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "gotest.py", GO_STYLE)
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + f"test = {f'{sys.executable} gotest.py'!r}\n".replace("'", '"')
               + f"fast_test = {f'{sys.executable} gotest.py'!r}\n".replace("'", '"'))
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    result = env.prompt().split("## Tests on the close run", 1)[1].split("\n## ", 1)[0]
    assert "exited with status 0" in result
    assert "--- SKIP: TestOutside (0.00s)" in result
    assert "needs a service outside the sandbox" in result
    assert "ok  \texample.com/app\t0.01s" in result


def test_5_close_runs_the_test_command_merged_from_the_default_branch(env):
    _with_test_command(env, SUITE)
    item, _ = env.start_fix()
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml",
               toml.read_text("utf-8").replace("-p no:cacheprovider", "-p no:cacheprovider -v"))
    env.repo.git("push", "-q", "origin", "main")
    assert env.close(item).returncode == 0
    result = env.prompt().split("## Tests on the close run", 1)[1].split("\n## ", 1)[0]
    assert "-p no:cacheprovider -v checks` exited" in result


def test_6_forge_init_in_a_go_repo_writes_a_test_command_that_prints_skips(repo, gh, tmp_path):
    # Plain `go test ./...` prints only a package's "ok" line, so skips and reasons never show.
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    (client / "go.mod").write_text("module example.com/app\n\ngo 1.22\n", encoding="utf-8")
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    initialized = repo.forge("init", cwd=client)
    assert initialized.returncode == 0, initialized.stderr
    toml = (client / "forge.toml").read_text(encoding="utf-8")
    assert 'test = "go test -v ./..."' in toml
