"""Every kind in forge.toml's [models] table may hold a codex and a claude entry; a single entry
counts for the family its model belongs to, and the other family gets no Forge model.

The worker tests run forge work on task BOARD/PAGE, with Codex through the stub app-server and
Claude through the stub claude; the review test runs forge close with only Claude installed.
"""
from __future__ import annotations

from pathlib import Path
import shutil

from test_close import ROOT, env  # noqa: F401  (env is a fixture)
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401  (sdk_data is a fixture)
from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only
from test_worker import calls as claude_calls, install_claude

STORY = "developers-use-claude-code-codex-or-both"
NOVA = 'model = "gpt-6-nova"\neffort = "high"\n'
OPUS = 'model = "opus"\neffort = "low"\n'


def _write(folder, workers: str, build: str) -> None:
    """The task's own forge.toml: these workers and this [models.build] section."""
    toml = folder / "forge.toml"
    head = toml.read_text("utf-8").split("\n[", 1)[0].rstrip("\n")
    toml.write_text(head.replace('workers = "codex"', f'workers = "{workers}"')
                    .replace('workers = "claude"', f'workers = "{workers}"') + "\n\n" + build,
                    encoding="utf-8")


def _work(repo, folder, workers: str, build: str) -> None:
    _write(folder, workers, build)
    done = repo.forge("work", "BOARD/PAGE")
    assert done.returncode == 0, done.stdout + done.stderr


def test_1_a_per_family_table_gives_each_family_its_own_entry(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    claude = install_claude(repo)
    build = f"[models.build.codex]\n{NOVA}\n[models.build.claude]\n{OPUS}"

    _work(repo, folder, "codex", build)
    assert _sent(calls, "thread/start")[-1]["config"] == {"model": "gpt-6-nova",
                                                          "model_reasoning_effort": "high"}
    _work(repo, folder, "claude", build)
    assert claude_calls(claude)[-1]["args"][:5] == ["-p", "--model", "opus", "--effort", "low"]


def test_2_a_single_entry_is_used_by_its_own_family(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    claude = install_claude(repo)

    _work(repo, folder, "codex", f"[models.build]\n{NOVA}")
    assert _sent(calls, "thread/start")[-1]["config"] == {"model": "gpt-6-nova",
                                                          "model_reasoning_effort": "high"}
    _work(repo, folder, "claude", f"[models.build]\n{OPUS}")
    assert claude_calls(claude)[-1]["args"][:5] == ["-p", "--model", "opus", "--effort", "low"]


def test_3_a_single_entry_asked_for_by_the_other_family_gives_no_model(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    claude = install_claude(repo)

    # A gpt model never reaches Claude, and a Claude model never reaches Codex: each runs on its
    # own settings instead.
    _work(repo, folder, "claude", f"[models.build]\n{NOVA}")
    args = claude_calls(claude)[-1]["args"]
    assert "--model" not in args and "--effort" not in args and "gpt-6-nova" not in args
    _work(repo, folder, "codex", f"[models.build]\n{OPUS}")
    assert not _sent(calls, "thread/start")[-1].get("config")


def test_4_the_review_takes_its_engine_s_entry(env, tmp_path, monkeypatch):
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + '\n[models.review.codex]\nmodel = "gpt-6-sol"\neffort = "xhigh"\n'
               + '\n[models.review.claude]\nmodel = "sonnet"\neffort = "medium"\n'
               + '\n[models.grill.claude]\nmodel = "opus"\neffort = "high"\n')
    env.repo.git("push", "-q", "origin", "main")
    _claude_only(tmp_path, monkeypatch, env.repo.bin,
                 (ROOT / "tests" / "stubs" / "autoreview").read_text("utf-8"))
    assert Path(shutil.which("gh")).parent == env.repo.bin
    item, _ = env.start_fix()
    env.open_pr("Readme greets new readers")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    [call] = env.review_calls()
    options = dict(zip(call["args"][::2], call["args"][1::2]))
    assert {name: options[name] for name in ("--engine", "--model", "--thinking")} == {
        "--engine": "claude", "--model": "claude=sonnet", "--thinking": "claude=medium"}
