"""The docs-only rule, also copied into the self-contained client CI script."""
import posixpath
import re
import shutil
import subprocess
from pathlib import Path


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
                                base, head, "--", ".", *excludes], cwd=top, capture_output=True,
                                text=True, encoding="utf-8")
        if found.returncode not in (0, 1):
            return False
        targets = {posixpath.normpath(posixpath.join(top.as_posix(), path)) for path in changed}
        strings = r'''(["'`])((?:\\.|(?!\1)[^\\\r\n])*)\1'''
        quoted = r'''(?:'[^'\r\n]*'|"[^"\r\n]*"|`[^`\r\n]*`)'''
        joined = re.compile(rf"\b(?:Path|join)\(\s*(?:__dirname\s*,\s*)?{quoted}"
                            rf"(?:\s*,\s*{quoted})*\s*\)(?:\s*/\s*{quoted})*")
        for consumer in filter(None, found.stdout.split("\0")):
            folder = posixpath.dirname(consumer.partition(":")[2])
            roots = ("", top.as_posix(), posixpath.join(top.as_posix(), folder))
            # A basename finds candidates, not consumers: resolve whole path literals.
            # Fold literal path joins so their components cannot match unrelated root files.
            source = joined.sub(lambda call: repr(posixpath.join(*(
                value[2] for value in re.finditer(strings, call[0])))), git("show", consumer))
            for literal in re.finditer(strings, source):
                name = literal[2].replace("\\", "/")
                if any(posixpath.normpath(posixpath.join(root, name)) in targets for root in roots):
                    return False
    return True
