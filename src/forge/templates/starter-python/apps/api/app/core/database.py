from collections.abc import Generator
from typing import cast

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_database(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(database_url, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Generator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session
