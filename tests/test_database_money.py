"""New apps receive exact money; sync preserves an adopted app's cents helper."""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client
from test_starter_tree import LIVE, STARTER, _junit_cases, _require_cases, live_run

pytest_plugins = ("test_python_starter",)
STORY = "FORGE-DATABASE-1"
CURRENCY_GUIDANCE = (
    "Ask for the app's currency at setup (default INR) and write its code to DEFAULT_CURRENCY in "
    "libs/shared/util/src/format.ts and, in a Python app, apps/api/app/core/config.py."
)


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("kind", ("react", "python"))
def test_4_money_is_an_exact_decimal_with_its_currency(
    repo, gh, tmp_path, tmp_path_factory, request, kind,
):
    # Audit: init owns helper/test delivery, defaults and setup guidance.
    # Missing copies or defaults break new apps; sync must preserve old cents code.
    # Existing tests own dates, not this currency or precision contract.
    # Live runs exercise pure-logic cases; real init/sync need no production test seam.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", kind)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    relative = "libs/shared/util/src"
    for name in ("format.ts", "format.test.ts"):
        assert (client / relative / name).read_bytes() == (STARTER / relative / name).read_bytes()
    assert "DEFAULT_CURRENCY = 'INR'" in (client / relative / "format.ts").read_text("utf-8")
    assert "DEFAULT_CURRENCY" in (client / relative / "index.ts").read_text("utf-8")
    if kind == "python":
        core = client / "apps/api/app/core"
        assert 'DEFAULT_CURRENCY = "INR"' in (core / "config.py").read_text("utf-8")
        assert "DEFAULT_CURRENCY" in (core / "__init__.py").read_text("utf-8")
    for host in (".codex", ".claude"):
        assert CURRENCY_GUIDANCE in (client / host / "skills/forge/SKILL.md").read_text("utf-8")
    readme = (STARTER / "README.md").read_text("utf-8")
    assert "numeric(19,4)" in readme
    assert "currency code column" in readme

    if LIVE:
        live = request.getfixturevalue("live_python_starter") if kind == "python" else live_run(tmp_path_factory)
        _require_cases(_junit_cases(live["folder"] / "test-results/formats.xml"), (
            "formats exact decimal money with each currency's own fraction digits",
            "refuses malformed money and currency codes",
        ))

    # One adopted case: sync follows the same path for either starter.
    if kind == "react":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        helper = repo.path / "libs/shared/src/format.ts"
        helper.parent.mkdir(parents=True, exist_ok=True)
        cents = "export const formatMoney = (cents: number) => `USD ${(cents / 100).toFixed(2)}`;\n"
        helper.write_text(cents, encoding="utf-8")
        before = helper.read_bytes()
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', f'"{version}"'), encoding="utf-8")
        repo.git("checkout", "-b", "fix/money-guidance")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert helper.read_bytes() == before
