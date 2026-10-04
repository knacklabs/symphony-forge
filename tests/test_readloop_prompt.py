STORY = "FORGE-READLOOP-1"
# What the cold reader is asked each round, and what the synced skill tells the agent to do with
# its findings.

import json
import os
from pathlib import Path

from conftest import _install
from test_codex_reader import GRILL
from test_codex_worker import ROOT, _sent, _toml
from test_codex_worker import sdk_data  # noqa: F401  (a fixture)
from test_discovery import HOSTS, _client
from test_phases import _flat
from test_story import DOC, new_story, setup

TEMPLATE = Path(__file__).resolve().parents[1] / "src" / "forge" / "templates" / "cold-read.md"


def _parts() -> tuple[str, str]:
    """The shipped prompt's first-round and next-round parts, whitespace flattened."""
    text = TEMPLATE.read_text("utf-8")
    first, rest = text.split("<!-- forge:round -->\n")
    round_part, _notes = rest.split("<!-- forge:notes -->\n")
    return _flat(first), _flat(round_part)


def _skills(repo, gh, tmp_path) -> list[str]:
    client = _client(repo, gh, tmp_path)  # forge init syncs the skill into a new client repo
    return [_flat((client / host / "skills/forge/SKILL.md").read_text("utf-8")) for host in HOSTS]


def _first_round_prompt(repo, monkeypatch, sdk_data, tmp_path) -> str:  # noqa: F811
    """The prompt Codex received from a real `forge read` of a story branch made before a trap
    landed on the default branch."""
    setup(repo)
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests" / "stubs" / "codex-app-server").read_text(encoding="utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    (tmp_path / "codex-home").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    # Codex runs project hooks, Forge's guard among them, only in a project it trusts.
    ((tmp_path / "codex-home") / "config.toml").write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    monkeypatch.delenv("CODEX_THREAD_ID")
    monkeypatch.setenv("CLAUDECODE", "1")  # under Claude Code the reader is Codex
    shop = new_story(repo, "SHOP")
    # A trap learned on the default branch after the story branch was made; the same heading
    # inside Forge's block is not the repo's own.
    repo.write("AGENTS.md", "<!-- forge:begin -->\n## Known traps\n\n- Forge's own line.\n"
                            "<!-- forge:end -->\n\n## Known traps\n\n"
                            "- Fixture paths break on Windows.\n")
    repo.git("add", "AGENTS.md")
    repo.git("commit", "-q", "-m", "Learn a trap")
    repo.git("push", "-q", "origin", "main")
    agents = shop / "AGENTS.md"
    assert "Fixture paths" not in (agents.read_text("utf-8") if agents.exists() else "")
    (shop / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    (shop / "forge.toml").write_text(_toml(version, "claude", GRILL), encoding="utf-8")

    read = repo.forge("read", "SHOP", cwd=shop)
    assert read.returncode == 0, read.stdout + read.stderr
    return _sent(repo.bin / "codex-app-server.jsonl", "turn/start")[-1]["input"][0]["text"]


def test_3_kept_findings_are_settled_not_argued(repo, gh, tmp_path):
    _first, round_part = _parts()
    for placeholder in ("$round", "$path", "$diff", "$dispositions", "$spec_diff", "$next",
                        "$traps"):
        assert placeholder in round_part, placeholder
    for gone in ("$doc", "$findings"):
        assert gone not in round_part, gone
    for rule in ("you are continuing your own earlier read",
                 "Open `$path` and read the whole doc again yourself",
                 "Your last round's findings, and any older finding whose disposition changed "
                 "since then, each with its disposition: $dispositions",
                 "the confirmed spec's diff since your last round, empty when it is unchanged: "
                 "$spec_diff When that diff is not empty, check the plan still matches the "
                 "changed spec.",
                 "Re-read the `## Answers` section of `docs/product/BRIEF.md` from the checkout",
                 "Is each of those findings closed?",
                 "Raise a kept finding again only when you disagree with its stated reason, as "
                 "`Disputed keep <n>: <why>`",
                 "Never raise again a finding whose disposition cites a `Decided:` line",
                 "Look for new gaps anywhere in the doc",
                 "a numbered list starting at $next",
                 "write exactly `No findings.` and nothing else"):
        assert rule in round_part, rule
    for skill in _skills(repo, gh, tmp_path):
        for step in ("`Disputed keep <n>: <why>`",
                     "Put it to the human as one question with options",
                     "record the answer in the doc's Notes as "
                     "`Decided: <finding>: <answer> (owner, <date>)`",
                     "give both the kept finding and the disputed one the disposition `keep` "
                     "citing that line"):
            assert step in skill, step


def test_4_the_reader_hunts_edge_cases(repo, gh, monkeypatch, sdk_data, tmp_path):  # noqa: F811
    # Inputs and failures still matter; one test proves a rule that can cover several cases.
    first, _round = _parts()
    prompt = _flat(_first_round_prompt(repo, monkeypatch, sdk_data, tmp_path))
    for question in ("which inputs and states it must handle",
                     "Windows PowerShell and cmd, WSL, macOS, Linux CI",
                     "which failure and refusal paths it has",
                     "which test, in which task's Tests cell, proves each rule",
                     "`Unproven: item <n>: <case>`", "`Trap: <trap>: item <n>`"):
        assert question in first, question
        assert question in prompt, question
    for skill in _skills(repo, gh, tmp_path):
        assert ("`Unproven: item <n>: <case>` or `Trap: <trap>: item <n>`: add the case to that "
                "Done-when item and its test to the Tests cell of the task that owns it. Never "
                "resolve one only in Notes.") in skill


def test_5_known_traps_are_shipped_and_learned(repo, gh, monkeypatch, sdk_data,  # noqa: F811
                                               tmp_path):
    first, round_part = _parts()
    for trap in ("Windows line endings and shells", "no network in CI",
                 "a new settings key the installed Forge rejects",
                 "documentation tasks skipping their required tests",
                 "tests that fail only under machine load",
                 "values a frontend build fixes at build time",
                 "This repository's own known traps, from its AGENTS.md: $traps"):
        assert trap in first, trap
    assert "known traps: $traps" in round_part
    for skill in _skills(repo, gh, tmp_path):
        for step in ("Before closing the story's last task, look back at the story's "
                     "review rounds",
                     "cost two or more fix rounds", "hit two or more tasks",
                     "add one trap line to the `## Known traps` section of the repo's AGENTS.md, "
                     "outside Forge's block, in the last task's worktree",
                     "create the section when it is missing",
                     "Commit it before closing the task"):
            assert step in skill, step
    prompt = _first_round_prompt(repo, monkeypatch, sdk_data, tmp_path)
    assert "Cold read of SHOP." in prompt
    for leaked in ("<!-- forge:round -->", "Round $round", "$traps", "Forge's own line."):
        assert leaked not in prompt, leaked
    assert "own known traps, from its AGENTS.md:\n\n- Fixture paths break on Windows.\n" in prompt
    for trap in ("Windows line endings and shells", "no network in CI"):
        assert trap in _flat(prompt), trap
