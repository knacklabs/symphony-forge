"""The docs-only rule, also copied into the self-contained client CI script."""
import shutil
import subprocess
from pathlib import Path


def only_docs(top: Path, base: str, excludes: list[str], *, allow_settings: bool = False,
              head: str = "HEAD") -> bool:
    """Generated files and test inputs always need the full checks."""
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
                 ":(glob)**/test_*.py", ":(glob)**/*_test.py"]
        if git(*diff, "--", *tests):
            return False
        # Check both sides: deleting an input still needs its consumer's tests.
        patterns = sorted({name for path in paths.strip("\0").split("\0")
                           for name in (path, Path(path).name)})
        found = subprocess.run([shutil.which("git") or "git", "grep", "-I", "-l", "-F",
                                *[arg for name in patterns for arg in ("-e", name)],
                                base, head, "--", *tests], cwd=top, capture_output=True)
        if found.returncode != 1:  # A match or an unreadable tree keeps the full checks.
            return False
    return True
