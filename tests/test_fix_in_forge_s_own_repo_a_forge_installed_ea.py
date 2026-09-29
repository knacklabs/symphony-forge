"""In Forge's own repo, a forge installed earlier from the checkout runs the checkout's code instead."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORY = "in-forge-s-own-repo-a-forge-installed-ea"
# Run forge from the given install folder, as an installed forge's entry point would.
ENTRY = "import sys; sys.path.insert(0, sys.argv.pop(1)); from forge.cli import main; sys.exit(main())"


def _forge_code(dest: Path, version: str) -> None:
    shutil.copytree(ROOT / "src" / "forge", dest / "forge")
    init = dest / "forge" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    init.write_text(text.replace(text.split('__version__ = "')[1].split('"')[0], version), "utf-8")


def _install(tmp_path: Path, made_from: Path) -> Path:
    """An installed forge v1.0.0, recording the folder it was installed from as pip and uv do."""
    install = tmp_path / "install"
    _forge_code(install, "1.0.0")
    info = install / "symphony_forge-1.0.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: symphony-forge\nVersion: 1.0.0\n",
                                   "utf-8")
    (info / "direct_url.json").write_text(json.dumps({"url": made_from.as_uri(), "dir_info": {}}),
                                          "utf-8")
    return install


def _checkout(path: Path) -> Path:
    """A newer forge-source checkout, v7.7.7."""
    _forge_code(path / "src", "7.7.7")
    (path / "forge.toml").write_text('version = "v7.7.7"\nrepo = "forge-source"\n', "utf-8")
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path, check=True,
                               capture_output=True, text=True).stdout.strip())


def _version(install: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", ENTRY, str(install), "--version"], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def test_1_an_older_install_runs_the_checkout_s_code_and_says_so_once(tmp_path):
    checkout = _checkout(tmp_path / "checkout")
    ran = _version(_install(tmp_path, made_from=checkout), checkout)

    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.strip() == "forge v7.7.7"
    assert ran.stderr.count("this checkout's code") == 1, ran.stderr


def test_2_another_repo_claiming_to_be_forge_never_runs_its_code(tmp_path):
    forge_checkout = _checkout(tmp_path / "forge")
    other = _checkout(tmp_path / "other")
    ran = _version(_install(tmp_path, made_from=forge_checkout), other)

    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.strip() == "forge v1.0.0"
    assert "this checkout's code" not in ran.stderr
