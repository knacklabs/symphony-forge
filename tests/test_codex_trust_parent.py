"""Forge trusts a project exactly when Codex does, and says which folder's entry to add.

Codex (codex-rs/config/src/loader/mod.rs, decision_for_dir, at rust-v0.159.2) reads only exact
[projects] entries: the checkout's own, then its main checkout's; the first one with a trust level
decides. A parent folder's entry counts for neither.
"""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FIX-CODEX-TRUST-PARENT"
ROW = "Codex doesn't trust this project"


def _fix(folder, config):
    return (f'open Codex here and trust the project, or set trust_level = "trusted" under '
            f'[projects."{folder}"] in {config}')


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
        config.write_text("".join(f'[projects."{path.as_posix()}"]\ntrust_level = "{level}"\n'
                                  for path, level in entries), encoding="utf-8")
        return repo.forge("doctor", cwd=worktree).stdout

    # A trusted parent folder: Codex would still ask, so Forge asks and names the main checkout.
    said = doctor([(tmp_path.resolve(), "trusted")])
    assert ROW in said and _fix(main, config) in said, said
    assert "not a parent folder's" in said and "covers every worktree" in said, said
    # The main checkout's entry covers the worktree, as it does for Codex.
    assert ROW not in doctor([(main, "trusted")])
    # The worktree's own untrusted entry is closer, so it wins over the main checkout's.
    said = doctor([(main, "trusted"), (worktree, "untrusted")])
    assert ROW in said and _fix(worktree, config) in said, said
