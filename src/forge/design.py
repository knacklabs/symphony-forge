"""The design folder bound by a story approval, and the prototype's design decision."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path, PurePosixPath

from forge import repo

IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def has_app_code(top: Path, ref: str, base: str = "") -> bool:
    """App changes exclude the canvas, records and files Forge itself writes.

    Without a base, inspect history: deleting an old app does not undo its working build.
    """
    from forge import sync

    skeleton = sync.TEMPLATES / "skeleton"
    scaffold = {"forge.toml", "plans/roadmap.json"}
    scaffold.update(path.relative_to(skeleton).as_posix()
                    for path in skeleton.rglob("*") if path.is_file())
    managed = repo.command_fact(("prototype managed paths",), top,
        lambda: {*scaffold, *sync.files(top, repo.config(top), check_syntax=False)})
    excluded = [f":(exclude,literal){name}" for name in managed]
    excluded += [f":(exclude,glob){name}**" for name in
                 ("docs/", "plans/", ".factory/", ".forge/", ".github/", ".claude/", ".codex/")]
    excluded.append(":(exclude,glob,icase)**/*.md")
    args = (("diff", "--name-only", "--no-renames", f"{base}...{ref}") if base else
            ("log", "--first-parent", "--diff-merges=first-parent", "--format=", "--name-only", ref))
    return bool(repo.git(*args, "--", ".", *excluded, cwd=top))


def working_build(top: Path, base: str) -> bool:
    from forge import story

    def find() -> bool:
        for ref in ("HEAD", base):
            names = repo.git("ls-tree", "-r", "--name-only", ref, "--", "docs/decisions", cwd=top)
            for name in names.splitlines():
                if not re.fullmatch(r"docs/decisions/\d{4,}-prototype-build\.md", name):
                    continue
                front = story.FRONTMATTER.match(story.show(top, ref, name) or "")
                if front and re.search(r"^status:\s*[\"']?accepted[\"']?\s*$", front[1], re.M):
                    return True
        return has_app_code(top, base)

    return repo.command_fact(("prototype working build", base), top, find)


def require_working_build(top: Path, base: str) -> None:
    if (repo.is_prototype(top, refs=(base, "HEAD")) and has_app_code(top, "HEAD", base)
            and not working_build(top, base)):
        repo.refuse(("This prototype needs the owner's accepted request before app code can merge.",
                     "forge decision new prototype-build"))


def check(top: Path, text: str, ref: str | None = None, *, required: bool = True) -> str | None:
    from forge import story

    body = story.sections(text).get("What changes for you", "").strip()
    if not required and not re.search(r"^Design:", body, re.M):
        return None  # Existing approvals adopt the rule at their next read and approval.
    if not any(row["User-facing"].lower() in ("yes", "true") for row in story.parse(text)["tasks"]):
        return None
    line = body.splitlines()[-1] if body else ""
    match = re.fullmatch(r"Design: (docs/design/[^/\s]+/) \(([0-9a-f]{40}|[0-9a-f]{64})\)", line)
    next_step = ('save the screens and images in docs/design/<KEY>/, add '
                 'Design: docs/design/<KEY>/ (<tree id>) at the end of What changes for you, '
                 'then run forge read <KEY>')
    if not match or len(re.findall(r"^Design:", body, re.M)) != 1:
        repo.refuse(("This user-facing story needs its design folder and tree id in the approved text.", next_step))
    folder, expected = match.groups()
    if PurePosixPath(folder).name in {".", ".."}:
        repo.refuse(("The design folder must be inside docs/design/.", next_step))
    actual, files = repo.command_fact(("design snapshot", top.resolve(), folder, ref), top,
                                     lambda: snapshot(top, folder, ref))
    if not any(PurePosixPath(name).suffix.lower() in IMAGES for name in files):
        repo.refuse(("The design folder has no screen images.", next_step))
    if actual != expected:
        repo.refuse(("The design folder changed; its tree id no longer matches the plan.", next_step))
    return folder


def snapshot(top: Path, folder: str, ref: str | None = None) -> tuple[str, list[str]]:
    """Hash checkout files with Git's own filters, without changing the caller's index."""
    if ref is None:
        path = top / folder
        if not path.is_dir() or any(part.is_symlink() for part in (path, *path.parents)):
            return "", []
        entries = list(path.rglob("*"))
        if not any(p.is_file() for p in entries) or any(p.is_symlink() for p in entries):
            return "", []
        with tempfile.TemporaryDirectory(dir=repo.forge_dir(top), prefix="design-") as temp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(temp) / "index")}
            repo.run("git", "add", "-f", "--all", "--", folder, cwd=top, env=env).check_returncode()
            tree = repo.run("git", "write-tree", f"--prefix={folder}", cwd=top, env=env)
    else:
        tree = repo.run("git", "rev-parse", "--verify", f"{ref}:{folder.rstrip('/')}", cwd=top)
    if tree.returncode:
        return "", []
    digest = tree.stdout.strip()
    files = repo.git("ls-tree", "-r", "--name-only", "-z", digest, cwd=top).strip("\0").split("\0")
    return digest, files


def require_prototype(top: Path, base: str) -> None:
    from forge import story

    next_step = ('save the screens and images in docs/design/prototype/ in a mechanical fix, '
                 'then forge decision new prototype-design and '
                 'forge decision accept prototype-design --by "<name>"')
    names = repo.git("ls-tree", "-r", "--name-only", base, "--", "docs/decisions", cwd=top).splitlines()
    for name in names:
        if not re.fullmatch(r"docs/decisions/\d{4}-prototype-design\.md", name):
            continue
        front = story.FRONTMATTER.match(story.show(top, base, name) or "")
        if front and re.search(r"^status:\s*[\"']?accepted[\"']?\s*$", front[1], re.M):
            expected = re.search(r"^design_tree: ([0-9a-f]+)\s*$", front[1], re.M)
            actual, files = snapshot(top, "docs/design/prototype/", base)
            if expected and actual == expected[1] and any(PurePosixPath(file).suffix.lower() in IMAGES for file in files):
                if not (story.show(top, base, "PRODUCT.md") or "").strip():
                    repo.refuse(("This prototype needs PRODUCT.md from the design skill's init before a UI fix can start.",
                                 "run impeccable init, commit PRODUCT.md in a mechanical fix, then retry this UI fix"))
                return
    repo.refuse(("This prototype needs an approved design before a UI fix can start.", next_step))


def prototype_tree(top: Path) -> str:
    """Only committed screens can be the subject of the design decision."""
    actual, files = snapshot(top, "docs/design/prototype/", "HEAD")
    current, _ = snapshot(top, "docs/design/prototype/")
    if actual != current or not any(PurePosixPath(file).suffix.lower() in IMAGES for file in files):
        repo.refuse(("The prototype design needs committed screen images before approval.",
                     "save and commit docs/design/prototype/, then forge decision accept prototype-design --by \"<name>\""))
    return actual
