"""The Python assistant model template keeps its key and monthly cap in settings."""

import py_compile
import runpy
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from assistant_copy_python import copy_assistant_python
from conftest import FORGE_SHIM, _install
from test_agent_ready import _new_client
from test_mcp import _adopted_files_after_sync
from test_starter_tree import LIVE, _require_cases, _run_live_starter


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src/forge/templates/skills/agents/assistant-module/python"
STORY = "FORGE-ASSIST-1/PYMODEL"


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize(
    "target", ["python", "earlier adopted", "python labelled secrets"]
)
def test_5_python_key_and_cap_come_from_settings(
    repo, gh, tmp_path, tmp_path_factory, target
):
    # Audit: copying the module must include its settings, usage, prompt and secret
    # checks, and the copied API tests exercise the module's real Postgres boundary.
    # Existing chat/storage coverage does not own model settings or usage costs.
    # No test-only production seam is needed.
    if target == "python labelled secrets":
        # Pure guard cases: the app test owns existing separators and card checks.
        # These cases catch whitespace labels before any persistence or model call.
        guard = runpy.run_path(str(TEMPLATE / "apps/api/app/assistant/guard.py"))
        contains_secret = guard["contains_secret"]
        for message in ("OTP 123456", "password hunter2", "Password\thunter2"):
            assert contains_secret(message), message
        assert not contains_secret("hunter2")  # The approved unlabelled limit stays.
        return

    # An installed wheel has Python bytecode beside its source templates. Exercise
    # both init and sync against that package, not only the editable checkout.
    built = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path / "dist")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    package = tmp_path / "installed"
    with zipfile.ZipFile(next((tmp_path / "dist").glob("*.whl"))) as wheel:
        wheel.extractall(package)
    compiled = py_compile.compile(
        str(
            package
            / "forge/templates/skills/agents/assistant-module/python/apps/api/app/assistant/guard.py"
        ),
        doraise=True,
    )
    assert Path(compiled).is_file()
    _install(
        repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(package))
    )
    if target == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert before == after
        for host in ("claude", "codex"):
            adopted = (
                repo.path
                / f".{host}/skills/agents/assistant-module/python/apps/api/app/assistant/model.py"
            )
            assert (
                adopted.read_bytes()
                == (TEMPLATE / "apps/api/app/assistant/model.py").read_bytes()
            )
        return

    client = _new_client(repo, gh, tmp_path, "python")
    assert not (client / "apps/api/app/assistant").exists()
    copy_assistant_python(client)

    for name in ("model.py", "usage.py", "prompt.py", "guard.py"):
        assert (client / "apps/api/app/assistant" / name).is_file(), name
    assert (client / "apps/api/tests/test_assistant_model.py").is_file()
    assert (
        client / "apps/api/migrations/versions/20261106_assistant_usage.py"
    ).is_file()

    if LIVE:
        script = client / "scripts/test.mjs"
        text = script.read_text(encoding="utf-8")
        sync = "  run('uv', ['--directory', 'apps/api', 'sync', '--frozen']);"
        if text.count(sync) != 1:
            raise AssertionError(
                f"copy step did not match one lock command in {script}"
            )
        script.write_text(
            text.replace(
                sync,
                "  const frozen = environment.UV_FROZEN;\n"
                "  environment.UV_FROZEN = '0';\n"
                "  run('uv', ['--directory', 'apps/api', 'lock']);\n"
                "  environment.UV_FROZEN = frozen;\n" + sync,
            ),
            encoding="utf-8",
        )
        result = _run_live_starter(tmp_path_factory, [(client, Path("."))])
        _require_cases(
            result["api"],
            (
                "test_only_the_model_settings_read_the_assistant_key",
                "test_the_assistant_module_contains_no_provider_key",
                "test_missing_model_settings_stop_assistant_startup_with_plain_messages",
                "test_the_model_uses_its_configured_key_model_and_prices",
                "test_the_monthly_cap_counts_current_usage_across_accounts_only",
                "test_the_prompt_is_bounded_and_secrets_are_refused",
            ),
        )
