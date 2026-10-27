import os
import subprocess
from collections.abc import Iterator

import httpx
import pytest


@pytest.fixture(scope="module", autouse=True)
def isolated_api() -> Iterator[None]:
    # API modules share one source IP. Give each module its own rate-limit
    # window without changing the app's limits or resetting the database.
    def recreate_api() -> None:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "compose.test.yml",
                "up",
                "-d",
                "--no-deps",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "180",
                "api",
            ],
            cwd="../..",
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=210,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    recreate_api()
    try:
        yield
    finally:
        recreate_api()


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=os.environ["API_TEST_URL"], timeout=15) as connection:
        yield connection


@pytest.fixture
def production_client() -> Iterator[httpx.Client]:
    with httpx.Client(
        base_url=os.environ["PRODUCTION_API_TEST_URL"], timeout=15
    ) as connection:
        yield connection
