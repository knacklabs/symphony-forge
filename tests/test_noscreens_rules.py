"""The screen rule specs ship in new apps and wait until their screens exist."""
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from test_setup import _fresh_client

STORY = "FORGE-NOSCREENS-1"
ROOT = Path(__file__).resolve().parents[1]
RULE_SCREENS = ("sign-in", "reset-password", "accept-invite", "members")
AUTH_CASES = (
    'five failed sign-ins lock the email for 15 minutes',
    'an unknown email is counted and locked the same way',
    'a good sign-in clears the count',
    'an unknown email takes about as long to refuse as a wrong password',
    'an invite answers its link and the link opens once',
    'an expired invite link is refused',
    'an admin makes a reset link that works once',
    'an expired reset link is refused',
    'a member cannot make a reset link',
    "an admin cannot make a reset link for another organisation's member",
    'production admin can create and use a reset link without a mail provider',
    'an admin removes a member, who is signed out at once',
)
LIVE = os.environ.get("FORGE_STARTER_LIVE") == "1"


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize('starter', ['typescript', 'python', 'earlier adopted'])
def test_4_auth_gives_links_and_locks_without_guessing(repo, gh, tmp_path, tmp_path_factory, starter):
    # Audit: init ships executable auth cases; sync preserves earlier apps. Missing shipped
    # cases or an app rewrite fails here. The live HTTP suite owns runtime assertions;
    # existing init tests do not check this auth delivery contract. No production seam.
    from test_noscreens_starters import _earlier_app
    from test_starter_tree import _require_cases, live_python_run, live_run

    if starter == 'earlier adopted':
        client = _earlier_app(repo, gh, tmp_path)
        assert not (client / 'apps/web/e2e/rules').exists()
        return
    args = ('--starter', 'python') if starter == 'python' else ('--starter',)
    client, initialized = _fresh_client(repo, gh, tmp_path, *args)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    auth_test = 'apps/api/tests/test_auth.py' if starter == 'python' else 'apps/api/test/auth.e2e-spec.ts'
    assert (client / auth_test).is_file()
    if LIVE:
        run = live_python_run if starter == 'python' else live_run
        expected = AUTH_CASES
        if starter == 'python':
            # Python's existing removal case keeps its pytest function name.
            expected = AUTH_CASES[:-1] + ('test_an_admin_removes_a_member_who_is_signed_out_at_once',)
        _require_cases(run(tmp_path_factory)['api'], expected)


def _install_client(client: Path, tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js 24 is required to list the client rule specs")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
    if version.returncode or not version.stdout.strip().startswith("v24."):
        pytest.skip("Node.js 24 is required to list the client rule specs")
    corepack = shutil.which("corepack")
    if not corepack:
        pytest.skip("Corepack is required to list the client rule specs")

    host_config = tmp_path / "client-test-host"
    user_home = host_config / "home"
    user_home.mkdir(parents=True)
    env = os.environ.copy()
    for name in tuple(env):
        if name.lower().startswith(("npm_config_", "pnpm_config_")):
            env.pop(name)
    env.update({
        "HOME": str(user_home),
        "COREPACK_HOME": str(host_config / "corepack"),
        "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
        "PNPM_CONFIG_STORE_DIR": str(host_config / "pnpm-store"),
        "XDG_CONFIG_HOME": str(host_config / "xdg-config"),
    })
    if sys.platform == "win32":
        env["USERPROFILE"] = str(user_home)
    installed = subprocess.run(
        [corepack, "pnpm", "install", "--frozen-lockfile"], cwd=client, env=env,
        capture_output=True, text=True, timeout=1800, shell=sys.platform == "win32",
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    return env, corepack


@pytest.mark.platform
@pytest.mark.parametrize("starter", ["typescript", "python"])
@pytest.mark.timeout(1800)
def test_5_the_rule_specs_ship_off_and_list(repo, gh, tmp_path, starter):
    # Audit: this protects the generated browser-test contract: basic-screen specs ship but stay
    # ignored until the app builds those screens. A removed spec or pending entry breaks this;
    # the starter-tree test owns screen absence but not the rule-spec opt-in path. Live listing
    # uses the client app created by Forge init. This needs no production test seam.
    init_args = ("--starter", "python") if starter == "python" else ("--starter",)
    client, initialized = _fresh_client(repo, gh, tmp_path, *init_args)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    rules = client / "apps/web/e2e/rules"
    for screen in RULE_SCREENS:
        assert (rules / f"{screen}.spec.ts").is_file(), screen

    config = (client / "apps/web/playwright.config.ts").read_text(encoding="utf-8")
    pending = re.search(r"pendingScreens\s*=\s*\[([^\]]*)\]", config)
    assert pending, "Playwright config must name screens whose rule specs are pending"
    assert set(re.findall(r"['\"]([^'\"]+)['\"]", pending.group(1))) == set(RULE_SCREENS)
    assert "testIgnore" in config and "pendingScreens" in config

    if not LIVE:
        return
    env, corepack = _install_client(client, tmp_path)
    generated_config = client / "apps/web/playwright.config.ts"
    original = generated_config.read_text(encoding="utf-8")
    enabled, count = re.subn(
        r"const pendingScreens\s*=\s*\[[^\]]*\]",
        "const pendingScreens: string[] = []",
        original,
    )
    assert count == 1, "Playwright config must expose one pending-screen list"
    generated_config.write_text(enabled, encoding="utf-8")
    try:
        result = subprocess.run(
            [corepack, "pnpm", "exec", "playwright", "test", "--config",
             Path("apps") / "web" / "playwright.config.ts", "--list"],
            cwd=client, env=env, capture_output=True, text=True, timeout=180,
            shell=sys.platform == "win32",
        )
    finally:
        generated_config.write_text(original, encoding="utf-8")
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    expected_titles = {
        title
        for path in rules.glob("*.spec.ts")
        for title in re.findall(r"\btest\(['\"]([^'\"]+)['\"]", path.read_text(encoding="utf-8"))
    }
    assert expected_titles
    for screen in RULE_SCREENS:
        assert f"{screen}.spec.ts" in output, output
    for title in expected_titles:
        assert title in output, (title, output)
