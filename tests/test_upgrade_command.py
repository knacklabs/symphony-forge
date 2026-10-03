STORY = "FORGE-UPGRADECMD-1"
"""One command upgrades Forge in a repo: forge upgrade installs the release, has that release sync
Forge's files in a fix and close it.

uv, gh and Autoreview are faked at their edges. The fake uv logs each call; its `tool install` puts
a launcher on PATH, and its `tool run` runs a copy of this checkout's code that reads as the
release, whose skill carries a marker. The sync-failure case removes a settings key only from
its fake release, so the real settings check supplies the refusal.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import conftest
from test_close import CLEAN, GREEN, blocked, env, finding  # noqa: F401

RELEASE, NAME = "v9.9.9", "upgrade-forge-to-v9-9-9"
URL = "git+https://github.com/knacklabs/symphony-forge@{}"
MARK = "release marker"

UV = """#!{python}
import json, os, pathlib, re, shutil, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
with open(here / "uv-calls.jsonl", "a", encoding="utf-8") as calls:
    calls.write(json.dumps({{"args": args, "cwd": os.getcwd()}}) + "\\n")

def launcher(release, via):
    src = here.parent / "releases" / release / "src"
    if not src.exists():
        # Laid out like this checkout, whose skill folders an editable install reads.
        shutil.copytree(pathlib.Path({root!r}, "src", "forge"), src / "forge",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for host in (".claude", ".codex"):
            shutil.copytree(pathlib.Path({root!r}, host, "skills"), src.parent / host / "skills")
        for rel, old, new in (("__init__.py", re.compile(r'__version__ = ".*"'), f'__version__ = "{{release[1:]}}"'),
                              ("templates/skill.md", re.compile(r"\\Z"), f"\\n<!-- {mark} {{release}} -->\\n")):
            path = src / "forge" / rel
            path.write_text(old.sub(new, path.read_text("utf-8"), count=1), "utf-8")
        if (here / "uv-reject-stage").exists():
            path = src / "forge" / "repo.py"
            path.write_text(path.read_text("utf-8").replace('"stage": str, ', ""), "utf-8")
    return (f"#!{{sys.executable}}\\nimport json, os, sys\\n"
            f"with open({{str(here.parent / 'forge-calls.jsonl')!r}}, 'a') as log:\\n"
            f"    log.write(json.dumps({{{{'via': {{via!r}}, 'args': sys.argv[1:], 'cwd': os.getcwd()}}}}) + '\\\\n')\\n"
            f"sys.path.insert(0, {{str(src)!r}})\\nfrom forge.cli import main\\nsys.exit(main())\\n")

def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    path.chmod(0o755)
    if os.name == "nt":
        path.with_name(path.name + ".cmd").write_text(f'@"{{sys.executable}}" "%~dp0{{path.name}}" %*\\n', "utf-8")
    return path

if args[:2] == ["tool", "install"]:
    if (here / "uv-install-fails").exists():
        sys.exit("error: Failed to fetch the release: network is unreachable")
    put(here.parent / "uvbin" / "forge", launcher(args[-1].rsplit("@", 1)[1], "installed"))
    sys.exit(0)
release = args[3].rsplit("@", 1)[1]
ran = put(here.parent / "releases" / release / "forge", launcher(release, "run"))
sys.exit(subprocess.run([sys.executable, str(ran), *args[5:]]).returncode)
"""


class Upgrade:
    """A Forge repo its pinned Forge synced, with the fake uv and its tool folder on PATH."""

    def __init__(self, env, tmp: Path):
        self.env, self.repo, self.tmp = env, env.repo, tmp
        self.folder = tmp / f"{self.repo.path.name}-fix-{NAME}"

    def run(self, *args: str):
        return self.repo.forge("upgrade", *args)

    def on_main(self, rel: str, text: str | None, message: str = "Change on main") -> None:
        """A change landed on the default branch, the way a merged pull request lands it."""
        path = self.repo.path / rel
        if text is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        self.repo.git("add", "-A", "--", rel)
        self.repo.git("-c", f"core.hooksPath={self.tmp / 'no-hooks'}", "commit", "-q",
                      "--allow-empty", "-m", message)
        self.repo.git("-c", f"core.hooksPath={self.tmp / 'no-hooks'}", "push", "-q", "origin", "main")

    def toml(self) -> str:
        return (self.repo.path / "forge.toml").read_text("utf-8")

    def uv(self) -> list[dict]:
        log = self.repo.bin / "uv-calls.jsonl"
        return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []

    def launched(self) -> list[dict]:
        log = self.tmp / "forge-calls.jsonl"
        return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []

    def show(self, rel: str, ref: str = f"fix/{NAME}") -> str:
        return self.repo.git("show", f"{ref}:{rel}")

    def upgrade_commit(self) -> list[str]:
        """The files the "Upgrade Forge to" commit changed, with their status letter."""
        sha = self.repo.git("log", "--format=%H", "--grep", f"^Upgrade Forge to {RELEASE}$",
                            f"fix/{NAME}")
        assert len(sha.split()) == 1, sha
        return self.repo.git("show", "--name-status", "--format=", sha).splitlines()

    def snapshot(self) -> tuple:
        """What a refusal must leave alone: branches, worktrees, uv calls and pull requests."""
        return (self.repo.git("for-each-ref", "--format=%(refname) %(objectname)"),
                self.repo.git("worktree", "list", "--porcelain"), self.uv(),
                self.env.gh_calls("pr", "create"))


@pytest.fixture
def unsynced_up(env, tmp_path, monkeypatch) -> Upgrade:
    conftest._install(env.repo.bin, "uv", UV.format(python=sys.executable, mark=MARK,
                                                    root=str(conftest.ROOT)))
    monkeypatch.setenv("PATH", f"{tmp_path / 'uvbin'}{os.pathsep}{os.environ['PATH']}")
    (tmp_path / "no-hooks").mkdir()
    return Upgrade(env, tmp_path)


@pytest.fixture
def up(unsynced_up) -> Upgrade:
    made = unsynced_up
    # The pinned Forge synced this repo once, as every client on Forge is.
    made.repo.git("switch", "-q", "-c", "setup")
    synced = made.repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    made.repo.git("add", "-A")
    made.repo.git("-c", f"core.hooksPath={made.tmp / 'no-hooks'}", "commit", "-q", "-m", "Sync")
    made.repo.git("switch", "-q", "main")
    made.repo.git("merge", "-q", "--ff-only", "setup")
    made.repo.git("branch", "-q", "-D", "setup")
    made.repo.git("-c", f"core.hooksPath={made.tmp / 'no-hooks'}", "push", "-q", "origin", "main")
    return made


def ours(up: Upgrade, *, installed: bool = True, committed: bool = True, started: bool = True,
         release: str = RELEASE, name: str = NAME) -> list[str]:
    """The upgrade's own lines, one per step, in order."""
    folder = up.tmp / f"{up.repo.path.name}-fix-{name}"
    return [f"Started fix {name} in {folder}." if started else f"Continuing fix {name} in {folder}.",
            f'Set version = "{release}" in the fix\'s forge.toml.',
            f"Installed Forge {release}." if installed
            else f"Forge {release} is already installed, so the install was skipped.",
            f"The forge on your PATH is Forge {release}.",
            f"Running Forge {release}'s forge sync in the fix's folder.",
            f"Committed the upgrade to Forge {release}." if committed else "Nothing new to commit.",
            f"Running Forge {release}'s forge close {name}."]


def assert_ready(up: Upgrade, done, expected: list[str], release: str = RELEASE,
                 name: str = NAME) -> None:
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert [line for line in lines if line in expected] == expected
    assert lines[-1] == (f"Ready: {name} has a clean review and green checks. "
                         "A human merges its pull request.")
    # Only the fix's own branch: a rerun never starts a second one.
    assert up.repo.git("for-each-ref", "--format=%(refname:short)", "refs/heads/fix/") == f"fix/{name}"


def install(release: str = RELEASE) -> list[str]:
    return ["tool", "install", "--force", "--reinstall", "--no-cache", "--python", "3.11",
            URL.format(release)]


def release_run(release: str, *args: str) -> list[str]:
    return ["tool", "run", "--from", URL.format(release), "forge", *args]


# --- Done-when 1: one command, from the install to the close ---------------------------------

def _named(up):
    original = up.toml()
    (up.repo.path / "notes.txt").write_text("an untracked file doesn't count\n", "utf-8")

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up))
    assert [call["args"] for call in up.uv()] == [
        install(), release_run(RELEASE, "sync"), release_run(RELEASE, "close", NAME)]
    assert {call["cwd"] for call in up.uv()[1:]} == {str(up.folder)}
    assert up.show("forge.toml") == original.replace(f'"{up.version}"', f'"{RELEASE}"').strip()
    state = json.loads(up.show(f".factory/fixes/{NAME}.json"))
    assert (state["why"], state["done_when"]) == (f"Upgrade Forge to {RELEASE}.",
                                                  f"This repo pins and runs Forge {RELEASE}.")
    assert up.toml() == original  # the default branch keeps its pin until the merge


def _pinned_older_than_the_installed_forge(up):
    # The command skips the pin check: under it, the older pinned release would run instead, and
    # that release has no upgrade command.
    up.on_main("forge.toml", up.toml().replace(f'"{up.version}"', '"v1.0.0"'), "Pin v1.0.0")

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up))
    assert [call["args"] for call in up.uv()][0] == install()


def _pinned_to_its_own_prerelease(up):
    # The release comes after its prerelease, so a repo on v9.9.9-rc.1 upgrades to v9.9.9.
    up.on_main("forge.toml", up.toml().replace(f'"{up.version}"', '"v9.9.9-rc.1"'), "Pin the rc")

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up))
    assert 'version = "v9.9.9"' in up.show("forge.toml")


def _newest_then_a_newer_one(up):
    up.env.gh.respond("release", "view", stdout=json.dumps({"tagName": RELEASE}))

    done = up.run()

    assert_ready(up, done, ours(up))
    assert ["release", "view", "--repo", "knacklabs/symphony-forge", "--json", "tagName"] in \
        up.env.gh.calls()

    # A newer release came out while the first upgrade waits for its merge.
    up.env.gh.respond("release", "view", stdout=json.dumps({"tagName": "v9.10.0"}))
    before = up.snapshot()

    done = up.run()

    assert done.returncode == 1
    assert done.stderr == (
        f"The upgrade to Forge {RELEASE} is still open in fix {NAME}.\n"
        f"Next: forge upgrade {RELEASE} to finish it, or remove it: git worktree remove --force "
        f"{up.folder} && git branch -D fix/{NAME}\n")
    assert up.snapshot() == before


def _failed_install_then_rerun(up):
    (up.repo.bin / "uv-install-fails").touch()

    done = up.run(RELEASE)

    assert done.returncode == 1
    command = " ".join(["uv", *install()])
    assert done.stderr == (
        f"Installing Forge {RELEASE} failed: error: Failed to fetch the release: network is "
        f"unreachable\nNext: run {command} in your own terminal, then forge upgrade {RELEASE}\n")
    assert [call["args"] for call in up.uv()] == [install()]

    (up.repo.bin / "uv-install-fails").unlink()
    done = up.run(RELEASE)

    assert_ready(up, done, ours(up, started=False))
    assert len(up.env.gh_calls("pr", "create")) == 1


def _staged_rename_then_rerun(up):
    # The first run stops at the install; meanwhile the fix's folder holds a staged rename.
    (up.repo.bin / "uv-install-fails").touch()
    assert up.run(RELEASE).returncode == 1
    (up.repo.bin / "uv-install-fails").unlink()
    up.repo.git("mv", "README.md", "READ-ME.md", cwd=up.folder)

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up, started=False))
    assert up.show("READ-ME.md") == "# A test repo"
    assert up.repo.git("ls-tree", "--name-only", f"fix/{NAME}", "README.md") == ""


def _interrupted_after_the_folder(up):
    # The run stopped right after git made the fix's folder and branch, before its state.
    up.repo.git("worktree", "add", "-q", "--no-track", "-b", f"fix/{NAME}", str(up.folder),
                "origin/main")

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up, started=False))
    assert json.loads(up.show(f".factory/fixes/{NAME}.json"))["why"] == f"Upgrade Forge to {RELEASE}."


def _failed_release_sync_then_rerun(up):
    # The new release no longer knows a setting this repo still has.
    (up.repo.bin / "uv-reject-stage").touch()
    up.on_main("forge.toml", up.toml() + 'stage = "live"\n')
    original = up.toml()

    done = up.run(RELEASE)

    assert done.returncode == 1
    assert "forge.toml is not usable: 'stage' is not a forge.toml key." in done.stderr
    assert [call["args"] for call in up.uv()] == [install(), release_run(RELEASE, "sync")]
    assert up.repo.git("rev-list", "--count", f"origin/main..fix/{NAME}") == "1"  # only its start
    assert (up.folder / "forge.toml").read_text("utf-8") == original.replace(
        f'"{up.version}"', f'"{RELEASE}"')

    # With the setting gone from the default branch and from the fix, a rerun goes on.
    up.on_main("forge.toml", original.replace('stage = "live"\n', ""))
    fixed = (up.folder / "forge.toml").read_bytes().replace(b'stage = "live"\n', b"")
    (up.folder / "forge.toml").write_bytes(fixed)  # bytes: Windows would rewrite its line endings

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up, started=False, installed=False))
    assert "stage" not in up.show("forge.toml")


def _rerun_after_the_commit(up):
    assert up.run(RELEASE).returncode == 0
    first = len(up.uv())

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up, started=False, installed=False, committed=False))
    assert [call["args"] for call in up.uv()[first:]] == [
        release_run(RELEASE, "sync"), release_run(RELEASE, "close", NAME)]


def _close_refuses(up):
    up.env.reviews(blocked(finding("P1", "The launcher pins the wrong release", ".forge/hooks.sh")))

    done = up.run(RELEASE)

    assert done.returncode == 1  # close's own refusal code
    assert [line for line in done.stdout.splitlines() if line in ours(up)] == ours(up)
    assert "1. P1 The launcher pins the wrong release (.forge/hooks.sh:1)" in done.stdout
    assert done.stderr.endswith(
        "The review left serious findings open: finding 1 (The launcher pins the wrong release).\n"
        f'Next: forge work {NAME}, or forge close {NAME} --dismiss <n> --because "<file:line> '
        '<reason>"\n')
    assert up.uv()[-1]["args"] == release_run(RELEASE, "close", NAME)


def _sync_deletes_a_file(up):
    # A Forge-only CLAUDE.md, which this release's sync replaces with AGENTS.md alone.
    up.on_main("CLAUDE.md", "@AGENTS.md\n", "Bring back CLAUDE.md")

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up))
    assert "D\tCLAUDE.md" in up.upgrade_commit()


def _hooks_inside_the_checkout(up):
    up.repo.git("config", "core.hooksPath", ".husky/_")

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up))
    assert (up.folder / ".husky" / "_" / "pre-commit").is_file()  # sync wrote its shims there
    assert not [line for line in up.upgrade_commit() if ".husky" in line]
    assert "M\tforge.toml" in up.upgrade_commit()


def _stale_forge_shadows_the_install(up, monkeypatch):
    stale = up.tmp / "stale"
    stale.mkdir()
    conftest._install(stale, "forge", f"#!{sys.executable}\nprint('forge v1.0.0')\n")
    monkeypatch.setenv("PATH", f"{stale}{os.pathsep}{os.environ['PATH']}")

    done = up.run(RELEASE)

    assert done.returncode == 1
    assert done.stderr == (
        f"After the install, your PATH finds Forge v1.0.0 at {shutil.which('forge', path=str(stale))} instead of Forge "
        f"{RELEASE}.\nNext: remove that forge or put uv's tool folder ahead of it on PATH, then "
        f"forge upgrade {RELEASE}\n")
    assert [call["args"] for call in up.uv()] == [install()]


# --- Done-when 1: each refusal stops before anything is created ----------------------------

def _leftover(up, make):
    """A fix folder and branch an earlier run left, as `make` shapes it."""
    up.repo.git("worktree", "add", "-q", "--no-track", "-b", f"fix/{NAME}", str(up.folder), "origin/main")
    make(up.folder)


def _taken_state(folder: Path) -> None:
    state = folder / ".factory" / "fixes" / f"{NAME}.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"kind": "fix", "why": "Something else entirely."}), "utf-8")


REFUSED = {
    "forge's own repo": (
        lambda up: up.on_main("forge.toml", 'repo = "forge-source"\n' + up.toml()), [RELEASE],
        "This is Forge's own repo, which moves its version by releasing a new Forge.\n"
        "Next: forge next\n"),
    "another branch": (
        lambda up: up.repo.git("switch", "-q", "-c", "elsewhere"), [RELEASE],
        "forge upgrade runs on main, and this checkout is on elsewhere.\n"
        f"Next: git switch main, then forge upgrade {RELEASE}\n"),
    "uncommitted changes": (
        lambda up: up.repo.write("README.md", "# Edited\n"), [],
        "This checkout has changes you haven't committed: README.md.\n"
        "Next: commit or undo them, then forge upgrade\n"),
    "a staged change undone in the folder": (
        lambda up: (up.repo.write("README.md", "# Edited\n"), up.repo.git("add", "README.md"),
                    up.repo.write("README.md", "# A test repo\n")), [RELEASE],
        "This checkout has changes you haven't committed: README.md.\n"
        f"Next: commit or undo them, then forge upgrade {RELEASE}\n"),
    "no v": (lambda up: None, ["1.3.0"],
             "'1.3.0' is not a Forge release; a release is v and three numbers, such as v1.3.0.\n"
             "Next: forge upgrade <release>\n"),
    "two numbers": (lambda up: None, ["v1.3"],
                    "'v1.3' is not a Forge release; a release is v and three numbers, such as "
                    "v1.3.0.\nNext: forge upgrade <release>\n"),
    "a prerelease": (lambda up: None, ["v9.9.9-rc1"],
                     "'v9.9.9-rc1' is not a Forge release; a release is v and three numbers, "
                     "such as v1.3.0.\nNext: forge upgrade <release>\n"),
    "the same release": (lambda up: None, ["<pinned>"],
                         "main already pins Forge <pinned>, so <pinned> would not be an upgrade.\n"
                         "Next: forge upgrade <a release newer than <pinned>>\n"),
    "a downgrade": (lambda up: None, ["v1.0.0"],
                    "main already pins Forge <pinned>, so v1.0.0 would not be an upgrade.\n"
                    "Next: forge upgrade <a release newer than <pinned>>\n"),
    "no newest": (
        lambda up: up.env.gh.respond("release", "view", stderr="HTTP 404: Not Found.\n", exit=1), [],
        "Forge could not find its newest release: HTTP 404: Not Found.\n"
        "Next: forge upgrade <release>, naming the release\n"),
    "another upgrade open": (
        lambda up: up.repo.git("worktree", "add", "-q", "-b", "fix/upgrade-forge-to-v9-8-0",
                               str(up.tmp / "other-upgrade"), "origin/main"), [RELEASE],
        "The upgrade to Forge v9.8.0 is still open in fix upgrade-forge-to-v9-8-0.\n"
        "Next: forge upgrade v9.8.0 to finish it, or remove it: git worktree remove --force "
        "<other> && git branch -D fix/upgrade-forge-to-v9-8-0\n"),
    "no version edit": (
        lambda up: up.on_main("forge.toml", up.toml() + "test = '''\nversion = \"fixture\"\n'''\n"),
        [RELEASE],
        f'forge.toml is not usable: Forge could not set version = "{RELEASE}" in it, so it left '
        "it alone.\nNext: forge doctor\n"),
    "a leftover folder with work": (
        lambda up: _leftover(up, lambda folder: (folder / "draft.txt").write_bytes(b"keep me\r\n")),
        [RELEASE],
        f"Fix {NAME} was interrupted as it started, and its folder <folder> holds work, so Forge "
        "left it alone.\nNext: check that folder, then git worktree remove --force <folder> && "
        f"git branch -D fix/{NAME}, then forge upgrade {RELEASE}\n"),
    "a fix of that name for other work": (
        lambda up: _leftover(up, _taken_state), [RELEASE],
        f"Fix {NAME} already exists for other work, so Forge left it alone.\n"
        f"Next: finish or remove that fix, then forge upgrade {RELEASE}\n"),
    "its branch without its folder": (
        lambda up: up.repo.git("branch", f"fix/{NAME}", "origin/main"), [RELEASE],
        f"Fix {NAME} already exists as a branch without its folder, so Forge left it alone.\n"
        f"Next: finish or remove that fix, then forge upgrade {RELEASE}\n"),
}


def _refused(up, case):
    setup, args, expected = REFUSED[case]
    setup(up)
    draft = up.folder / "draft.txt"
    before = up.snapshot()

    done = up.run(*[arg.replace("<pinned>", up.version) for arg in args])

    assert done.returncode == 1
    assert done.stderr == (expected.replace("<pinned>", up.version).replace("<other>", str(up.tmp / "other-upgrade"))
                           .replace("<folder>", str(up.folder)))
    assert done.stdout == ""
    assert up.snapshot() == before
    if case == "a leftover folder with work":
        assert draft.read_bytes() == b"keep me\r\n"  # fails too if the file were gone


def _repo_adopted_on_the_previous_release(up):
    # A landed v1.2.2 adoption, including that release's synced files, rather than a current
    # sync with an older version string. The fixture README records its real-command origin.
    shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path,
                    dirs_exist_ok=True)
    up.repo.git("switch", "-q", "-c", "adoption")
    up.repo.git("add", "-A")
    up.repo.git("commit", "-q", "-m", "Adopt Forge v1.2.2")
    up.repo.git("switch", "-q", "main")
    up.repo.git("merge", "-q", "--ff-only", "adoption")
    up.repo.git("branch", "-q", "-D", "adoption")
    up.repo.git("push", "-q", "origin", "main")
    original = up.toml()
    assert tomllib.loads(original)["version"] == "v1.2.2"
    for host in (".claude", ".codex"):
        assert "forge upgrade" not in (up.repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up))
    assert [call["args"] for call in up.uv()] == [
        install(), release_run(RELEASE, "sync"), release_run(RELEASE, "close", NAME)]
    assert up.show("forge.toml") == original.replace('"v1.2.2"', f'"{RELEASE}"').strip()
    assert up.toml() == original
    for host in (".claude", ".codex"):
        skill = up.show(f"{host}/skills/forge/SKILL.md")
        assert f"<!-- {MARK} {RELEASE} -->" in skill
        assert "`forge upgrade <release>`" in skill.split("## Upgrade Forge\n", 1)[1]
    assert "forge hook deny" in up.show(".claude/settings.json")
    assert "forge hook deny" in up.show(".codex/hooks.json")
    config = tomllib.loads(up.show(".codex/config.toml"))
    assert config["features"]["hooks"] is True
    assert config["mcp_servers"]["docs"]["command"] == "docs-server"
    assert RELEASE in up.show(".forge/hooks.sh")
    assert "Keep the public API stable." in up.show("AGENTS.md")
    assert len(up.env.gh_calls("pr", "create")) == 1


SCENARIOS = [_named, _pinned_older_than_the_installed_forge, _pinned_to_its_own_prerelease, _newest_then_a_newer_one,
             _failed_install_then_rerun, _staged_rename_then_rerun, _interrupted_after_the_folder,
             _failed_release_sync_then_rerun, _rerun_after_the_commit, _close_refuses,
             _sync_deletes_a_file, _hooks_inside_the_checkout, _stale_forge_shadows_the_install,
             _repo_adopted_on_the_previous_release]


@pytest.mark.parametrize("case", [*SCENARIOS, *REFUSED], ids=lambda case: getattr(case, "__name__", case))
def test_1_one_command_upgrades_forge_and_opens_its_pull_request(unsynced_up, case, monkeypatch,
                                                              request):
    up = unsynced_up if case is _repo_adopted_on_the_previous_release else request.getfixturevalue("up")
    up.version = re.search(r'^version = "(.+)"$', up.toml(), re.M)[1]
    if isinstance(case, str):  # each refusal stops before anything is created
        _refused(up, case)
    else:
        case(*(up, monkeypatch)[:case.__code__.co_argcount])


# --- Done-when 2: the release writes both hosts' files, whoever runs the command -------------

@pytest.mark.parametrize("workers", ["claude", "codex"])
@pytest.mark.parametrize("host", ["CLAUDECODE", "CODEX_THREAD_ID", None])
def test_2_the_release_writes_both_hosts_files_whoever_runs_it(up, host, workers, monkeypatch):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    if host:
        monkeypatch.setenv(host, "1")
    up.on_main("forge.toml", re.sub(r'^workers = ".*"$', f'workers = "{workers}"', up.toml(),
                                    flags=re.M))
    config = (up.repo.path / ".codex" / "config.toml").read_text("utf-8")
    up.on_main(".codex/config.toml", config + '\n[mcp_servers.docs]\ncommand = "docs-server"\n')

    done = up.run(RELEASE)

    assert_ready(up, done, ours(up))
    for host_dir in (".claude", ".codex"):
        skill = up.show(f"{host_dir}/skills/forge/SKILL.md")
        assert f"<!-- {MARK} {RELEASE} -->" in skill
        # Done-when 4: the skill sync writes tells the agent to run the one command.
        table, section = skill.split("## Upgrade Forge\n", 1)
        assert "`forge upgrade <release>`" in section.split("\n## ", 1)[0]
        assert "`forge upgrade <release>`" in table  # the command table's row
        assert 'forge fix start "Upgrade Forge' not in skill
    assert "forge hook deny" in up.show(".claude/settings.json")
    assert "forge hook deny" in up.show(".codex/hooks.json")
    settings = tomllib.loads(up.show(".codex/config.toml"))
    assert settings["features"]["hooks"] is True
    assert settings["mcp_servers"]["docs"]["command"] == "docs-server"
    assert 'v9.9.9' in up.show(".forge/hooks.sh")
    # The release's own sync wrote them: run again on the fix's head, it changes nothing.
    check = up.tmp / "check"
    up.repo.git("worktree", "add", "-q", "--detach", str(check), f"fix/{NAME}")
    again = subprocess.run([sys.executable, str(up.tmp / "releases" / RELEASE / "forge"),
                                     "sync"], cwd=check, capture_output=True, text=True)
    assert again.returncode == 0, again.stderr
    assert not [line for line in again.stdout.splitlines() if line.startswith("Wrote")]
    up.repo.git("worktree", "remove", "--force", str(check))
    assert {"args": release_run(RELEASE, "sync"), "cwd": str(up.folder)} in up.uv()
    # The installed Forge never ran sync in the fix's folder: only close's throwaway check did.
    assert not [call for call in up.launched() if call["via"] == "installed"
                and call["args"][:1] == ["sync"] and call["cwd"] == str(up.folder)]
