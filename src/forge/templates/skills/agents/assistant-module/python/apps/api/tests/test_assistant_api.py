"""Chat create, list and read contracts at the running API boundary."""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from test_api import credentials, sign_up
from test_invites import invite
from app.assistant.schema import (
    Block,
    BlockEvent,
    ChartBlock,
    ChartProps,
    Column,
    ConfirmBlock,
    ConfirmEvent,
    ConfirmProps,
    DetailBlock,
    DetailField,
    DetailProps,
    DoneEvent,
    ErrorEvent,
    LimitEvent,
    Notice,
    Schema,
    StatsBlock,
    StatsProps,
    TableBlock,
    TableProps,
    TextDelta,
    TextEvent,
    Tile,
    StreamEvent,
)
from pydantic import TypeAdapter


def _create_chat(client: httpx.Client, csrf: str, key: str) -> str:
    response = client.post(
        "/api/v1/assistant/chats",
        headers={"x-csrf-token": csrf, "Idempotency-Key": key},
        json={},
    )
    assert response.status_code == 201, response.text
    chat_id = response.json()["data"]["id"]
    assert isinstance(chat_id, str)
    return chat_id


def _joined_member(admin: httpx.Client, admin_csrf: str) -> tuple[httpx.Client, str]:
    account = credentials()
    token = invite(admin, admin_csrf, account["email"])
    member = httpx.Client(base_url=admin.base_url, timeout=15)
    joined = member.post("/api/v1/auth/accept-invite", json={**account, "token": token})
    assert joined.status_code == 201, joined.text
    return member, joined.cookies["starter_csrf"]


def _seed_conversation(chat_id: str, confirm_id: str, expires_at: str) -> None:
    source = f"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Interrupt
from psycopg.conninfo import make_conninfo
from app.core import load_settings

settings = load_settings()
database_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
conninfo = make_conninfo(database_url, options="-c search_path=assistant,public")
with PostgresSaver.from_conn_string(conninfo) as saver:
    saver.setup()
    config = {{"configurable": {{"thread_id": {json.dumps(chat_id)}, "checkpoint_ns": ""}}}}
    checkpoint = {{
        "v": 1,
        "id": {json.dumps(str(uuid4()))},
        "ts": {json.dumps(datetime.now(UTC).isoformat())},
        "channel_values": {{"messages": [
            HumanMessage(content="Can you check the project status?"),
            AIMessage(content="The project is active."),
            SystemMessage(content="system-only instruction"),
            ToolMessage(content="private tool result", tool_call_id="assistant-test-tool"),
        ]}},
        "channel_versions": {{"messages": "1"}},
        "versions_seen": {{}},
        "pending_sends": [],
    }}
    saved = saver.put(
        config, checkpoint, {{"source": "input", "step": -1, "parents": {{}}}},
        {{"messages": "1"}},
    )
    saver.put_writes(saved, [("__interrupt__", [Interrupt(
        id={json.dumps(confirm_id)},
        value={{
            "title": "Change project status",
            "lines": ["Set project status to archived"],
            "expiresAt": {json.dumps(expires_at)},
        }},
    )])], "assistant-api-test")
"""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.test.yml",
            "exec",
            "-T",
            "api",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-",
        ],
        cwd="../..",
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_person_lists_only_their_own_chats(client: httpx.Client) -> None:
    # Audit: the running API and Postgres own chat creation, paging, and privacy. Existing
    # starter tests do not cover assistant chats. HTTP-created accounts and invitations prove
    # a same-organisation member boundary; no test-only production seam is needed.
    _, admin_csrf = sign_up(client)
    person, person_csrf = _joined_member(client, admin_csrf)
    other_person, other_csrf = _joined_member(client, admin_csrf)
    try:
        key = str(uuid4())
        first_chat = _create_chat(person, person_csrf, key)
        assert _create_chat(person, person_csrf, key) == first_chat
        empty = person.get(f"/api/v1/assistant/chats/{first_chat}")
        assert empty.status_code == 200, empty.text
        assert empty.json()["data"]["messages"] == []
        assert empty.json()["data"]["confirm"] is None
        second_chat = _create_chat(person, person_csrf, str(uuid4()))
        other_chat = _create_chat(other_person, other_csrf, str(uuid4()))

        first = person.get("/api/v1/assistant/chats", params={"limit": 1})
        assert first.status_code == 200, first.text
        first_data = first.json()["data"]
        first_items = first_data["items"]
        assert len(first_items) == 1
        assert first_data["paging"]["limit"] == 1
        assert first_data["paging"]["total"] == 2
        assert first_data["paging"]["totalCapped"] is False
        first_id = first_items[0]["id"]
        assert first_id == second_chat
        next_cursor = first_data["paging"]["nextCursor"]
        assert isinstance(next_cursor, str)

        second = person.get(
            "/api/v1/assistant/chats", params={"limit": 1, "after": next_cursor}
        )
        assert second.status_code == 200, second.text
        second_data = second.json()["data"]
        second_items = second_data["items"]
        assert len(second_items) == 1
        second_id = second_items[0]["id"]
        assert second_id == first_chat
        assert other_chat not in {first_id, second_id}
        previous_cursor = second_data["paging"]["previousCursor"]
        assert isinstance(previous_cursor, str)
        previous = person.get(
            "/api/v1/assistant/chats",
            params={"limit": 1, "before": previous_cursor},
        )
        assert previous.status_code == 200, previous.text
        assert previous.json()["data"]["items"][0]["id"] == first_id

        invalid_body = person.post(
            "/api/v1/assistant/chats",
            headers={"x-csrf-token": person_csrf, "Idempotency-Key": str(uuid4())},
            json={"unexpected": True},
        )
        assert invalid_body.status_code == 400, invalid_body.text
        assert invalid_body.json()["error"]["code"] == "VALIDATION_ERROR"
        invalid_cursor = person.get(
            "/api/v1/assistant/chats", params={"after": "not-a-cursor"}
        )
        assert invalid_cursor.status_code == 400, invalid_cursor.text
        assert invalid_cursor.json()["error"]["code"] == "VALIDATION_ERROR"
        unknown_query = person.get(
            "/api/v1/assistant/chats", params={"unexpected": "true"}
        )
        assert unknown_query.status_code == 400, unknown_query.text
        assert unknown_query.json()["error"]["code"] == "VALIDATION_ERROR"

        no_csrf = person.post(
            "/api/v1/assistant/chats",
            headers={"Idempotency-Key": str(uuid4())},
            json={},
        )
        assert no_csrf.status_code == 403, no_csrf.text
        bad_csrf = person.post(
            "/api/v1/assistant/chats",
            headers={
                "x-csrf-token": person_csrf + "wrong",
                "Idempotency-Key": str(uuid4()),
            },
            json={},
        )
        assert bad_csrf.status_code == 403, bad_csrf.text
        assert bad_csrf.json()["error"]["code"] == "CSRF_CHECK_FAILED"
    finally:
        person.close()
        other_person.close()

    with httpx.Client(base_url=client.base_url, timeout=15) as anonymous:
        response = anonymous.get("/api/v1/assistant/chats")
        assert response.status_code == 401, response.text
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_a_person_reads_messages_and_a_pending_confirmation(
    client: httpx.Client,
) -> None:
    # Audit: the real HTTP route must read the user's checkpoint and expose only chat messages
    # and its pending confirmation. No other API test covers this response or owns a test seam.
    _, csrf = sign_up(client)
    chat_id = _create_chat(client, csrf, str(uuid4()))
    confirm_id = str(uuid4())
    expires_at = (datetime.now(UTC) + timedelta(minutes=15)).isoformat()
    _seed_conversation(chat_id, confirm_id, expires_at)

    response = client.get(f"/api/v1/assistant/chats/{chat_id}")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["id"] == chat_id
    assert data["messages"] == [
        {"role": "user", "text": "Can you check the project status?"},
        {"role": "assistant", "text": "The project is active."},
    ]
    assert data["confirm"]["confirmId"] == confirm_id
    assert data["confirm"]["title"] == "Change project status"
    assert data["confirm"]["lines"] == ["Set project status to archived"]
    assert datetime.fromisoformat(
        data["confirm"]["expiresAt"].replace("Z", "+00:00")
    ) == (datetime.fromisoformat(expires_at))
    assert "system-only instruction" not in response.text
    assert "private tool result" not in response.text


def test_another_person_and_an_admin_get_404_for_a_chat(client: httpx.Client) -> None:
    # Audit: same-organisation membership and admin role must not grant access to a chat.
    # Existing tests cover project and history scopes, not assistant checkpoint reads.
    _, admin_csrf = sign_up(client)
    person, person_csrf = _joined_member(client, admin_csrf)
    other_person, _ = _joined_member(client, admin_csrf)
    try:
        chat_id = _create_chat(person, person_csrf, str(uuid4()))
        for reader in (other_person, client):
            response = reader.get(f"/api/v1/assistant/chats/{chat_id}")
            assert response.status_code == 404, response.text
            assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        person.close()
        other_person.close()


def test_python_stream_events_match_the_typescript_contracts() -> None:
    # Audit: the Python models and browser Zod schemas are independent contract owners. This
    # catches alias or field drift that Python-only response checks cannot detect.
    confirm = ConfirmProps(
        confirm_id=str(uuid4()),
        title="Change project status",
        lines=["Set project status to archived"],
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    column = Column(key="count", label="Count")
    blocks: list[Block] = [
        TableBlock(props=TableProps(columns=[column], rows=[{"count": 2}], total=2)),
        TableBlock(
            props=TableProps(columns=[column], rows=[{"count": None}], total=None)
        ),
        ChartBlock(
            props=ChartProps(
                type="bar",
                x_key="month",
                series=[column],
                rows=[{"month": "Nov", "count": 2}],
            )
        ),
        StatsBlock(props=StatsProps(tiles=[Tile(label="Total", value=2)])),
        DetailBlock(
            props=DetailProps(
                title="Project",
                fields=[
                    DetailField(label="Name", value="Renovation"),
                    DetailField(label="Due date", value=None),
                ],
            )
        ),
        ConfirmBlock(props=confirm),
    ]
    events: list[StreamEvent] = [
        TextEvent(data=TextDelta(delta="The project is active.")),
        *(BlockEvent(data=block) for block in blocks),
        ConfirmEvent(data=confirm),
        LimitEvent(data=Notice(message="The assistant spend limit has been reached.")),
        ErrorEvent(data=Notice(message="Start a new chat and try again.")),
        DoneEvent(data=Schema()),
    ]
    payload = [
        json.loads(
            TypeAdapter(StreamEvent).dump_json(event, by_alias=True).decode("utf-8")
        )
        for event in events
    ]
    source = """
import { readFileSync } from 'node:fs';
import { streamEventSchema } from './libs/assistant/contracts/dist/index.js';
for (const event of JSON.parse(readFileSync(0, 'utf8'))) {
  streamEventSchema.parse(event);
}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd="../..",
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
