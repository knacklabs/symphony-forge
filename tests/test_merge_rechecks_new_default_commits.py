"""Merge checks each new default-branch move without another human command."""
import json
import sys

import pytest

from conftest import _install
from test_close import env  # noqa: F401
from test_merge_refreshes_behind_base import _client, _github_moves_default

STORY = "FIX-MERGE-RETRIES-WHEN-MAIN-MOVES"


# Test audit: the public merge command must accept unrelated late commits, retest
# overlapping late commits, and stop at five moves. The old late-test cases only
# require a refusal after one move. Real git commits cause the race and real
# client assertions decide test success; only GitHub is faked. No new seam.
# Permission audit: accepting a late disjoint forge.toml commit must honor the
# owner's current merge setting. Prior cases never revoke permission. Extend
# this same command boundary with real remote settings, without a new seam.
@pytest.mark.parametrize("previous,case,moves", [
    (False, "unrelated", 1), (True, "unrelated", 1),
    (False, "overlap", 2), (False, "limit", 5), (False, "red", 1),
    (False, "disabled", 1), (True, "disabled", 1),
], ids=["new-unrelated", "adopted-unrelated", "two-overlaps", "five-moves", "late-red",
        "new-disabled", "adopted-disabled"])
def test_1_merge_rechecks_new_commits_until_clear_or_five_moves(env, tmp_path, previous, case, moves):
    log = _client(env, tmp_path, previous)
    other = tmp_path / "other-change"
    _, setup = env.start("test-setup", "fix/test-setup", ".factory/fixes/test-setup.json",
                         {"kind": "fix", "why": "Check the combined client",
                          "done_when": "Client assertions check the combined change"}, {})
    command = f'"{sys.executable}" verify.py'
    config = (setup / "forge.toml").read_text("utf-8").replace(
        '"python verify.py"', json.dumps(command))
    if case == "disabled":
        config = config.replace('stage = "prototype"', 'stage = "live"')
    env.commit(setup, "forge.toml", config)
    env.commit(setup, "verify.py", (
        "import json, pathlib, subprocess\n"
        f"log = pathlib.Path({json.dumps(log.as_posix())})\n"
        "head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
        "with log.open('a', encoding='utf-8') as out:\n"
        "    out.write(json.dumps(head) + '\\n')\n"
        "assert pathlib.Path('app.py').read_text().startswith('print(')\n"
        "assert 'Broken closing' not in pathlib.Path('README.md').read_text()\n"
        "count = len(log.read_text().splitlines())\n"
        f"other = pathlib.Path({json.dumps(other.as_posix())})\n"
        f"if count <= {moves}:\n"
        + ("    path = other / 'forge.toml'\n"
           "    text = path.read_text().replace('merge = \"agent\"', 'merge = \"human\"')\n"
           "    path.write_bytes(text.encode('utf-8'))\n" if case == "disabled" else
           "    path = other / 'other.txt'\n"
           "    path.write_bytes(str(count).encode('utf-8'))\n" if case == "unrelated" else
           "    path = other / 'README.md'\n"
           "    lines = path.read_text().splitlines()\n"
           + ("    lines[-1] = 'Broken closing'\n" if case == "red" else
              "    lines[-1] = f'Closing {count}'\n")
           + "    path.write_bytes(('\\n'.join(lines) + '\\n').encode('utf-8'))\n")
        + "    subprocess.run(['git', 'add', path.name], cwd=other, check=True)\n"
        "    subprocess.run(['git', 'commit', '-qm', 'Another change lands'], cwd=other, check=True)\n"
        "    subprocess.run(['git', 'push', '-q', 'origin', 'main'], cwd=other, check=True)\n"))
    env.repo.git("merge", "-q", "--ff-only", "fix/test-setup")
    remote = env.repo.git("remote", "get-url", "origin")
    env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=remote)
    item, where = env.start_fix({"app.py": "print('hello')\n",
                                 "README.md": "Branch greeting\n\nKeep this paragraph.\n\nOld closing\n"})
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    original = env.repo.git("rev-parse", "HEAD", cwd=where)
    reviews = len(env.review_calls())
    env.repo.git("clone", "-q", remote, str(other))
    if case == "unrelated":
        # A later disjoint move must not repeat the first overlapping retest
        # or its push/check wait. The older late-test cases start disjoint.
        env.commit(other, "README.md", "Original greeting\n\nKeep this paragraph.\n\nFirst closing\n")
    else:
        env.commit(other, "initial.txt", "The first move triggers combined tests.\n")
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    _github_moves_default(env, False, "CLEAN")
    stub = (env.repo.bin / "gh").read_text("utf-8")
    stub = stub.replace('    subprocess.run(["git", "merge-base", "--is-ancestor", marker.read_text(), "FETCH_HEAD"],\n'
                        '                   cwd=checkout, check=True)\n', '')
    _install(env.repo.bin, "gh", stub)
    (env.repo.bin / "default-moved").write_text(
        env.repo.git("rev-parse", "HEAD", cwd=other), encoding="utf-8")

    result = env.repo.forge("merge", item)

    tested = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    attempts = env.gh_calls("pr", "merge")
    assert len(env.review_calls()) == reviews
    if case == "disabled":
        assert result.returncode != 0, result.stdout + result.stderr
        assert not attempts
        assert len(tested) == 1
        assert 'forge merge is disabled by merge = "human" in the default branch\'s forge.toml.' in result.stderr
        assert "Next: the repo owner runs forge merge enable in their own terminal" in result.stderr
        assert 'merge = "human"' in env.repo.git("show", "main:forge.toml", cwd=remote)
        assert 'merge = "agent"' in (where / "forge.toml").read_text("utf-8")
    elif case in {"limit", "red"}:
        assert result.returncode != 0, result.stdout + result.stderr
        assert not attempts
        assert len(tested) == (5 if case == "limit" else 2)
        message = ("The default branch moved five times after the retest. Run forge merge again."
                   if case == "limit" else "The combined change failed its tests.")
        assert message in result.stderr
        assert f"Next: forge {'merge' if case == 'limit' else 'work'} {item}" in result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(attempts) == 1
        assert len(tested) == (1 if case == "unrelated" else 3)
        published = attempts[0][attempts[0].index("--match-head-commit") + 1]
        assert published != original
        assert env.repo.git("show", "origin/main:app.py") == "print('hello')"
        assert env.repo.git("show", "origin/main:README.md").startswith("Branch greeting")
        if case == "overlap":
            assert env.repo.git("show", "origin/main:README.md").endswith("Closing 2")
        assert any(f"/commits/{published}/" in call[-1] for call in env.gh_calls("api"))
