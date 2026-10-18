"""Concurrent test SDK rebuilds publish a complete environment and keep the winner."""
from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import threading

import pytest

from conftest import REAL_UV, _install_claude_sdk
from test_codex_worker import PIN, sdk_data

STORY = "sdk-cache-race"


@pytest.mark.parametrize("sdk", ["codex", "claude"])
def test_1_concurrent_rebuilds_keep_one_ready_sdk(tmp_path, monkeypatch, pytestconfig, sdk):
    if sdk == "codex" and REAL_UV is None:
        pytest.skip("uv is missing, so the Codex SDK test environment can't be built")
    data = tmp_path / "data"
    pin = PIN if sdk == "codex" else "0.2.161"
    name = f"openai-codex-{pin}" if sdk == "codex" else f"claude-agent-sdk-{pin}"
    env = data / "forge" / f"{sdk}-sdk" / name
    env.mkdir(parents=True)
    # A ready marker whose Python disappeared after a restart is still a broken cache.
    (env / "forge-sdk-ready").write_text(pin + "\n", encoding="utf-8")
    stale = env / "stale"
    stale.touch()
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    winner = env / "in-use"
    monkeypatch.setattr(pytestconfig.cache, "mkdir", lambda name: data)
    installing = threading.Barrier(2, timeout=30)
    published = threading.Event()
    run = subprocess.run

    def concurrent_install(command, *args, **kwargs):
        if "venv" in command:
            # Both callers have found the same stale cache before either build finishes.
            position = installing.wait()
            if position == 1:
                assert published.wait(60), "The first rebuild did not finish"
            result = run(command, *args, **kwargs)
            if position == 0:
                assert stale.exists(), "A rebuild removed the public cache before publication"
                assert not python.exists(), "An unfinished build is visible in the public cache"
            else:
                assert winner.exists(), "A rebuild removed the SDK another worker is using"
            return result
        return run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", concurrent_install)

    def rebuild(worker):
        try:
            if sdk == "codex":
                sdk_data.__wrapped__(pytestconfig)
            else:
                bin_dir = tmp_path / f"bin-{worker}"
                bin_dir.mkdir()
                _install_claude_sdk(bin_dir, data)
            if published.is_set():
                assert winner.exists(), "The later publisher replaced an SDK already in use"
            else:
                winner.touch()
        finally:
            published.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(rebuild, worker) for worker in range(2)]
        for future in futures:
            future.result(timeout=90)
    assert winner.exists()
    assert not stale.exists(), "The broken cache was not replaced"
    assert (env / "forge-sdk-ready").read_text("utf-8") == pin + "\n"
    code = "import openai_codex" if sdk == "codex" else "pass"
    run([python, "-I", "-c", code], check=True, timeout=10)
