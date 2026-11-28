"""Engine and session setup. Portable SQLAlchemy 2.x; SQLite now, PostgreSQL later."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_db_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, object] = {}
    if url.get_backend_name() == "sqlite":
        # FastAPI may serve a request on a different thread than the one that
        # opened the pooled connection.
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Create the SQLite parent directory if needed, then all tables.

    ``create_all`` is the hackathon migration path; Alembic is the documented path
    for PostgreSQL (docs/DATABASE_DESIGN.md).
    """
    import backend.app.models  # noqa: F401  (registers tables on Base.metadata)

    url = engine.url
    if url.get_backend_name() == "sqlite" and url.database not in (
        None,
        "",
        ":memory:",
    ):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
