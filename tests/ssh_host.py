"""A stand-in for a Linux machine reached with ssh: a folder with its own home, programs and git.

The `ssh` program it installs runs the command with `sh -c` in that home. Like the real ssh, it
relays its pipes, so ending it closes the command's stdin. Not a test file.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import FORGE_SHIM, ROOT, _install

SSH = '''#!{python}
import json, os, subprocess, sys, threading
hosts = {hosts!r}
args, host, command, i = sys.argv[1:], None, "", 0
while i < len(args):
    if args[i] in ("-o", "-p", "-l", "-i", "-F"):
        i += 2
    elif args[i].startswith("-"):
        i += 1
    else:
        host, command = args[i], " ".join(args[i + 1:])
        break
home = os.path.join(hosts, host or "", "home")
with open(os.path.join(hosts, "ssh-calls.jsonl"), "a", encoding="utf-8") as log:
    log.write(json.dumps({{"host": host, "command": command}}) + "\\n")
def cut(text):
    print(text, file=sys.stderr)
    sys.exit(255)
if not os.path.isdir(home) or os.path.exists(os.path.join(hosts, host, "down")):
    cut("ssh: Could not resolve hostname " + str(host))
for name in os.listdir(os.path.join(hosts, host)):
    if name.startswith("fail-") and name[5:] in command:
        os.remove(os.path.join(hosts, host, name))
        cut("ssh: connect to host " + host + " failed")
env = {{k: v for k, v in os.environ.items() if not k.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_", "FORGE_", "PYTEST_"))
       and k not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}}
env.update(HOME=home, XDG_CONFIG_HOME=home + "/.config", XDG_DATA_HOME=home + "/.local/share",
           CODEX_HOME=home + "/.codex", PATH=home + "/.local/bin" + os.pathsep + env["PATH"])
child = subprocess.Popen(["sh", "-c", command], cwd=home, env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
def feed():
    try:
        while data := os.read(0, 65536):
            child.stdin.write(data)
            child.stdin.flush()
    except OSError:
        pass
    finally:
        try:
            child.stdin.close()
        except OSError:
            pass
def copy(src, fd):
    while data := src.read1(65536):
        os.write(fd, data)
threads = [threading.Thread(target=feed, daemon=True),
           threading.Thread(target=copy, args=(child.stdout, 1)),
           threading.Thread(target=copy, args=(child.stderr, 2))]
for thread in threads:
    thread.start()
code = child.wait()
for thread in threads[1:]:
    thread.join()
sys.exit(code)
'''


class Host:
    def __init__(self, repo, name: str, kit: Path):
        self.name, self.hosts = name, repo.path.parent / "hosts"
        self.folder = self.hosts / name
        self.home = self.folder / "home"
        self.kit = kit
        (self.home / ".local/bin").mkdir(parents=True)
        self.program("codex", 'if [ "$1 $2" = "login status" ]; then [ -f "$HOME/.codex/auth.json" ]; exit $?; fi; exit 0')
        self.program("uv", 'echo "$*" >> "$HOME/uv.log"\n'
                           '[ "$1" = venv ] && { for last; do :; done; mkdir -p "$(dirname "$last")"; '
                           f'cp -a "{kit}" "$last"; }}\nexit 0')
        self.forge()
        self.cores(4)

    def program(self, name: str, body: str) -> None:
        _install(self.home / ".local/bin", name, "#!/bin/sh\n" + body + "\n")

    def cores(self, count: int) -> None:
        self.program("getconf", f'[ "$1" = _NPROCESSORS_ONLN ] && {{ echo {count}; exit 0; }}; '
                                'exec /usr/bin/getconf "$@"')

    def forge(self, version: str | None = None, load: float = 0.0, cores: int = 4) -> None:
        """The test's own forge, with a load and processor count, or a forge of another version."""
        target = self.home / ".local/bin/forge"
        if version:
            self.program("forge", f'echo "forge {version}"')
            return
        text = FORGE_SHIM.format(python=sys.executable, src=str(ROOT / "src")).replace(
            "(0.0, 0.0, 0.0)", repr((load,) * 3)).replace(
            "from forge.cli import main", f"import os\nos.cpu_count = os.process_cpu_count = lambda: {cores}\n"
            "from forge.cli import main")
        _install(target.parent, "forge", text)

    def sign_in(self) -> None:
        (self.home / ".codex").mkdir(exist_ok=True)
        (self.home / ".codex/auth.json").write_text("{}", encoding="utf-8")

    def trust(self, path: str) -> None:
        (self.home / ".codex").mkdir(exist_ok=True)
        with (self.home / ".codex/config.toml").open("a", encoding="utf-8") as out:
            out.write(f'[projects.{json.dumps(path)}]\ntrust_level = "trusted"\n')

    def down(self, on: bool = True) -> None:
        (self.folder / "down").touch() if on else (self.folder / "down").unlink()

    def no_git(self, on: bool = True) -> None:
        if on:
            self.program("git", "exit 127")
        else:
            (self.home / ".local/bin/git").unlink()

    def fail(self, word: str) -> None:
        (self.folder / f"fail-{word}").touch()

    def run(self, script: str) -> subprocess.CompletedProcess[str]:
        """Run a shell script on the machine, as the stand-in ssh does."""
        return subprocess.run(["ssh", self.name, script], capture_output=True, text=True, timeout=60)

    def git(self, *args: str) -> str:
        done = self.run("git " + " ".join(f"'{a}'" for a in args))
        assert done.returncode == 0, done.stderr
        return done.stdout.strip()

    def calls(self) -> list[str]:
        log = self.hosts / "ssh-calls.jsonl"
        return [json.loads(line)["command"] for line in log.read_text("utf-8").splitlines()] if log.exists() else []


def machine(repo, name: str = "devbox", kit: Path | None = None) -> Host:
    """Put a stand-in ssh first on PATH and make the machine NAME."""
    _install(repo.bin, "ssh", SSH.format(python=sys.executable, hosts=str(repo.path.parent / "hosts")))
    data = Path(kit or os.environ["XDG_DATA_HOME"])
    env = data / "forge" / "codex-sdk"
    return Host(repo, name, next(p for p in env.glob("openai-codex-*") if p.is_dir()))
