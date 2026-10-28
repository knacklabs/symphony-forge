"""Prototype workers receive the demo proof contract on both tools and repeat rounds.

The contract protects the brief delivered at work, not its template implementation.
The regression is a normal full-proof brief leaking into a requested prototype.
Design-context tests check design delivery, not prototype test scope. No new seam
is needed: real work delivers the brief to the third-party SDK stub.
"""
import pytest

from test_close import env  # noqa: F401
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_design_context import prepare
from test_worker import calls, install_claude


STORY = "FORGE-PACE-1"


@pytest.mark.parametrize("family", ["claude", "codex"])
def test_35_prototype_rounds_prove_only_demo_steps_and_boundaries(env, monkeypatch, sdk_data, family):
    repo = env.repo
    codex_log = prepare(env, monkeypatch, sdk_data, family, prototype=True)
    item, where = env.start_fix(fix_kind="backend", allow_large="Prototype before sign-off")
    env.commit(where, "docs/decisions/0001-prototype-build.md",
               '---\nstatus: accepted\nconfirmed_by: "Owner"\n---\n'
               '# Working build\n\n## Context\nThe canvas cannot prove speed.\n')
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setenv("CLAUDECODE" if family == "codex" else "CODEX_THREAD_ID", "1")
    claude_log = install_claude(repo)
    for _ in range(2):
        built = repo.forge("work", item)
        assert built.returncode == 0, built.stdout + built.stderr
        prompt = (_sent(codex_log, "turn/start")[-1]["input"][0]["text"] if family == "codex"
                  else calls(claude_log)[-1]["brief"])
        assert "## Prototype proof" in prompt
        proof = prompt.split("## Prototype proof", 1)[1]
        for text in ("demo workflow steps", "security", "data boundaries", "per-function proof",
                     "full proof is due at sign-off"):
            assert text in proof
