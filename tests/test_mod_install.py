"""Real Claude installation from an isolated, local tagged marketplace.

The stub command tests own failure handling and argv. This independently detects
an install Claude rejects, a failed reload or a pane that cannot read either
current or old Forge. Claude's real CLI decides installation and rendering;
the fixture supplies no install receipt, enabled setting or Forge command result.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

import pytest

from conftest import ROOT, _install, patient
from test_setup import _on_a_branch_with_forge_toml

REAL_CLAUDE = shutil.which("claude")


def real_claude_sync_installs_from_local_release_tag(repo, tmp_path, monkeypatch):
    if not REAL_CLAUDE:
        pytest.skip("Real Claude Code is not installed; the plugin CI job installs its pinned version.")
    _on_a_branch_with_forge_toml(repo)
    _install(repo.bin, "claude", f'''#!{sys.executable}
import os, sys
os.execv({json.dumps(REAL_CLAUDE)}, [{json.dumps(REAL_CLAUDE)}, *sys.argv[1:]])
''')
    home = tmp_path / "isolated-home"
    patient(lambda: home.mkdir())
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    scratch = home / "tmp"
    patient(lambda: scratch.mkdir())
    for name in ("TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME"):
        monkeypatch.setenv(name, str(scratch))
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.setenv(name, "")
    # A parent Claude session can inject its own inline plugin even with an
    # isolated home. Keep security configuration; discard only parent identity,
    # messaging and plugin paths so these sessions load their actual install.
    for name in (
        "CLAUDECODE", "CLAUDE_PID", "CLAUDE_CODE_BRIDGE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
        "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_EXECPATH", "CLAUDE_CODE_MESSAGING_SOCKET",
        "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_PLUGIN_DIRS", "CLAUDE_CODE_SESSION_ATTENDED",
        "CLAUDE_CODE_SESSION_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    # No authentication or host settings: installation itself needs no model.
    for name in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    version = re.search(r'__version__ = "([^"]+)"', (ROOT / "src/forge/__init__.py").read_text("utf-8"))[1]
    release = tmp_path / "local release with spaces"
    patient(lambda: release.mkdir())
    patient(lambda: shutil.copytree(ROOT / "src/forge/mod", release / "src/forge/mod"))
    repo.git("init", "-q", "-b", "main", str(release))
    repo.git("add", "-A", cwd=release)
    repo.git("commit", "-q", "-m", "Local mod release", cwd=release)
    repo.git("tag", "v" + version, cwd=release)
    market = tmp_path / "marketplace"
    patient(lambda: (market / ".claude-plugin").mkdir(parents=True))
    # Keep the shipped version/path/ref; only replace the remote transport so
    # real Claude installs this checkout's own mod files without the network.
    manifest = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text("utf-8"))
    plugin = manifest["plugins"][0]
    plugin["source"]["url"] = release.as_uri()
    (market / ".claude-plugin/marketplace.json").write_text(json.dumps(manifest), encoding="utf-8")

    def claude(*args):
        result = subprocess.run([REAL_CLAUDE, *args], cwd=repo.path, env=os.environ.copy(),
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    # Register the public marketplace name from a local path first: sync's
    # normal update/install commands then use only local git, with no network.
    claude("plugin", "marketplace", "add", str(market))
    assert not json.loads(claude("plugin", "list", "--json"))
    (home / ".claude/settings.json").write_text("{}", encoding="utf-8")
    current_path = os.environ["PATH"]

    def install():
        # The session is already running without the mod. Sync changes only the
        # user install; /reload-plugins must make it live in the native pane.
        with monkeypatch.context() as local:
            local.setenv("PATH", current_path)
            synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        installed = json.loads(claude("plugin", "list", "--json"))
        entry = next((row for row in installed if row["id"] == "forge@forge"), None)
        assert entry is not None, installed
        assert entry["scope"] == "user" and entry["enabled"] is True
        assert entry["version"] == version
        claude("plugin", "validate", "--strict", entry["installPath"])

    _reload_and_open_installed_mod(repo.path, home, "Nothing in progress.", install)
    claude("plugin", "uninstall", "forge@forge", "--scope", "user")
    assert not json.loads(claude("plugin", "list", "--json"))
    old_bin = tmp_path / "old-bin"
    patient(lambda: old_bin.mkdir())
    _old_forge(old_bin, tmp_path, "forge")
    old_repo = tmp_path / "old repo with spaces"
    patient(lambda: old_repo.mkdir())
    repo.git("init", "-q", "-b", "main", str(old_repo))
    monkeypatch.setenv("PATH", f"{old_bin}{os.pathsep}{current_path}")
    _reload_and_open_installed_mod(old_repo, home,
                                  "This repo's Forge is too old for the pane: upgrade Forge here.", install)


def _reload_and_open_installed_mod(folder, home, expected, install):
    if os.name == "nt":
        pytest.skip("The real interactive PTY lifecycle runs in the pinned Linux plugin job; Windows command transport has separate coverage.")
    import pty
    import select
    import signal
    import struct
    import termios
    import fcntl

    # Ordinary isolated client preferences bypass onboarding, not mod loading.
    (home / ".claude/.claude.json").write_text(json.dumps({
        "hasCompletedOnboarding": True, "lastOnboardingVersion": "2.1.291", "theme": "dark",
        "projects": {str(folder): {"hasTrustDialogAccepted": True, "hasCompletedProjectOnboarding": True}},
    }), encoding="utf-8")
    environment = os.environ.copy()
    environment.update(TERM="xterm-256color", ANTHROPIC_API_KEY="offline-test-key",
                       CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 180, 0, 0))
    process = subprocess.Popen([REAL_CLAUDE, "--setting-sources", "user", "--ax-screen-reader",
                                "--debug-file", "/dev/stderr"], cwd=folder,
                               env=environment, stdin=slave, stdout=slave, stderr=slave,
                               start_new_session=True)
    os.close(slave)
    output = ""

    def until(pattern):
        nonlocal output
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if re.search(pattern, output, re.I) or re.search(pattern, re.sub(r"\s+", "", output), re.I):
                return
            if process.poll() is not None:
                break
            ready, _, _ = select.select([master], [], [], max(0, deadline - time.monotonic()))
            if ready:
                try:
                    chunk = os.read(master, 65536).decode("utf-8", errors="replace")
                except OSError:
                    break
                output += re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", chunk)
        raise AssertionError(f"Claude did not show {pattern!r}: {output[-6000:]}")

    try:
        until("DoyouwanttousethisAPIkey\\?")
        os.write(master, b"y\r")
        until("Notloggedin|APIUsageBilling")
        until("effort:medium.*?/effort")
        assert "Nothing in progress." not in output and "upgrade Forge here." not in output
        output = ""
        install()
        # Claude debounces its settings watcher. Wait for the real running
        # client to acknowledge this external write before asking it to reload.
        until("Detected change to " + re.escape(str(home / ".claude/settings.json")))
        output = ""
        os.write(master, b"/reload-plugins")
        until("/reload-plugins")
        output = ""
        os.write(master, b"\r")
        until(r"reload(?:ed|ing).*plugin|plugin.*reload(?:ed|ing)")
        # No /forge command is sent: its independent text reply cannot satisfy
        # this check. The wide terminal must draw the native Board pane itself.
        until(re.escape(re.sub(r"\s+", "", expected)) + r"✕")
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        os.close(master)


def _old_forge(bin_dir, tmp_path, command):
    old = tmp_path / "old-forge"
    patient(lambda: shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old))
    patient(lambda: (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py"))
    _install(bin_dir, command, f'''#!{sys.executable}
import sys
sys.path.insert(0, {json.dumps(str(old / 'src'))})
from forge.cli import main
sys.exit(main())
''')


def mod_reads_real_old_forge_refusal_and_spaced_working_directory(repo, tmp_path, monkeypatch):
    from test_mod_plugin import HOST, node_run

    _old_forge(repo.bin, tmp_path, "old-forge")
    folder = tmp_path / "Windows repo with spaces"
    patient(lambda: folder.mkdir())
    repo.git("init", "-q", "-b", "main", str(folder))
    refusal = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "board", "--json"],
                             cwd=folder, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert refusal.returncode != 0 and "unrecognized arguments: --json" in refusal.stderr
    # The host is only Claude's API transport. Both the old-version refusal and
    # the ordinary refresh failure come from Forge's real command entry points.
    answers = node_run(tmp_path, HOST + f'''
const mod = await import({json.dumps((ROOT / 'src/forge/mod/hooks/register.ts').as_uri())});
let old = true;
const api = {{
  session: {{cwd: async () => {json.dumps(str(folder))}}},
  clock: {{now: async () => 0, every: () => ({{cancel(){{}}}})}},
  command: {{register: async () => {{}}}},
  ui: {{invalidate() {{}}, open: async () => ({{isPlaced: false}})}},
  process: {{run: async (argv, init) => {{
    assert.deepEqual(argv, ['forge', argv[1], '--json']);
    assert.equal(init.cwd, {json.dumps(str(folder))});
    try {{
      return {{exitCode: 0, stderr: '', stdout: execFileSync({json.dumps(sys.executable)},
        [old ? {json.dumps(str(repo.bin / 'old-forge'))} : {json.dumps(str(repo.bin / 'forge'))}, ...argv.slice(1)],
        {{cwd: init.cwd, encoding: 'utf8', timeout: init.timeoutMs}})}};
    }} catch (e) {{return {{exitCode: e.status ?? 1, stdout: String(e.stdout ?? ''), stderr: String(e.stderr ?? '')}}}}
  }}}},
}};
mod.register(on);
await fire('session.start', {{cwd: {json.dumps(str(folder))}, surface: null, isInteractive: false}}, api);
const before = (await fire('command.run', {{command: 'forge'}}, api)).text;
old = false;
await fire('session.start', {{cwd: {json.dumps(str(folder))}, surface: null, isInteractive: false}}, api);
const after = (await fire('command.run', {{command: 'forge'}}, api)).text;
console.log(JSON.stringify({{before, after}}));
''')
    too_old = "This repo's Forge is too old for the pane: upgrade Forge here."
    assert too_old in answers["before"]
    assert too_old not in answers["after"] and "Couldn't refresh:" in answers["after"]
