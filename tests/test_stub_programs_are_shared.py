"""Shared test programs retain each test's files and cannot corrupt another test."""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from conftest import _install

STORY = "FIX-SHARED-TEST-STUBS"


def test_1_programs_share_readonly_content_and_keep_test_state_local(tmp_path):
    # The old installer wrote a new executable inode per test. Execute the links
    # too: resolving __file__ would send test state into the shared directory.
    source = (f"#!{sys.executable}\nfrom pathlib import Path\n"
              f"# {uuid4()}\n"
              "Path(__file__).absolute().with_name('answer').write_text('first')\n")
    bins = [tmp_path / str(index) for index in range(8)]
    for folder in bins:
        folder.mkdir()
    with ThreadPoolExecutor() as pool:
        list(pool.map(lambda folder: _install(folder, "program", source), bins))
    programs = [folder / "program" for folder in bins]
    if os.name == "nt":
        assert all(not program.is_symlink() for program in programs)
        programs[0].write_text("changed", "utf-8")
        assert programs[1].read_text("utf-8") == source
        programs[0].write_text(source, "utf-8")
        assert all(program.with_suffix(".cmd").exists() for program in programs)
    else:
        assert all(program.is_symlink() for program in programs)
        assert all(program.samefile(programs[0]) for program in programs)
        target = programs[0].resolve()
        inode = target.stat().st_ino
        _install(bins[0], "program", source)
        assert programs[0].stat().st_ino == inode
        assert target.stat().st_mode & 0o222 == 0
        assert target.parent.stat().st_mode & 0o222 == 0
        try:
            programs[0].write_text("corrupt", "utf-8")
        except PermissionError:
            pass
        else:
            raise AssertionError("Shared executable allowed an in-place rewrite")
    for program in programs:
        subprocess.run([sys.executable, str(program)], check=True)
        assert program.with_name("answer").read_text("utf-8") == "first"
    _install(bins[0], "program", source.replace("'first'", "'second'"))
    subprocess.run([sys.executable, str(programs[0])], check=True)
    assert bins[0].joinpath("answer").read_text("utf-8") == "second"
    assert programs[1].read_text("utf-8") == source
