"""The deny hook lets rm -rf clear the system temp folder and lets git config values be read."""
from __future__ import annotations

import json
from pathlib import Path

STORY = "FIX-THE-DESTRUCTIVE-COMMAND-GUARD-BLOCKS-RM"
DESTROY = "because it can destroy work that cannot be recovered."
HOOKS = "because the git hooks must run on every commit and push."


def _check(repo, builders, command: str, cwd: Path):
    for build in builders:
        payload = build("PreToolUse", "Bash", {"command": command}, cwd=cwd)
        yield repo.forge("hook", "deny", input=json.dumps(payload))


def test_1_rm_rf_inside_the_system_temp_folder(repo, claude_payload, codex_payload, tmp_path,
                                                monkeypatch):
    scratch = tmp_path / "scratch"
    (scratch / "clone").mkdir(parents=True)
    (scratch / "home-link").symlink_to(Path.home())
    monkeypatch.setenv("TMPDIR", str(scratch))
    outside = Path(__file__).resolve().parent  # the checkout, never inside a temp folder
    builders = (claude_payload, codex_payload)
    allowed = {
        "rm -rf /tmp/forge-scratch-clone": outside,
        "rm -rf /private/tmp/forge-scratch-clone": outside,
        'rm -rf "$TMPDIR/clone"': outside,
        "rm -fr $TMPDIR/clone /tmp/other-clone": outside,
        'rm -r -f -- "$TMPDIR/clone"': outside,
    }
    # Only a command that is rm alone, on absolute or $TMPDIR paths, is allowed: anything before
    # the rm could change the folder or the variable it relies on.
    blocked = {
        "cd /etc && rm -rf config": scratch,
        'TMPDIR=/etc; rm -rf "$TMPDIR/config"': outside,
        'TMPDIR=/etc rm -rf "$TMPDIR/config"': outside,
        "export TMPDIR=/etc\nrm -rf $TMPDIR/config": outside,
        "rm -rf '$TMPDIR/config'": outside,
        "rm -rf ${TMPDIR}/clone": outside,
        "git status && rm -rf /tmp/a": outside,
        "(rm -rf /tmp/a)": outside,
        "sudo rm -rf /tmp/a": outside,
        "rm -rf clone": scratch,
        "rm -rf /tmp": outside,
        "rm -rf /tmp/": outside,
        "rm -rf /tmp/../etc": outside,
        "rm -rf /tmp/a/../../etc": outside,
        "rm -rf /tmp/clone build": outside,
        "rm -rf build": outside,
        "rm -rf ../..": scratch,
        "rm -rf $TMPDIR/home-link/Documents": outside,
        "rm -rf /tmp/$UNSET_FORGE_VAR": outside,
        "rm -rf /tmp/*": outside,
        "rm -rf ~/clone": outside,
        "ls /tmp | xargs rm -rf": outside,
        "find /tmp -exec rm -rf {} +": scratch,
    }
    for command, cwd in allowed.items():
        for result in _check(repo, builders, command, cwd):
            assert (result.returncode, result.stderr) == (0, ""), command
    for command, cwd in blocked.items():
        for result in _check(repo, builders, command, cwd):
            assert result.returncode == 2 and DESTROY in result.stderr, command


def test_2_reading_a_git_config_value(repo, claude_payload, codex_payload):
    builders = (claude_payload, codex_payload)
    for command in ("git config --get core.hooksPath", "git config core.hooksPath",
                    "git config --global --get core.hooksPath",
                    "git -C web config --get-all core.hooksPath"):
        for result in _check(repo, builders, command, repo.path):
            assert (result.returncode, result.stderr) == (0, ""), command
    for command in ("git config core.hooksPath /dev/null", "git config --unset core.hooksPath",
                    "git config --global core.hooksPath .hooks",
                    "git -c core.hooksPath=/dev/null config --get user.name"):
        for result in _check(repo, builders, command, repo.path):
            assert result.returncode == 2 and HOOKS in result.stderr, command
