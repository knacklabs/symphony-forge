STORY = "FORGE-UPGRADE-1"
"""Doctor says which Forge version it compares the synced files with.

Each test is named test_<n>_ after the story's Done-when item it proves.
"""
import json
import os
import re

import pytest

from test_setup import _autoreview, _executable, _fresh_client, _stub_forge, _version

INSTALL = "uv tool install git+https://github.com/knacklabs/symphony-forge@{pin}"


def _compared(installed: str, pinned: str) -> str:
    if pinned == installed:
        return f"- Note: doctor compared the synced files with the installed Forge {installed}.\n"
    return (f"- Note: doctor compared the synced files with the installed Forge {installed}, not "
            f"the pinned {pinned}.\n  To check with {pinned}: {INSTALL.format(pin=pinned)}, then "
            "run forge doctor again.\n")


# Old contract: the comparison note appeared only when the pin differed from the installed Forge,
# so a failing doctor with a matching pin never said which version it compared with. New
# contract: it says so whenever it compared, drifted or clean, whatever else fails, and says it
# couldn't compare, and why, when forge sync can't work out what it would write.
@pytest.mark.parametrize("case", ["clean", "drifted", "old pin clean", "old pin drifted",
                                  "all is well", "can't compare"])
def test_5_doctor_says_which_forge_version_it_compares_with(repo, gh, tmp_path, monkeypatch,
                                                            case):
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    installed = "v" + _version(repo).removeprefix("v")
    toml = client / "forge.toml"
    pinned = "v0.0.1" if case.startswith("old pin") else installed
    toml.write_text(re.sub(r'version = ".*"', f'version = "{pinned}"',
                           toml.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    drift = case.endswith("drifted")
    if drift:
        (client / ".claude/skills/remote-approval/SKILL.md").write_text("old\n", encoding="utf-8")
    if case == "can't compare":  # a broken Forge block stops forge sync working out its files
        (client / "AGENTS.md").write_text("<!-- forge:end -->\nOurs.\n<!-- forge:begin -->\n",
                                          encoding="utf-8")
    if case == "all is well":
        toml.write_text(toml.read_text(encoding="utf-8").replace(
            'workers = "split"', 'workers = "claude"', 1), encoding="utf-8")
        (tmp_path / "home").mkdir()
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
        codex_home = tmp_path / "codex"
        codex_home.mkdir()
        monkeypatch.setenv("CODEX_HOME", str(codex_home))
        (codex_home / "config.toml").write_text(
            f'[projects.{json.dumps(str(client))}]\ntrust_level = "trusted"\n', encoding="utf-8")
        _executable(repo.bin / "claude", "#!/bin/sh\n")
        if os.name == "nt":
            (repo.bin / "claude.cmd").write_text("@exit /b 0\n", encoding="utf-8")
        _stub_forge(tmp_path, monkeypatch)
    else:
        gh.respond("auth", "status", exit=1)  # another check fails too

    done = repo.forge("doctor", cwd=client)

    if case == "all is well":
        assert done.returncode == 0, done.stdout + done.stderr
        # The verdict leads; the comparison line follows it.
        assert done.stdout == (f"Everything checks out for Forge {installed}.\n"
                               + _compared(installed, installed)), done.stdout
        return
    assert done.returncode == 1, done.stdout + done.stderr
    assert "- gh is not signed in to GitHub.\n  Fix: gh auth login\n" in done.stdout, done.stdout
    if case == "can't compare":
        assert ("- doctor couldn't compare the synced files with what forge sync writes: "
                "AGENTS.md has a broken Forge block; keep one <!-- forge:begin --> line and, after "
                "it, one <!-- forge:end --> line.\n  Fix: forge sync\n") in done.stdout, done.stdout
        assert "compared the synced files with the installed Forge" not in done.stdout, done.stdout
        assert "differs from what forge sync writes" not in done.stdout, done.stdout
        return
    assert _compared(installed, pinned) in done.stdout, done.stdout
    row = (f".claude/skills/remote-approval/SKILL.md differs from what forge sync writes for "
           f"the installed Forge {installed}.")
    assert (row in done.stdout) == drift, done.stdout
