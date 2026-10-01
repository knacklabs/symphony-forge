"""forge doctor --fix repairs what it safely can: the pinned Forge, the git hooks, the Codex SDK
where Codex is used, and the folders of finished work.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves. Fakes stand only
for the third parties at their edge: uv, gh and the newly installed forge.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import _install
from test_codex_setup import PIN as SDK_PIN
from test_codex_setup import UV_STUB as SDK_UV
from test_setup import _version

STORY = "FORGE-DOCTORFIX-1"
NEWER = "9.0.0"
INSTALL = f"uv tool install git+https://github.com/knacklabs/symphony-forge@v{NEWER}"
HOOKS_FIXED = "- Fixed: installed the git hooks that check each commit and push."
HOOKS_ROW = "The git hooks that check each commit and push aren't installed."

# Fake uv: logs each call. `tool install` puts a fake forge, standing in for the pinned release,
# into the folder that comes first on PATH, unless the test makes uv fail.
UV = """#!{python}
import json, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
with open(here / "uv-calls.jsonl", "a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if {fail!r}:
    sys.stderr.write("Resolving forge\\n{fail}\\n")
    sys.exit(2)
forge = pathlib.Path({pinned!r}) / "forge"
forge.write_text({forge!r}, encoding="utf-8")
forge.chmod(0o755)
if sys.platform == "win32":
    forge.with_suffix(".cmd").write_text('@"' + sys.executable + '" "%~dp0forge" %*\\n')
"""

# The pinned release's forge: says what it was run with, then fails with its own code.
PINNED_FORGE = """#!{python}
import os, sys
print("pinned forge ran with", " ".join(sys.argv[1:]), "and", os.environ.get("FORGE_PINNED_RUN"))
sys.exit(3)
"""


def _client(repo, version: str = "", workers: str = "claude") -> None:
    repo.write("forge.toml", f'version = "{version or _version(repo)}"\nworkers = "{workers}"\n'
                             'test = "true"\nchecks = ["tests"]\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set up client")


def _fake_uv(repo, tmp_path, monkeypatch, fail: str = "") -> Path:
    pinned = tmp_path / "pinned-bin"
    pinned.mkdir()
    monkeypatch.setenv("PATH", f"{pinned}{os.pathsep}{os.environ['PATH']}")
    _install(repo.bin, "uv", UV.format(python=sys.executable, fail=fail, pinned=str(pinned),
                                       forge=PINNED_FORGE.format(python=sys.executable)))
    return repo.bin / "uv-calls.jsonl"


def _uv_calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()]


def _hooks(repo) -> list[Path]:
    return [repo.path / ".git" / "hooks" / name for name in ("pre-commit", "pre-push")]


def _commit_refused(repo) -> bool:
    """Whether the git hooks stop a commit on the default branch, as Forge's hooks do."""
    return subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "Straight to main"],
                          cwd=repo.path, capture_output=True, text=True).returncode != 0


SHELL = pytest.mark.skipif(os.name == "nt",
                           reason="the stand-in Codex program is a shell script")


# --- item 1: the pinned Forge -------------------------------------------------------------------


def _a_newer_pin_is_installed_and_doctor_runs_again_with_it(repo, gh, tmp_path, monkeypatch, _):
    _client(repo, NEWER)
    log = _fake_uv(repo, tmp_path, monkeypatch)
    assert f"Fix: forge doctor --fix" in repo.forge("doctor").stdout  # without --fix, only the row
    assert _uv_calls(log) == []

    done = repo.forge("doctor", "--fix")
    assert _uv_calls(log) == [INSTALL.split()[1:]]
    # The second run's output comes through as it came, and its exit code is doctor's.
    assert done.stdout == (f"- Fixed: installed Forge v{NEWER}, the version this repo pins.\n"
                           f"pinned forge ran with doctor --fix and v{NEWER}\n"), done.stderr
    assert done.returncode == 3


def _a_second_run_still_on_the_wrong_forge_keeps_the_row(repo, gh, tmp_path, monkeypatch, _):
    _client(repo, NEWER)
    log = _fake_uv(repo, tmp_path, monkeypatch)
    monkeypatch.setenv("FORGE_PINNED_RUN", f"v{NEWER}")  # another forge came earlier on PATH
    done = repo.forge("doctor", "--fix")
    assert _uv_calls(log) == []
    assert (f"- Forge {_version(repo)} is installed, but this repo pins v{NEWER}.\n"
            f"  Fix: {INSTALL}\n") in done.stdout
    assert done.returncode == 1


def _an_older_pin_or_a_dev_build_is_left_alone(repo, gh, tmp_path, monkeypatch, pin):
    # Ruling: the dev build case pins the installed three numbers with a suffix; doctor compares
    # only the three numbers either way, so it is the same case as a dev build installed.
    version = "1.0.0" if pin == "1.0.0" else f"{_version(repo).removeprefix('v')}.dev1"
    _client(repo, version)
    log = _fake_uv(repo, tmp_path, monkeypatch)
    for args in (("doctor",), ("doctor", "--fix")):
        done = repo.forge(*args)
        assert (f"is installed, but this repo pins v{version}.\n  Fix: uv tool install "
                f"git+https://github.com/knacklabs/symphony-forge@v{version}\n") in done.stdout
    assert _uv_calls(log) == []
    assert HOOKS_FIXED in done.stdout  # the other repairs still run


def _a_failing_install_keeps_the_row(repo, gh, tmp_path, monkeypatch, _):
    _client(repo, NEWER)
    log = _fake_uv(repo, tmp_path, monkeypatch, fail="error: failed to replace forge.exe")
    done = repo.forge("doctor", "--fix")
    assert _uv_calls(log) == [INSTALL.split()[1:]]
    assert (f"this repo pins v{NEWER}. Installing it failed: error: failed to replace forge.exe\n"
            f"  Fix: {INSTALL}\n") in done.stdout
    assert HOOKS_FIXED in done.stdout and _commit_refused(repo)
    assert done.returncode == 1 and "Traceback" not in done.stderr


def _without_uv_the_row_stays(repo, gh, tmp_path, monkeypatch, _):
    _client(repo, NEWER)
    monkeypatch.setenv("PATH", os.pathsep.join(
        folder for folder in os.environ["PATH"].split(os.pathsep)
        if not shutil.which("uv", path=folder)))
    done = repo.forge("doctor", "--fix")
    assert f"this repo pins v{NEWER}.\n  Fix: {INSTALL}\n" in done.stdout
    assert "- uv is not installed or not on PATH." in done.stdout
    assert HOOKS_FIXED in done.stdout


# --- item 2: the git hooks and the Codex SDK ----------------------------------------------------


def _missing_hooks_are_put_back_on_the_default_branch(repo, gh, tmp_path, monkeypatch, _):
    _client(repo)
    before = repo.forge("doctor")
    assert f"- {HOOKS_ROW}\n  Fix: forge doctor --fix\n" in before.stdout
    assert not _commit_refused(repo)

    done = repo.forge("doctor", "--fix")
    assert HOOKS_FIXED in done.stdout and HOOKS_ROW not in done.stdout
    assert repo.git("branch", "--show-current") == "main"
    # Doctor's own check is that the hooks match what forge sync installs.
    assert HOOKS_ROW not in repo.forge("doctor").stdout
    assert _commit_refused(repo)


def _a_hook_that_is_not_forges_is_kept(repo, gh, tmp_path, monkeypatch, _):
    _client(repo)
    own = _hooks(repo)[0]
    own.write_text("#!/bin/sh\necho our own check\n", encoding="utf-8")
    done = repo.forge("doctor", "--fix")
    assert HOOKS_FIXED in done.stdout
    assert own.with_name("pre-commit.pre-forge").read_text(encoding="utf-8") == (
        "#!/bin/sh\necho our own check\n")


def _a_hook_with_its_pre_forge_copy_is_a_row_not_a_traceback(repo, gh, tmp_path, monkeypatch, _):
    _client(repo)
    own = _hooks(repo)[0]
    own.write_text("#!/bin/sh\necho one\n", encoding="utf-8")
    own.with_name("pre-commit.pre-forge").write_text("#!/bin/sh\necho two\n", encoding="utf-8")
    done = repo.forge("doctor", "--fix")
    assert (f"- {own} and {own}.pre-forge both hold a hook that isn't Forge's; combine them into "
            f"{own}.pre-forge by hand and delete {own}.\n  Fix: forge sync\n") in done.stdout
    assert done.returncode == 1 and "Traceback" not in done.stderr


def _sdk(repo, tmp_path, monkeypatch, workers: str) -> Path:
    _client(repo, workers=workers)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))  # never the real SDK environment
    program = tmp_path / "bundled-codex"
    program.write_text(f"#!/bin/sh\necho codex-cli {SDK_PIN}\n", encoding="utf-8")
    program.chmod(0o755)
    _install(repo.bin, "uv", SDK_UV.format(python=sys.executable, pin=SDK_PIN,
                                           program=str(program)))
    return repo.bin / "uv-calls.jsonl"


def _the_codex_sdk_is_installed_only_where_codex_is_used(repo, gh, tmp_path, monkeypatch, case):
    log = _sdk(repo, tmp_path, monkeypatch, case.split()[0])
    if case == "claude under Claude Code":
        monkeypatch.setenv("CLAUDECODE", "1")
        _install(repo.bin, "codex", "#!/bin/sh\nexit 0\n")
    done = repo.forge("doctor", "--fix")
    if case == "claude":
        assert _uv_calls(log) == [] and "Codex SDK" not in done.stdout
    else:
        assert [call[0] for call in _uv_calls(log)] == ["venv", "pip"]
        assert f"Installed the Codex SDK {SDK_PIN}" in done.stdout
    assert HOOKS_FIXED in done.stdout


def _a_failing_sdk_install_is_a_row(repo, gh, tmp_path, monkeypatch, _):
    _client(repo, workers="codex")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    _install(repo.bin, "uv", f"#!{sys.executable}\nimport sys\n"
                             "sys.stderr.write('uv: the network is down\\n')\nsys.exit(1)\n")
    done = repo.forge("doctor", "--fix")
    assert ("- uv venv failed while installing the Codex SDK: uv: the network is down\n"
            "  Fix: forge doctor --fix\n") in done.stdout
    assert HOOKS_FIXED in done.stdout and _commit_refused(repo)
    assert done.returncode == 1 and done.stderr.startswith("forge doctor found ")


# --- item 3: the folders of finished work -------------------------------------------------------


def _work(repo, tmp_path, branch: str = "fix/done", commit: bool = True) -> tuple[Path, str]:
    """A worktree on its own branch with one commit; returns its folder and its head."""
    folder = tmp_path / branch.replace("/", "-")
    repo.git("worktree", "add", "-q", "-b", branch, str(folder))
    if commit:
        (folder / "change.txt").write_text("a change\n", encoding="utf-8")
        repo.git("add", "change.txt", cwd=folder)
        repo.git("commit", "-q", "-m", "A change", cwd=folder)
    return folder, repo.git("rev-parse", "HEAD", cwd=folder)


def _prs(gh, branch: str, *prs: tuple[str, str], stdout: str = "", exit: int = 0) -> None:
    gh.respond("pr", "list", "--head", branch, exit=exit, stdout=stdout or json.dumps(
        [{"headRefOid": head, "state": state, "a_new_field": 1} for head, state in prs]))


def _gone(repo, folder: Path, branch: str) -> bool:
    return not folder.exists() and branch not in repo.git("branch", "--list", branch)


def _kept(repo, folder: Path, branch: str) -> bool:
    return folder.exists() and branch in repo.git("branch", "--list", branch)


def _a_finished_folder_with_a_lockfile_change_goes(repo, gh, tmp_path, monkeypatch, state):
    _client(repo)
    repo.write("uv.lock", "version = 1\n")
    repo.git("add", "uv.lock")
    repo.git("commit", "-q", "-m", "Lock")
    folder, head = _work(repo, tmp_path)
    (folder / "uv.lock").write_text("version = 2\n", encoding="utf-8")
    _prs(gh, "fix/done", (head, state))
    # Without --fix: only the row, and nothing removed.
    listed = repo.forge("doctor")
    assert (f"- 1 folders hold finished work: {folder}.\n  Fix: forge doctor --fix\n"
            in listed.stdout), listed.stdout
    assert _kept(repo, folder, "fix/done")

    done = repo.forge("doctor", "--fix")
    assert f"- Fixed: removed {folder}, whose pull request is {state.lower()}.\n" in done.stdout
    assert _gone(repo, folder, "fix/done")
    assert ["pr", "list", "--head", "fix/done", "--state", "all", "--limit", "100", "--json",
            "headRefOid,state"] in gh.calls()


def _clean_and_cache_only_folders_are_removed(repo, gh, tmp_path, monkeypatch, _):
    _client(repo)
    repo.write(".gitignore", ".venv/\nnode_modules/\n__pycache__/\n")
    # Caches sit beside tracked code; git lists a folder holding only ignored files as one entry.
    repo.write("src/app.py", "")
    repo.write("web/package.json", "{}\n")
    repo.git("add", ".gitignore", "src", "web")
    repo.git("commit", "-q", "-m", "Ignore caches")
    clean, clean_head = _work(repo, tmp_path, "task/CLEAN")
    cached, cached_head = _work(repo, tmp_path, "story/CACHED")
    for cache in (".venv/bin", "web/node_modules/x", "src/__pycache__"):
        (cached / cache).mkdir(parents=True)
        (cached / cache / "f").write_text("x\n", encoding="utf-8")
    _prs(gh, "task/CLEAN", (clean_head, "MERGED"))
    _prs(gh, "story/CACHED", (cached_head, "MERGED"))
    done = repo.forge("doctor", "--fix")
    assert _gone(repo, clean, "task/CLEAN") and _gone(repo, cached, "story/CACHED"), done.stdout


LEFTOVERS = ["changed file", "untracked file", "ignored .env", "ignored data folder",
             "hidden untracked file", "submodules", "commit past the pull request",
             "open pull request"]


def _a_folder_holding_anything_else_is_kept(repo, gh, tmp_path, monkeypatch, leftover):
    _client(repo)
    repo.write(".gitignore", ".env\ndata/\n")
    repo.git("add", ".gitignore")
    repo.git("commit", "-q", "-m", "Ignore secrets")
    folder, head = _work(repo, tmp_path)
    prs = [(head, "MERGED")]
    if leftover == "changed file":
        (folder / "change.txt").write_text("more\n", encoding="utf-8")
    elif leftover == "untracked file":
        (folder / "notes.md").write_text("notes\n", encoding="utf-8")
    elif leftover == "ignored .env":
        (folder / ".env").write_text("SECRET=1\n", encoding="utf-8")
    elif leftover == "ignored data folder":
        (folder / "data").mkdir()
        (folder / "data" / "rows.csv").write_text("1\n", encoding="utf-8")
    elif leftover == "hidden untracked file":
        repo.git("config", "status.showUntrackedFiles", "no")
        (folder / "notes.md").write_text("notes\n", encoding="utf-8")
    elif leftover == "submodules":
        (folder / ".gitmodules").write_text("", encoding="utf-8")
        repo.git("add", ".gitmodules", cwd=folder)
        repo.git("commit", "-q", "-m", "Submodules", cwd=folder)
        prs = [(repo.git("rev-parse", "HEAD", cwd=folder), "MERGED")]
    elif leftover == "commit past the pull request":
        repo.git("commit", "-q", "--allow-empty", "-m", "Later", cwd=folder)
    else:
        prs.append(("0" * 40, "OPEN"))
    _prs(gh, "fix/done", *prs)
    done = repo.forge("doctor", "--fix")
    assert _kept(repo, folder, "fix/done") and "folders hold finished work" not in done.stdout


def _an_unusable_github_answer_removes_nothing(repo, gh, tmp_path, monkeypatch, answer):
    _client(repo)
    folder, head = _work(repo, tmp_path)
    if answer == "fails":
        _prs(gh, "fix/done", (head, "MERGED"), exit=1)
    elif answer == "not a list":
        _prs(gh, "fix/done", stdout=json.dumps({"headRefOid": head, "state": "MERGED"}))
    else:
        _prs(gh, "fix/done", *[(head, "MERGED")] * 100)
    for args in (("doctor",), ("doctor", "--fix")):
        assert "folders hold finished work" not in repo.forge(*args).stdout
    assert _kept(repo, folder, "fix/done")


def _the_folder_doctor_runs_in_and_the_main_checkout_are_kept(repo, gh, tmp_path, monkeypatch, _):
    _client(repo)
    folder, head = _work(repo, tmp_path)
    _prs(gh, "fix/done", (head, "MERGED"))
    repo.forge("doctor", "--fix", cwd=folder)
    assert _kept(repo, folder, "fix/done")

    # The main checkout on a finished branch, with doctor run from another folder.
    repo.git("checkout", "-q", "-b", "fix/main-here")
    _prs(gh, "fix/main-here", (repo.git("rev-parse", "HEAD"), "MERGED"))
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert repo.path.exists() and repo.git("branch", "--show-current") == "fix/main-here"
    assert "whose pull request is merged" not in done.stdout


def _failed_removals_are_rows_and_the_other_repairs_go_on(repo, gh, tmp_path, monkeypatch, _):
    _client(repo)
    locked, locked_head = _work(repo, tmp_path, "fix/a-locked")
    stuck, stuck_head = _work(repo, tmp_path, "fix/b-stuck-branch")
    free, free_head = _work(repo, tmp_path, "fix/c-free")
    repo.git("worktree", "lock", str(locked))
    # A leftover ref lock makes git refuse to delete that branch.
    (repo.path / ".git" / "refs" / "heads" / "fix" / "b-stuck-branch.lock").write_text("")
    for branch, head in (("fix/a-locked", locked_head), ("fix/b-stuck-branch", stuck_head),
                         ("fix/c-free", free_head)):
        _prs(gh, branch, (head, "MERGED"))
    done = repo.forge("doctor", "--fix")
    assert f"- Forge couldn't remove {locked}: " in done.stdout
    assert "  Fix: unlock it or close programs using it, then forge doctor --fix\n" in done.stdout
    assert _kept(repo, locked, "fix/a-locked")
    assert (f"- Removed {stuck}, but its branch fix/b-stuck-branch is still here: "
            in done.stdout), done.stdout
    assert "  Fix: git branch -D fix/b-stuck-branch\n" in done.stdout
    assert not stuck.exists()
    assert _gone(repo, free, "fix/c-free")
    assert HOOKS_FIXED in done.stdout and done.returncode == 1



def _cases(*cases) -> list:
    """Each case, once per value it takes, named after the case and the value."""
    return [pytest.param(case, value, marks=marks, id=case.__name__.strip("_") + (
                f"[{value}]" if value else "")) for case, values, marks in cases
            for value in values]


@pytest.mark.parametrize("case, value", _cases(
    (_a_newer_pin_is_installed_and_doctor_runs_again_with_it, [None], ()),
    (_a_second_run_still_on_the_wrong_forge_keeps_the_row, [None], ()),
    (_an_older_pin_or_a_dev_build_is_left_alone, ["1.0.0", "dev build"], ()),
    (_a_failing_install_keeps_the_row, [None], ()),
    (_without_uv_the_row_stays, [None], ())))
def test_1_doctor_installs_the_pinned_forge_and_finishes_with_it(repo, gh, tmp_path, monkeypatch,
                                                                 case, value):
    case(repo, gh, tmp_path, monkeypatch, value)


@pytest.mark.parametrize("case, value", _cases(
    (_missing_hooks_are_put_back_on_the_default_branch, [None], ()),
    (_a_hook_that_is_not_forges_is_kept, [None], ()),
    (_a_hook_with_its_pre_forge_copy_is_a_row_not_a_traceback, [None], ()),
    (_the_codex_sdk_is_installed_only_where_codex_is_used,
     ["claude", "claude under Claude Code", "codex"], SHELL),
    (_a_failing_sdk_install_is_a_row, [None], ())))
def test_2_doctor_puts_back_the_git_hooks_and_the_codex_sdk(repo, gh, tmp_path, monkeypatch, case,
                                                           value):
    case(repo, gh, tmp_path, monkeypatch, value)


@pytest.mark.parametrize("case, value", _cases(
    (_a_finished_folder_with_a_lockfile_change_goes, ["MERGED", "CLOSED"], ()),
    (_clean_and_cache_only_folders_are_removed, [None], ()),
    (_a_folder_holding_anything_else_is_kept, LEFTOVERS, ()),
    (_an_unusable_github_answer_removes_nothing, ["fails", "not a list", "100 entries"], ()),
    (_the_folder_doctor_runs_in_and_the_main_checkout_are_kept, [None], ()),
    (_failed_removals_are_rows_and_the_other_repairs_go_on, [None], ())))
def test_3_doctor_removes_only_the_folders_of_finished_work(repo, gh, tmp_path, monkeypatch, case,
                                                            value):
    case(repo, gh, tmp_path, monkeypatch, value)
