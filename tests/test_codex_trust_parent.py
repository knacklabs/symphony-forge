"""Forge counts a project as trusted by Codex only on an exact trusted entry for its own folder or
main checkout, refuses otherwise, and names the one entry to add."""
import json
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FIX-CODEX-TRUST-PARENT"
ROW = "Codex doesn't trust this project"


def _fix(folder, config):
    return (f'open Codex here and trust the project, or add trust_level = "trusted" under '
            f'[projects.{json.dumps(str(folder))}] in {config}')


@pytest.mark.parametrize("history", ["new", "adopted"])
def test_1_trust_follows_codex_rule(repo, gh, tmp_path, monkeypatch, history):
    if history == "new":  # a client repo made by forge init
        client, init = _fresh_client(repo, gh, tmp_path)
        assert init.returncode == 0, init.stdout + init.stderr
    else:  # a client adopted on an earlier release
        client = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client, dirs_exist_ok=True)
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-qm", "Adopt the earlier release", cwd=client)
    main = client.resolve()
    worktree = (tmp_path / "work" / "client-FIX").resolve()  # where Forge puts a worktree
    repo.git("worktree", "add", "-q", "-b", "fix/w", str(worktree), cwd=client)
    codex = tmp_path / "codex"
    codex.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex))
    config = codex / "config.toml"

    def doctor(entries):
        config.write_text("".join(f'[projects.{json.dumps(key)}]\ntrust_level = "{level}"\n'
                                  for key, level in entries), encoding="utf-8")
        return repo.forge("doctor", cwd=worktree).stdout

    # A trusted parent folder doesn't count: Forge asks and names the main checkout's entry.
    said = doctor([(str(tmp_path.resolve()), "trusted")])
    assert ROW in said and _fix(main, config) in said, said
    assert "a parent folder's entry does not count" in said, said
    # The main checkout's exact entry covers the worktree.
    assert ROW not in doctor([(str(main), "trusted")])
    # The worktree's own untrusted entry refuses, even with a trusted main checkout.
    said = doctor([(str(main), "trusted"), (str(worktree), "untrusted")])
    assert ROW in said and (f'set trust_level = "trusted" under [projects.{json.dumps(str(worktree))}] '
                            f"in {config}; a parent folder's entry does not count") in said, said
