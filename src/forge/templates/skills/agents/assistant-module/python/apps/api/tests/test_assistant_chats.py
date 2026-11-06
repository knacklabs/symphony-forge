"""Chat retention uses the real Postgres checkpointer and public storage service."""

import json
import subprocess
from typing import cast
from uuid import uuid4

import httpx
from test_api import sign_up

# Audit: the public clean-up service and real Postgres own chat retention.
# A wrong cutoff, a missing vendor erase or stale activity breaks these cases.
# No existing test owns optional chats. The fixed time is the specified public
# method argument, with no test-only production setting or fake datastore.


def _retention(
    client: httpx.Client, age_days: int, *, touch: bool = False
) -> dict[str, object]:
    account, _ = sign_up(client)
    source = f'''
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import app.auth  # noqa: F401
import app.organisations  # noqa: F401
from app.assistant import Chat, ChatService, Cleanup
from app.core import AccountPrincipal, create_database, load_settings
from app.organisations.models import Membership
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import make_conninfo
from sqlalchemy import delete, select, text

settings = load_settings()
engine, session_factory = create_database(settings.database_url)
database_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
conninfo = make_conninfo(database_url, options="-c search_path=assistant,public")
try:
    with PostgresSaver.from_conn_string(conninfo) as saver:
        saver.setup()
        now = datetime.now(UTC)
        last_message = now - timedelta(days={age_days})
        chat_id = None
        payload = None
        try:
            with session_factory() as db:
                membership = db.scalar(
                    select(Membership).where(Membership.email == {json.dumps(account["email"])})
                )
                assert membership is not None
                principal = AccountPrincipal(
                    membership.account_id,
                    membership.email,
                    membership.organisation_id,
                    membership.role,
                )
                chat = ChatService(db).create(principal, last_message)
                chat_id = chat.id

            thread_id = str(chat_id)
            config = {{"configurable": {{"thread_id": thread_id, "checkpoint_ns": ""}}}}
            checkpoint = {{
                "v": 1,
                "id": str(UUID("{uuid4()}")),
                "ts": last_message.isoformat(),
                "channel_values": {{"messages": [{{"role": "user", "content": "private conversation"}}]}},
                "channel_versions": {{"messages": "1"}},
                "versions_seen": {{}},
                "pending_sends": [],
            }}
            saved = saver.put(
                config,
                checkpoint,
                {{"source": "input", "step": -1, "parents": {{}}}},
                {{"messages": "1"}},
            )
            saver.put_writes(saved, [("pending", "private write")], "task")
            assert saver.get_tuple(config) is not None
            # Primitive channels live inline in checkpoints. A message list must
            # create a blob, or the zero-row check after expiry proves nothing.
            with session_factory() as db:
                blobs = db.execute(
                    text("SELECT count(*) FROM assistant.checkpoint_blobs WHERE thread_id = :id"),
                    {{"id": thread_id}},
                ).scalar_one()
                assert blobs > 0
            if {touch!r}:
                with session_factory() as db:
                    ChatService(db).touch(principal, chat_id, now)

            deleted = Cleanup(session_factory, saver).delete_expired(now)
            with session_factory() as db:
                exists = db.get(Chat, chat_id) is not None
                rows = db.execute(
                    text(
                        "SELECT (SELECT count(*) FROM assistant.checkpoints WHERE thread_id = :id) "
                        "+ (SELECT count(*) FROM assistant.checkpoint_blobs WHERE thread_id = :id) "
                        "+ (SELECT count(*) FROM assistant.checkpoint_writes WHERE thread_id = :id)"
                    ),
                    {{"id": thread_id}},
                ).scalar_one()
            payload = {{
                "deleted": deleted,
                "exists": exists,
                "checkpoint": saver.get_tuple(config) is not None,
                "checkpoint_rows": int(rows),
            }}
        finally:
            if chat_id is not None:
                saver.delete_thread(str(chat_id))
                with session_factory.begin() as db:
                    db.execute(delete(Chat).where(Chat.id == chat_id))
        print(json.dumps(payload))
finally:
    engine.dispose()
'''
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
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"The assistant storage call failed: {output}"
    return cast(dict[str, object], json.loads(result.stdout))


def test_a_chat_31_days_after_its_last_message_is_deleted_with_its_checkpoints(
    client: httpx.Client,
) -> None:
    result = _retention(client, 31)
    assert result == {
        "deleted": 1,
        "exists": False,
        "checkpoint": False,
        "checkpoint_rows": 0,
    }


def test_a_chat_29_days_after_its_last_message_stays(client: httpx.Client) -> None:
    result = _retention(client, 29)
    assert result["deleted"] == 0
    assert result["exists"] is True
    assert result["checkpoint"] is True
    rows = result["checkpoint_rows"]
    assert isinstance(rows, int) and rows > 0


def test_a_new_message_moves_the_30_days(client: httpx.Client) -> None:
    result = _retention(client, 31, touch=True)
    assert result["deleted"] == 0
    assert result["exists"] is True
    assert result["checkpoint"] is True
    rows = result["checkpoint_rows"]
    assert isinstance(rows, int) and rows > 0
