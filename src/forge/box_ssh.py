"""A Linux machine the team owns, reached with ssh: its setup and its turn-off."""
import hashlib
import posixpath
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any, NoReturn

from forge import box, codex, githooks, machine, repo, sync, task

FOLDER = "forge-host"
# A round's own remote command writes runs/<item>/<entry>.done after its driver exits; a round
# entry (runs/<item>/<entry>.py beside its <entry>/ worktree) with no such file counts as running.
DONE = ".done"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30",
       "-o", "ServerAliveCountMax=4"]
NAME = re.compile(r"[A-Za-z0-9_.@:%\[\]-]+")
PATH = 'PATH="$HOME/.local/bin:$PATH"; '
KIT = f'"${{XDG_DATA_HOME:-$HOME/.local/share}}/forge/codex-sdk/openai-codex-{codex.SDK_PIN}"'
CONFIG = '"${CODEX_HOME:-$HOME/.codex}/config.toml"'


def ssh(host: str, script: str, *, input: str | None = None):
    """Run a script on the machine; ssh's own failure (exit 255) is a ProviderError."""
    done = repo.run(*SSH, host, PATH + script, input=input)
    if done.returncode == 255:
        raise box.ProviderError("ssh", _last(done.stderr))
    return done


def _last(text: str) -> str:
    return (text.strip().splitlines() or [""])[-1]


def _folder(top: Path) -> str:
    main = machine.main_checkout(top)
    return f"{FOLDER}/{main.name}-{hashlib.sha256(main.as_posix().encode()).hexdigest()[:6]}"


def _refuse(problem: str, next_step: str) -> NoReturn:
    raise repo.Refused(problem, next_step)


def setup(top: Path, args: Any) -> int:
    cfg = repo.config(top)
    saved = box.record(top) or {}
    host = args.host or saved.get("host")
    if not host:
        _refuse("Name your machine: forge lanes --box setup --host <the name you give ssh>.",
                "forge lanes --box setup --host <name>")
    if not NAME.fullmatch(host) or host.startswith("-"):
        _refuse(f'--host "{host}" is not a name ssh takes; use the name from your ssh settings.',
                "forge lanes --box setup --host <name>")
    if saved and host != saved["host"]:
        _refuse(f"This clone is set up on {saved['host']}; turn that off first.",
                "forge lanes --box off, then forge lanes --box setup")
    again = "forge lanes --box setup" + ("" if saved else f" --host {host}")
    folder, pin = _folder(top), cfg["version"]
    home = f'"$HOME"/{shlex.quote(folder)}'

    def remote(script: str, doing: str, input: str | None = None):
        try:
            return ssh(host, script, input=input)
        except box.ProviderError as error:
            _refuse(f"{doing} on {host} failed: {error.message}.", again)

    try:
        facts = ssh(host, f'''echo "GIT $(git --version 2>/dev/null)"; echo "FORGE $(forge --version 2>/dev/null)"
codex login status >/dev/null 2>&1; echo "CODEX $?"
echo "PROBE $({KIT}/bin/python -c {shlex.quote(codex.PROBE)} 2>&1 | tail -n 1)"
echo "CORES $(getconf _NPROCESSORS_ONLN)"
echo "HOME $HOME"; test -d {home}/clone/.git && echo "CLONE yes"
echo "CONFIG $(echo {CONFIG})"; cat {CONFIG} 2>/dev/null; true''')
    except box.ProviderError as error:
        _refuse(f"Forge cannot reach {host} with ssh: {error.message}. ssh {host} true must work from this laptop "
                "with no password prompt.", again)
    head, _, config = facts.stdout.partition("CONFIG ")
    config_path, _, config = config.partition("\n")
    got = {line.split(" ", 1)[0]: line.split(" ", 1)[-1].strip() for line in head.splitlines() if line.strip()}
    if not got.get("GIT", "").startswith("git"):
        _refuse(f"{host} has no git.", f"install git on {host}, then {again}")
    version = (got.get("FORGE", "").split() or [""])[-1]
    if version.removeprefix("v") != pin.removeprefix("v"):
        _refuse(f"{host} has {'Forge ' + version if version else 'no Forge'}, and this repo pins Forge {pin}.",
                f"on {host}: {sync.install_line(pin)}, then {again}")
    if got.get("CODEX") != "0":
        _refuse(f"Codex is not signed in on {host}.", f"on {host}: codex login --device-auth (install Codex first "
                f"with npm install -g @openai/codex when it is missing), then {again}")
    if not codex.GOOD.fullmatch(got.get("PROBE", "")):
        print(f"Installing the Codex kit {codex.SDK_PIN} on {host} with uv (about 300 MB).", flush=True)
        done = remote(f'''env={KIT}; rm -f "$env/{codex.READY}"; rm -rf "$env"; mkdir -p "$(dirname "$env")"
(uv venv --python 3.11 "$env" && uv pip install --python "$env/bin/python" openai-codex=={codex.SDK_PIN} \\
&& echo {codex.SDK_PIN} > "$env/{codex.READY}") 2>&1''', "The Codex kit install")
        if done.returncode:
            _refuse(f"The Codex kit install on {host} failed: {_last(done.stdout + done.stderr)}.", again)
    identity = [repo.run("git", "config", key, cwd=top).stdout.strip() for key in ("user.name", "user.email")]
    if not all(identity):
        _refuse("This checkout has no git user name or email, so a worker could not commit.",
                'git config --global user.name "<name>" and user.email "<email>", then forge lanes --box setup')
    clone = f"{got['HOME']}/{folder}/clone"
    hook = (githooks.SHIM.replace("<version>", pin).replace("<hook>", "pre-commit").replace("<what>", "commit")
            .replace("<install>", sync.install_line(pin)).replace("<run-prior>", '"$0.pre-forge" "$@"'))
    default = shlex.quote(repo.default_branch(top))
    make = "" if got.get("CLONE") else (
        'mkdir -p "$F/runs" && git init -q "$C" && cat > "$C/.git/hooks/pre-commit" '
        '&& chmod 755 "$C/.git/hooks/pre-commit" '
        f'&& git -C "$C" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/{default} && ')
    done = remote(f'F={home}; C="$F/clone"; {make}'
               f'git -C "$C" config user.name {shlex.quote(identity[0])} '
               f'&& git -C "$C" config user.email {shlex.quote(identity[1])} '
               # Git reads hooks from core.hooksPath, so this clone names its own hooks folder.
               '&& git -C "$C" config core.hooksPath "$C/.git/hooks"', "Making Forge's folder", hook if make else None)
    if done.returncode:
        _refuse(f"Forge could not make its folder on {host}: {_last(done.stderr)}.", again)
    try:
        trusted = tomllib.loads(config).get("projects", {}).get(clone, {}).get("trust_level") == "trusted"
    except tomllib.TOMLDecodeError:
        trusted = False
    if not trusted:
        _refuse(f"Codex on {host} does not trust {clone}, so it would skip Forge's checks there.",
                f'on {host}, add [projects."{clone}"] with trust_level = "trusted" to {config_path}, then {again}')
    box.save(top, {"provider": "ssh", "host": host, "clone": clone})
    print(f"{host} is set up for this repo ({got.get('CORES', '?')} processors). Codex build rounds start there "
          "while it has room, and on this laptop when it has none.")
    return 0


def _holds(top: Path, saved: dict[str, Any]) -> dict[str, Any]:
    """What Forge's folder on the machine holds: running rounds, loose files, stashes, commits not back."""
    tips = repo.git("for-each-ref", "--format=%(objectname)", "refs/heads", "refs/remotes", cwd=top)
    out = ssh(saved["host"], f'''F={shlex.quote(posixpath.dirname(saved["clone"]))}; C="$F/clone"
[ -d "$F" ] || exit 0
cd "$F" || {{ echo "ERR cannot open $F"; exit 0; }}
known=""; while read s; do git -C "$C" cat-file -e "$s^{{commit}}" 2>/dev/null && known="$known $s"; done
git --version >/dev/null 2>&1 || echo "ERR git does not run"
# Forge's own rounds only: runs/<item>/<entry>.py beside its <entry>/ worktree (a .git file), never an
# app's script inside a worktree. A round has ended only when its <entry>.done file exists.
pys=$(find runs -mindepth 2 -maxdepth 3 -name '*.py' 2>&1) || echo "ERR find: $pys"
for p in $(echo "$pys" | sort); do
  [ -f "${{p%.py}}/.git" ] || continue
  if [ -f "${{p%.py}}{DONE}" ]; then r=0; else r=1; fi
  echo "RUN ${{p%.py}} $r"; done
gits=$(find runs -name .git -type f 2>&1) || echo "ERR find: $gits"
for g in $gits; do d=$(dirname "$g")
  st=$(git -C "$d" status --porcelain -uall --ignored 2>&1) || {{ echo "ERR status of $d: $st"; continue; }}
  printf '%s\\n' "$st" | sed "s|^|FILE $d |"; done
st=$(git -C "$C" stash list 2>&1) || echo "ERR stash list: $st"
[ -z "$st" ] || printf '%s\\n' "$st" | sed 's/^/STASH /'
bs=$(git -C "$C" for-each-ref --format='%(refname:short) %(objectname)' refs/heads 2>&1) || echo "ERR branches: $bs"
printf '%s\\n' "$bs" | while read b s; do [ -n "$b" ] || continue
  n=$(git -C "$C" rev-list --count "$s" --not $known 2>&1) || {{ echo "ERR commits of $b: $n"; continue; }}
  echo "BRANCH $b $n"; done
exit 0''', input=tips + "\n")
    if out.returncode or "\nERR " in "\n" + out.stdout:
        error = next((line[4:] for line in out.stdout.splitlines() if line.startswith("ERR ")), _last(out.stderr))
        raise box.ProviderError("inspect", error)
    found: dict[str, Any] = {"running": None, "files": {}, "stash": [], "branches": []}
    for line in out.stdout.splitlines():
        kind, _, rest = line.partition(" ")
        if kind == "RUN" and rest.endswith(" 1") and not found["running"]:
            found["running"] = rest[:-2]
        elif kind == "FILE":
            where, _, entry = rest.partition(" ")
            path = entry[3:].strip('"')
            if not (entry.startswith("!!") and set(path.rstrip("/").split("/")) & repo.CACHES):
                found["files"].setdefault(where, []).append(path + (" (ignored)" if entry.startswith("!!") else ""))
        elif kind == "STASH":
            found["stash"].append(rest)
        elif kind == "BRANCH" and rest.rsplit(" ", 1)[1] != "0":
            found["branches"].append(rest.rsplit(" ", 1))
    return found


def off(top: Path, saved: dict[str, Any], yes: bool) -> int:
    host, folder = saved["host"], posixpath.dirname(saved["clone"])
    try:
        found = _holds(top, saved)
    except box.ProviderError as error:
        _refuse(f"Could not {'delete' if yes and error.code == 'ssh' else 'read'} {folder} on {host}: {error.message}.", "forge lanes --box off")
    if found["running"]:
        entry = f"{folder}/{found['running']}"
        _refuse(f"A round on {host} has no {DONE} file, so it may still run: {entry}.",
                f"check on {host} that nothing of it runs, then run touch {shlex.quote(entry + DONE)} there and "
                "forge lanes --box off")
    print(f"Turning off deletes Forge's folder {folder} on {host}, with everything in it:")
    for where, files in found["files"].items():
        print(f"  {posixpath.join(folder, where)}: {', '.join(files)}")
    for line in found["stash"]:
        print(f"  stash: {line}")
    for name, count in found["branches"]:
        found_item = task.branch_item(name, top)
        hint = f"; forge work {found_item[0]} brings them back first" if found_item else ""
        print(f"  {found_item[0] if found_item else name}: {count} commits that have not come back{hint}")
    if not (found["files"] or found["stash"] or found["branches"]):
        print("Nothing in it is work that has not come back.")
    if not yes:
        print("Next: forge lanes --box off --yes, once the developer agrees")
        return 0
    try:
        done = ssh(host, f"rm -rf {shlex.quote(folder)}")
    except box.ProviderError as error:
        _refuse(f"Could not delete {folder} on {host}: {error.message}.", "forge lanes --box off")
    if done.returncode:
        _refuse(f"Could not delete {folder} on {host}: {_last(done.stderr)}.", "forge lanes --box off")
    box.save(top, None)
    print(f"Deleted Forge's folder {folder} on {host}. Codex build rounds now run on this laptop. "
          f"Codex's sign-in and its trust entry on {host} stay.")
    return 0
