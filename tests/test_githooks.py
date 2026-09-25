"""The git hooks: commits only on Forge's branches, and fixes stay small unless the human allows."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

NEXT_PROMOTE = "Next: forge story new <KEY> --from-fix {fix}\n"


def hooked(repo, interfaces=()):
    """Pin Forge on main, then install the two git hook shims the way forge sync does."""
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ninterfaces = {json.dumps(list(interfaces))}\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    for name in ("pre-commit", "pre-push"):
        shim = repo.path / ".git" / "hooks" / name
        shim.write_text(f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" '
                        f'"{(repo.bin / "forge").as_posix()}" hook {name} "$@"\n', encoding="utf-8")
        shim.chmod(0o755)


def start_fix(repo, why: str) -> tuple[str, Path]:
    started = repo.forge("fix", "start", why, "--done", "It works")
    assert started.returncode == 0, started.stderr
    name = started.stdout.split()[2]
    folder = repo.path.parent / f"repo-fix-{name}"
    printed = started.stdout.splitlines()[0].split(" in ", 1)[1]
    assert Path(printed).resolve() == folder.resolve()
    return name, folder


def commit(folder: Path, *files: str, flags: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    for rel in files:
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(f"{rel}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=folder, check=True)
    return subprocess.run(["git", "commit", "-q", "-m", "Work", *flags], cwd=folder,
                          capture_output=True, text=True, encoding="utf-8")


def push(folder: Path, *refspec: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "push", "-q", "origin", *refspec], cwd=folder,
                          capture_output=True, text=True, encoding="utf-8")


def test_20_pre_commit(repo):
    hooked(repo, interfaces=["**/routes/**"])

    on_main = commit(repo.path, "app.py")
    assert on_main.returncode != 0
    assert on_main.stderr == ("Forge changes nothing on main; work happens on a story, task or fix "
                              'branch.\nNext: forge fix start "<why>" --done "<done when>"\n')

    repo.git("checkout", "-q", "-b", "my-idea")
    not_forge = commit(repo.path, "app.py")
    assert not_forge.stderr == ("my-idea was not started by Forge, so it has no story, task or fix.\n"
                                'Next: forge fix start "<why>" --done "<done when>"\n')

    fix, folder = start_fix(repo, "Fix the login typo")
    assert commit(folder, *(f"src/f{n}.py" for n in range(5))).returncode == 0
    # Markdown, planning documents and state never count.
    assert commit(folder, "docs/notes.md", "plans/roadmap.json", ".factory/x.json").returncode == 0
    sixth = commit(folder, "src/f5.py")
    assert sixth.returncode != 0
    assert sixth.stderr == (
        f"Fix {fix} changes 6 code files, over the limit of 5, so it has to become a story, unless "
        "the human allows it with forge fix allow-large.\n" + NEXT_PROMOTE.format(fix=fix))

    fix, folder = start_fix(repo, "Rename the users route")
    interface = commit(folder, "api/routes/users.py")
    assert interface.stderr == (
        f"Fix {fix} changes the interface api/routes/users.py, so it has to become a story, unless "
        "the human allows it with forge fix allow-large.\n" + NEXT_PROMOTE.format(fix=fix))


def test_21_pre_push(repo):
    hooked(repo)
    fix, folder = start_fix(repo, "Fix the login typo")
    assert commit(folder, "src/app.py").returncode == 0
    assert push(folder, f"fix/{fix}").returncode == 0

    to_main = push(folder, "HEAD:main")
    assert to_main.returncode != 0
    assert ("main changes only through a merged pull request, so this push is refused.\n"
            "Next: forge close <item>\n") in to_main.stderr

    # Commits made with --no-verify skip pre-commit, but not pre-push. The destination names the
    # fix, so pushing the branch, its commit ID or another branch to it is refused alike.
    assert commit(folder, *(f"src/f{n}.py" for n in range(5)), flags=("--no-verify",)).returncode == 0
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=folder, capture_output=True, text=True,
                         check=True).stdout.strip()
    subprocess.run(["git", "branch", "side"], cwd=folder, check=True)
    for refspec in (f"fix/{fix}", f"{sha}:refs/heads/fix/{fix}", f"side:fix/{fix}"):
        over = push(folder, refspec)
        assert over.returncode != 0, refspec
        assert (f"Fix {fix} changes 6 code files, over the limit of 5, so it has to become a story, "
                "unless the human allows it with forge fix allow-large.\n"
                + NEXT_PROMOTE.format(fix=fix)) in over.stderr, refspec


def test_39_fix_lines_and_permission(repo):
    hooked(repo)
    no_done = repo.forge("fix", "start", "Fix the login typo")
    assert no_done.returncode != 0 and "--done" in no_done.stderr and "Next: " in no_done.stderr
    for why, done in ((" ", "It works"), ("Fix the typo", ""), ("Fix\nthe typo", "It works")):
        refused = repo.forge("fix", "start", why, "--done", done)
        assert refused.stderr == ("A fix needs a one-line why and a one-line done-when.\n"
                                  'Next: forge fix start "<why>" --done "<done when>"\n')

    fix, folder = start_fix(repo, "Rename the user model")
    assert commit(folder, *(f"src/f{n}.py" for n in range(6))).returncode != 0

    outside = repo.forge("fix", "allow-large", "The rename touches six files")
    assert outside.stderr == ("main is not a fix, and allow-large works only inside a fix's folder.\n"
                              'Next: cd <the fix folder> && forge fix allow-large "<reason>"\n')
    blank = repo.forge("fix", "allow-large", " ", cwd=folder)
    assert blank.stderr == ("The permission needs a one-line reason.\n"
                            'Next: forge fix allow-large "<reason>"\n')

    allowed = repo.forge("fix", "allow-large", "The rename touches six files", cwd=folder)
    assert allowed.returncode == 0, allowed.stderr
    assert commit(folder).returncode == 0
    assert push(folder, f"fix/{fix}").returncode == 0
    assert "The rename touches six files" in repo.git(
        "show", f"HEAD:.factory/fixes/{fix}.json", cwd=folder)
