import os
from collections.abc import Iterator

import httpx
import pytest


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
