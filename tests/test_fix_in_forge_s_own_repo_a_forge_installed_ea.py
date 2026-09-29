"""In Forge's own repo, a forge installed earlier runs the checkout's code instead of its own."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORY = "in-forge-s-own-repo-a-forge-installed-ea"
# Run forge from the given folder's code, as an installed forge's entry point would.
ENTRY = "import sys; sys.path.insert(0, sys.argv.pop(1)); from forge.cli import main; sys.exit(main())"


def _forge_code(dest: Path, version: str) -> None:
    shutil.copytree(ROOT / "src" / "forge", dest / "forge")
    init = dest / "forge" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    init.write_text(text.replace(text.split('__version__ = "')[1].split('"')[0], version), "utf-8")


def test_1_an_older_install_runs_the_checkout_s_code_and_says_so_once(tmp_path):
    install, checkout = tmp_path / "install", tmp_path / "checkout"
    _forge_code(install, "1.0.0")
    _forge_code(checkout / "src", "7.7.7")
    (checkout / "forge.toml").write_text('version = "v7.7.7"\nrepo = "forge-source"\n', "utf-8")
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)

    ran = subprocess.run([sys.executable, "-c", ENTRY, str(install), "--version"], cwd=checkout,
                         capture_output=True, text=True, encoding="utf-8", timeout=60)

    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.strip() == "forge v7.7.7"
    assert ran.stderr.count("this checkout's code") == 1, ran.stderr
