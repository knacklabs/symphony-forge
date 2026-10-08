"""A silent SDK interpreter failure reports its exit status at the work command boundary.

Only the external SDK interpreter's startup is made to fail. The real worker must refuse
before launching a model, preserving the pin check and exposing the diagnostic CI lost.
"""
import json

from test_codex_worker import PIN, _codex_repo, sdk_data  # noqa: F401

STORY = "agent-allowance"


def test_1_work_reports_the_sdk_interpreters_silent_exit_status(repo, monkeypatch, sdk_data,
                                                             tmp_path):
    _, calls = _codex_repo(repo, monkeypatch, sdk_data)
    sdk = sdk_data / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
    startup = tmp_path / "failed-sdk-startup"
    startup.mkdir()
    (startup / "sitecustomize.py").write_text(
        "import os, pathlib, sys\n"
        f"if pathlib.Path(sys.prefix).resolve() == pathlib.Path({json.dumps(str(sdk.resolve()))}):\n"
        "    os._exit(42)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(startup))

    refused = repo.forge("work", "BOARD/PAGE")

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert refused.stderr == (
        f"The Codex SDK in {sdk} should be openai-codex {PIN}, openai-codex-cli-bin {PIN}, "
        f"codex-cli {PIN}, but its Python says: it exited with status 42 without output\n"
        "Next: forge doctor --fix\n")
    assert not calls.exists(), "A failed SDK probe must start no model"
