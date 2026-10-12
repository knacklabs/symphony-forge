"""A real coordinating process owns read places, chats and round hand-backs."""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from concurrent.futures import Future
from pathlib import Path

import pytest

from conftest import machine_cores
from test_codex_reader import GRILL
from test_codex_worker import _toml
from test_fix_agent_runs_wait_in_line import _until
from test_story import DOC, new_story, setup

STORY = "FORGE-TOOLS-1"

# Only the host is a shim: every child runs the real command and real OS identity lookup.
LAUNCHER = r"""
const {spawn, spawnSync} = require('node:child_process');
const readline = require('node:readline');
const children = new Set();
const input = readline.createInterface({input: process.stdin});
function stop() {
    for (const child of children) {
      if (process.platform === 'win32') {
        spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F']);
      } else {
        try { process.kill(-child.pid, 'SIGTERM'); }
        catch (error) { if (error.code !== 'ESRCH') throw error; }
      }
    }
    input.close();
    process.stdin.destroy();
}
process.on('SIGTERM', stop);
input.on('line', line => {
  const request = JSON.parse(line);
  if (request.stop) {
    stop();
    return;
  }
  const child = spawn(request.command[0], request.command.slice(1), {
    cwd: request.cwd, env: request.env, stdio: ['pipe', 'pipe', 'pipe'],
    detached: process.platform !== 'win32'
  });
  children.add(child);
  let stdout = '', stderr = '';
  child.stdout.on('data', chunk => stdout += chunk);
  child.stderr.on('data', chunk => stderr += chunk);
  child.on('close', code => {
    children.delete(child);
    console.log(JSON.stringify({id: request.id, code, stdout, stderr}));
  });
  child.stdin.end(request.input);
});
"""


class Session:
    """A named Node parent survives commands, including concurrently queued commands."""

    def __init__(self, repo, directory, name):
        directory.mkdir()
        binaries = directory / "bin"
        binaries.mkdir()
        executable = binaries / (name + (".exe" if os.name == "nt" else ""))
        node = shutil.which("node")
        assert node, "Forge's Node runtime is needed to launch a real coordinating process"
        library = Path(node).resolve().parent.parent / "lib"
        if sys.platform == "darwin" and library.is_dir():
            # Homebrew's binary resolves libnode relative to its bin directory.
            (directory / "lib").symlink_to(library, target_is_directory=True)
        shutil.copy2(node, executable)
        launcher = directory / "session.cjs"
        launcher.write_text(LAUNCHER, "utf-8")
        self.repo, self.pending, self.closed = repo, {}, False
        # Exit the bootstrap before commands: an outer real app must not become this host's owner.
        bootstrap = ("import json,subprocess,sys; child=subprocess.Popen(sys.argv[1:], "
                     "stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr); "
                     "print(json.dumps({'pid':child.pid}),flush=True)")
        self.process = subprocess.Popen([sys.executable, "-c", bootstrap,
                                         str(executable), str(launcher)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding="utf-8")
        self.pid = json.loads(self.process.stdout.readline())["pid"]
        assert self.process.wait(timeout=15) == 0
        self.reader = threading.Thread(target=self._receive, daemon=True)
        self.reader.start()

    def _receive(self):
        for line in self.process.stdout:
            result = json.loads(line)
            self.pending[result["id"]].set_result(subprocess.CompletedProcess(
                [], result["code"], result["stdout"], result["stderr"]))
        error = self.process.stderr.read()
        for future in self.pending.values():
            if not future.done():
                future.set_exception(RuntimeError("Coordinating process exited: " + error))

    def start(self, *args, cwd=None, input=""):
        number = len(self.pending)
        future = self.pending[number] = Future()
        command = [sys.executable, "-c", "import subprocess,sys; sys.exit(subprocess.call(sys.argv[1:]))",
                   sys.executable, str(self.repo.bin / "forge"), *args]
        request = {"id": number, "command": command,
                   "cwd": str(cwd or self.repo.path), "env": dict(os.environ), "input": input}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        return future

    def forge(self, *args, **kwargs):
        return self.start(*args, **kwargs).result(timeout=120)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.reader.is_alive():
                self.process.stdin.write('{"stop":true}\n')
                self.process.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            self.process.stdin.close()
        self.reader.join(timeout=15)
        if self.reader.is_alive():
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.pid), "/T", "/F"],
                               capture_output=True, timeout=15)
            else:
                try:
                    os.kill(self.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            self.reader.join(timeout=10)
        assert not self.reader.is_alive()
        self.process.stdout.close()
        self.process.stderr.close()


@pytest.mark.parametrize("tool,host", [("codex", "codex-session"), ("claude", "claude-session"),
                                      ("codex", "node")])
def test_4_session_holds_handed_out_reads(repo, gh, monkeypatch, tmp_path, tool, host):
    # Unlike READS' result test, this owns OS-session lifetime and admission safety.
    setup(repo, keys=("SHOP", "WISH"))
    machine_cores(repo, 2)
    if tool == "claude":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-chat")
    version = repo.forge("--version").stdout.split()[-1]
    config = _toml(version, "split", GRILL).replace(
        'workers = "split"', f'workers = "split"\ntools = "{tool}"')
    shop, wish = (new_story(repo, key) for key in ("SHOP", "WISH"))
    for checkout, key in ((shop, "SHOP"), (wish, "WISH")):
        (checkout / f"plans/{key}.md").write_text(DOC, "utf-8")
        (checkout / "forge.toml").write_text(config, "utf-8")
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text("\n".join(
        f'[projects.{json.dumps(str(checkout))}]\ntrust_level = "trusted"'
        for checkout in (shop, wish)), "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))

    sessions = []

    def open_session(name=host):
        owner = Session(repo, tmp_path / f"owner-{len(sessions)}", name)
        sessions.append(owner)
        return owner

    def lanes():
        result = repo.forge("lanes", "--json")
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)["agents"]["entries"]

    def offer(owner, key="SHOP"):
        result = owner.forge("read", key)
        assert result.returncode == 0, result.stdout + result.stderr
        handed = json.loads(result.stdout)
        assert isinstance(handed["round"], int)
        assert f'--round {handed["round"]}' in handed["instruction"]
        return handed

    def back(owner, handed, key="SHOP", text="No findings."):
        return owner.forge("handback", key, "--round", str(handed["round"]),
                           "--subagent", "reader-chat", "--text", text)

    def success(result):
        assert result.returncode == 0, result.stdout + result.stderr

    try:
        first = open_session()
        initial = offer(first)
        [entry] = lanes()
        assert entry["item"] == "SHOP" and entry["kind"] == "read" and entry["native"] is True
        duplicate = first.forge("read", "SHOP")
        assert duplicate.returncode == 1 and "already running" in duplicate.stderr
        assert [row["id"] for row in lanes()] == [entry["id"]]
        other = open_session()
        foreign = back(other, initial)
        assert foreign.returncode == 1
        assert "This session has no pending read for that target." in foreign.stderr
        assert [row["id"] for row in lanes()] == [entry["id"]]
        # Reads wait on the model's service, not this machine, so a second read takes no
        # place and starts while the first session still holds its read.
        result = other.start("read", "WISH").result(timeout=120)
        success(result)
        wish_offer = json.loads(result.stdout)
        assert sorted((row["item"], row["place"]) for row in lanes()) == [("SHOP", 0), ("WISH", 0)]
        first.close()
        _until(lambda: [row["item"] for row in lanes()] == ["WISH"], "the closed session's read to leave")
        [entry] = lanes()
        assert entry["item"] == "WISH" and entry["native"] is True
        success(back(other, wish_offer, "WISH"))
        assert lanes() == []

        initial = offer(other)
        success(back(other, initial))
        doc = shop / "plans/SHOP.md"
        doc.write_text(doc.read_text("utf-8") + "\nSaved baskets expire after thirty days.\n", "utf-8")
        # A cleared conversation keeps the same process; its old subagent may still be reachable.
        monkeypatch.setenv("CODEX_THREAD_ID" if tool == "codex" else "CLAUDE_SESSION_ID",
                           "cleared-conversation")
        continued = offer(other)
        assert continued["subagent"] == "reader-chat"
        assert continued["prompt"] != continued["fresh_prompt"]
        instruction = continued["instruction"].splitlines()
        assert "continue" in instruction[0].lower()
        assert "start fresh" in instruction[1].lower() and "whole brief" in instruction[1].lower()
        success(back(other, continued))
        other.close()
        fresh_owner = open_session()
        doc.write_text(doc.read_text("utf-8") + "\nExpired baskets may be saved again.\n", "utf-8")
        fresh = offer(fresh_owner)
        assert fresh["subagent"] is None and fresh["prompt"] == fresh["fresh_prompt"]
        assert "because the session that ran its last round has ended" in fresh["reason"]
        next_result = repo.forge("next")
        success(next_result)
        assert "handback" in next_result.stdout and f'--round {fresh["round"]}' in next_result.stdout
        assert "Next: forge read SHOP" not in next_result.stdout
        stopped = fresh_owner.forge("stop", "SHOP")
        success(stopped)
        assert "Stopped Forge's hold; stop the subagent in your session too." in stopped.stdout
        success(fresh_owner.forge("--version"))
        assert lanes() == []
        after_stop = repo.forge("next")
        success(after_stop)
        assert "Next: forge read SHOP" in after_stop.stdout
        replacement = offer(fresh_owner)
        assert replacement["round"] > fresh["round"]
        assert f"Round {replacement['round']}" in replacement["prompt"]
        stale = back(fresh_owner, fresh)
        assert stale.returncode == 1
        assert "That round was stopped or replaced, so Forge recorded nothing." in stale.stderr
        assert [row["item"] for row in lanes()] == ["SHOP"]
        success(back(fresh_owner, replacement))
        assert lanes() == []

        # A missing host refuses before the read commits edited input or changes the item.
        doc.write_text(doc.read_text("utf-8") + "\nThe shopper can rename a basket.\n", "utf-8")
        head = repo.git("rev-parse", "HEAD", cwd=shop)
        state = (shop / ".factory/stories/SHOP/story.json").read_bytes()
        notes = (shop / "plans/SHOP.read.md").read_bytes()
        missing_host = open_session("python-host")
        missing = missing_host.forge("read", "SHOP")
        assert missing.returncode == 1
        app = "Claude Code" if tool == "claude" else "Codex"
        assert f"Forge cannot find the coordinating {app} session; nothing ran." in missing.stderr
        assert repo.git("rev-parse", "HEAD", cwd=shop) == head
        assert (shop / ".factory/stories/SHOP/story.json").read_bytes() == state
        assert (shop / "plans/SHOP.read.md").read_bytes() == notes
        assert lanes() == []
        with monkeypatch.context() as no_session:
            for name in ("CODEX_THREAD_ID", "CLAUDECODE", "CLAUDE_SESSION_ID"):
                no_session.delenv(name, raising=False)
            refused = repo.forge("read", "SHOP")
        assert refused.returncode == 1
        assert ("Forge runs this repo's work inside a Claude Code or Codex session, and none is "
                "open here, so nothing ran.") in refused.stderr
        assert "open one in this repo and run forge read SHOP there" in refused.stderr
        assert repo.git("rev-parse", "HEAD", cwd=shop) == head
        assert (shop / ".factory/stories/SHOP/story.json").read_bytes() == state
        assert (shop / "plans/SHOP.read.md").read_bytes() == notes
        assert lanes() == []
    finally:
        for owner in reversed(sessions):
            owner.close()
