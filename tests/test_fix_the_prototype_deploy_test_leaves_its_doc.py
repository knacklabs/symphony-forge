STORY = "FIX-THE-PROTOTYPE-DEPLOY-TEST-LEAVES-ITS-DOC"

import shutil
import subprocess
import time
import uuid

import pytest

from test_proto_deploy import LABEL, LINUX_CONTAINERS, _remove_stale_leftovers


def _docker(*args):
    return subprocess.run(["docker", *args], text=True, capture_output=True, timeout=180)


def _exists(kind, name):
    return _docker(kind, "inspect", name).returncode == 0


@LINUX_CONTAINERS
def test_1_old_labelled_leftover_is_removed_and_a_fresh_one_is_kept():
    if not shutil.which("docker") or _docker("info").returncode:
        pytest.skip("Docker daemon is required to prove leftover cleanup")
    tag = "forge-proto-leftover-" + uuid.uuid4().hex[:12]
    # A run killed two hours ago, and a run that started a moment ago and is still going.
    old = (f"{LABEL}={time.time() - 7200:.0f}", tag + "-old")
    fresh = (f"{LABEL}={time.time():.0f}", tag + "-fresh")
    try:
        for label, name in (old, fresh):
            assert _docker("network", "create", "--label", label, name).returncode == 0
            made = _docker("create", "--label", label, "--name", name, "--network", name,
                           "postgres:16-alpine")
            assert made.returncode == 0, made.stderr
        _remove_stale_leftovers()
        assert not _exists("container", old[1])
        assert not _exists("network", old[1])
        assert _exists("container", fresh[1])
        assert _exists("network", fresh[1])
    finally:
        for _, name in (old, fresh):
            _docker("rm", "-f", name)
            _docker("network", "rm", name)
