"""The close command runs Forge's source for an unpublished pin.

This protects a close after a release version bump but before publication. A regression makes
the command ask uv for a missing Git release. Existing pin handoff tests cover published
releases only. This runs close through Forge's CLI; the uv stub only stands in for package
resolution, and no production-only seam is needed.
"""

import json
import re
import shutil
import sys
from pathlib import Path

from conftest import FORGE_SHIM, ROOT, _install

STORY = "FIX-CLOSE-CATCHES-WORKFLOW-DRIFT"


def test_3_close_runs_an_unpublished_forge_source_pin_from_its_checkout(
        repo, tmp_path):
    source = tmp_path / "source"
    repo.git("clone", "--no-tags", ROOT.as_posix(), source.as_posix(), cwd=tmp_path)
    current = re.search(r'__version__ = "([^"]+)"',
                        (source / "src" / "forge" / "__init__.py").read_text("utf-8"))[1]
    repo.git("tag", "v0.0.1", cwd=source)
    source_init = source / "src" / "forge" / "__init__.py"
    source_init.write_text(re.sub(r'__version__ = "[^"]+"', '__version__ = "0.0.2"',
                                  source_init.read_text("utf-8")), "utf-8")
    shutil.copyfile(ROOT / "src" / "forge" / "repo.py", source / "src" / "forge" / "repo.py")

    installed = tmp_path / "installed" / "src"
    shutil.copytree(ROOT / "src" / "forge", installed / "forge")
    init = installed / "forge" / "__init__.py"
    init.write_text(re.sub(r'__version__ = "[^"]+"', '__version__ = "0.0.1"',
                           init.read_text("utf-8")), "utf-8")
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable,
                                                   src=installed.as_posix()))

    calls = repo.bin / "uv-calls.jsonl"
    _install(repo.bin, "uv", f'''#!{sys.executable}
import json, pathlib, sys
args = sys.argv[1:]
with open({json.dumps(calls.as_posix())}, "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
if args[:3] == ["tool", "run", "--from"]:
    print("Failed to resolve --with requirement from the unpublished release", file=sys.stderr)
    sys.exit(1)
assert args[:2] == ["run", "--project"], args
project = pathlib.Path(args[2])
assert args[3] == "forge", args
sys.path.insert(0, str(project / "src"))
from forge.cli import main
sys.exit(main(args[4:]))
''')

    done = repo.forge("close", "missing-fix", cwd=source)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "Forge has not started missing-fix" in done.stderr
    assert "Failed to resolve --with requirement" not in done.stderr
    assert (f"Forge v{current} is not published yet, so this checkout runs through uv."
            in done.stderr)
    [args] = [json.loads(line) for line in calls.read_text("utf-8").splitlines()]
    assert args[:2] == ["run", "--project"]
    assert Path(args[2]) == source
    assert args[3:] == ["forge", "close", "missing-fix"]
    assert f'version = "v{current}"' in (source / "forge.toml").read_text("utf-8")
