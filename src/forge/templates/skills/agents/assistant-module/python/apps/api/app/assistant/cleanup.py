import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Error as PostgresError
from psycopg.conninfo import make_conninfo
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.assistant.models import Chat
from app.core import log_event

RETENTION = timedelta(days=30)
CLEANUP_INTERVAL_SECONDS = 60 * 60


class Cleanup:
    def __init__(
        self, session_factory: sessionmaker[Session], saver: PostgresSaver
    ) -> None:
        self.session_factory = session_factory
        self.saver = saver

    def delete_expired(self, now: datetime) -> int:
        deleted = 0
        with self.session_factory() as db:
            ids = list(
                db.scalars(
                    select(Chat.id).where(Chat.last_message_at_utc <= now - RETENTION)
                )
            )
        for chat_id in ids:
            with self.session_factory.begin() as db:
                # Lock and recheck activity before erasing any checkpoint copy.
                chat = db.scalar(
                    select(Chat)
                    .where(
                        Chat.id == chat_id,
                        Chat.last_message_at_utc <= now - RETENTION,
                    )
                    .with_for_update()
                )
                if chat is not None:
                    self.saver.delete_thread(str(chat.id))
                    db.delete(chat)
                    deleted += 1
        return deleted

    async def run(self, stopped: asyncio.Event, environment: str) -> None:
        while not stopped.is_set():
            try:
                await asyncio.wait_for(stopped.wait(), CLEANUP_INTERVAL_SECONDS)
            except TimeoutError:
                try:
                    await asyncio.to_thread(self.delete_expired, datetime.now(UTC))
                except (SQLAlchemyError, PostgresError):
                    # Keep the timer alive and report failure without chat content.
                    log_event(
                        None,
                        "error",
                        "Assistant chat clean-up failed",
                        "app.assistant",
                        {},
                        environment=environment,
                    )


@asynccontextmanager
async def assistant_lifespan(
    session_factory: sessionmaker[Session],
    database_url: str,
    environment: str = "unknown",
) -> AsyncIterator[PostgresSaver]:
    conninfo = make_conninfo(
        database_url.replace("postgresql+psycopg://", "postgresql://", 1),
        options="-c search_path=assistant,public",
    )
    with PostgresSaver.from_conn_string(conninfo) as saver:
        await asyncio.to_thread(saver.setup)
        cleanup = Cleanup(session_factory, saver)
        await asyncio.to_thread(cleanup.delete_expired, datetime.now(UTC))
        stopped = asyncio.Event()
        timer = asyncio.create_task(cleanup.run(stopped, environment))
        try:
            yield saver
        finally:
            stopped.set()
            await timer
