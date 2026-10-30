import os
import subprocess
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import httpx2
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


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


@asynccontextmanager
async def agent_client(key: str) -> AsyncIterator[ClientSession]:
    """Connect to the running API through the official MCP Streamable HTTP client."""
    async with (
        httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {key}"}, timeout=15
        ) as connection,
        streamable_http_client(
            f"{os.environ['API_TEST_URL'].rstrip('/')}/mcp",
            http_client=connection,
        ) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        yield session


def add_agent_key(
    client: httpx.Client, csrf: str, name: str, role: str
) -> tuple[dict[str, object], str]:
    added = client.post(
        "/api/v1/agents",
        headers={"x-csrf-token": csrf},
        json={"name": name, "role": role},
    )
    assert added.status_code == 201, added.text
    agent = added.json()["data"]
    key_response = client.post(
        f"/api/v1/members/{agent['accountId']}/key",
        headers={"x-csrf-token": csrf},
    )
    assert key_response.status_code == 201, key_response.text
    return agent, key_response.json()["data"]["key"]
