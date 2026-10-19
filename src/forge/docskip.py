"""The docs-only rule, also copied into the self-contained client CI script."""
import shutil
import subprocess
from pathlib import Path


def only_docs(top: Path, base: str, excludes: list[str], *, allow_settings: bool = False) -> bool:
    """Generated files always need tests, even under a documentation exclusion."""
    def git(*args: str, input: str | None = None) -> str:
        return subprocess.run([shutil.which("git") or "git", *args], cwd=top, input=input,
                              check=True, capture_output=True, text=True,
                              encoding="utf-8").stdout

    diff = ("diff", "--name-only", "-z", "--no-renames", f"{base}...HEAD")
    remaining = git(*diff, "--", ".", *excludes).strip("\0")
    if remaining and not (allow_settings and remaining == "forge.toml"):
        return False
    paths = git(*diff)
    if paths:
        attributes = git("check-attr", "-z", "--stdin", "linguist-generated", input=paths)
        values = attributes.strip("\0").split("\0")[2::3]
        if any(value.lower() not in {"unspecified", "unset", "false"} for value in values):
            return False
    return True
