"""The docs-only rule, also copied into the self-contained client CI script."""
import ast
import posixpath
import re
import shutil
import subprocess
from pathlib import Path

PATH_LITERALS = r'''(["'`])((?:\\.|(?!\1)[^\\\r\n])*)\1'''


def reads_file_relative(source: str, basenames: set[str]) -> bool:
    """Match literals in file-relative paths, not unrelated content assertions."""
    if not basenames or not re.search(r"\b__file__\b", source):
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Embedded Python and newer syntax still get the conservative check.
        return any(posixpath.basename(literal[2].replace("\\", "/")) in basenames
                   for literal in re.finditer(PATH_LITERALS, source))
    roots = {"__file__"}

    def rooted(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in roots
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            return rooted(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
            return rooted(node.left) or rooted(node.right)
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            return name in {"Path", "join", "dirname", "abspath", "realpath", "normpath",
                            "resolve", "absolute", "joinpath", "with_name", "with_suffix"} and (
                rooted(node.func) or any(rooted(arg) for arg in node.args))
        return False

    assignments = [node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign))]
    while True:
        before = len(roots)
        for node in assignments:
            if rooted(node.value):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                roots.update(target.id for target in targets if isinstance(target, ast.Name))
        if len(roots) == before:
            break
    for node in ast.walk(tree):
        if isinstance(node, (ast.BinOp, ast.Call)) and rooted(node) and any(
                isinstance(part, ast.Constant) and isinstance(part.value, str)
                and posixpath.basename(part.value.replace("\\", "/")) in basenames
                for part in ast.walk(node)):
            return True
    return False


def test_readers(files: list[Path], picked: set[Path]) -> set[Path]:
    """Keep every text reference, including plugin strings and scoped conftest users."""
    texts = {path: path.read_text("utf-8-sig") for path in files}
    while True:
        names = {path.stem for path in picked}
        fixtures = [path.parent for path in picked if path.name == "conftest.py"]
        expanded = picked | {path for path, text in texts.items()
                             if any(name in text for name in names)
                             or any(path.is_relative_to(folder) for folder in fixtures)}
        if expanded == picked:
            return picked
        picked = expanded


def only_docs(top: Path, base: str, excludes: list[str], *, allow_settings: bool = False,
              head: str = "HEAD") -> bool:
    """Generated files and inputs read by code always need the full checks."""
    def git(*args: str, input: str | None = None) -> str:
        return subprocess.run([shutil.which("git") or "git", *args], cwd=top, input=input,
                              check=True, capture_output=True, text=True,
                              encoding="utf-8").stdout

    diff = ("diff", "--name-only", "-z", "--no-renames", f"{base}...{head}")
    remaining = git(*diff, "--", ".", *excludes).strip("\0")
    if remaining and not (allow_settings and remaining == "forge.toml"):
        return False
    paths = git(*diff)
    if paths:
        attributes = git("check-attr", "-z", "--stdin", "linguist-generated", input=paths)
        values = attributes.strip("\0").split("\0")[2::3]
        if any(value.lower() not in {"unspecified", "unset", "false"} for value in values):
            return False
        tests = [":(glob)**/test*/**", ":(glob)**/*.test.*", ":(glob)**/*.spec.*",
                 ":(glob)**/test_*.py", ":(glob)**/*_test.py",
                 ":(glob)**/__tests__/**", ":(glob)**/conftest.py"]
        if git(*diff, "--", *tests):
            return False
        # Check both sides: deleting an input still needs its consumer's tests.
        changed = paths.strip("\0").split("\0")
        patterns = sorted({posixpath.basename(path) for path in changed})
        found = subprocess.run([shutil.which("git") or "git", "grep", "-I", "-l", "-z", "-F",
                                *[arg for name in patterns for arg in ("-e", name)],
                                base, head, "--", ".", *excludes,
                                ":(exclude,glob)**/.gitattributes"], cwd=top, capture_output=True,
                                text=True, encoding="utf-8")
        if found.returncode not in (0, 1):
            return False
        targets = {posixpath.normpath(posixpath.join(top.as_posix(), path)) for path in changed}
        quoted = r'''(?:'[^'\r\n]*'|"[^"\r\n]*"|`[^`\r\n]*`)'''
        joined = re.compile(rf"\b(?:Path|join)\(\s*(?:__dirname\s*,\s*)?{quoted}"
                            rf"(?:\s*,\s*{quoted})*\s*\)(?:\s*/\s*{quoted})*")
        for consumer in filter(None, found.stdout.split("\0")):
            folder = posixpath.dirname(consumer.partition(":")[2])
            roots = ("", top.as_posix(), posixpath.join(top.as_posix(), folder))
            source = git("show", consumer)
            # File-relative expressions cannot always be resolved from literals alone.
            # Prefer extra tests when a quoted basename could read the changed input.
            if reads_file_relative(source, set(patterns)):
                return False
            # A basename finds candidates, not consumers: resolve whole path literals.
            # Fold literal path joins so their components cannot match unrelated root files.
            source = joined.sub(lambda call: repr(posixpath.join(*(
                value[2] for value in re.finditer(PATH_LITERALS, call[0])))), source)
            for literal in re.finditer(PATH_LITERALS, source):
                name = literal[2].replace("\\", "/")
                if any(posixpath.normpath(posixpath.join(root, name)) in targets for root in roots):
                    return False
    return True
