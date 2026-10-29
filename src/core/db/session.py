from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.config import settings
from src.core.db.base import Base

DATABASE_URL = settings.database_url

if DATABASE_URL.startswith("sqlite"):
    # SQLite can briefly lock on concurrent writes (API + background workers).
    # Increase busy timeout so transient contention does not fail requests.
    _sqlite_args = {"check_same_thread": False, "timeout": 30}
    if ":memory:" in DATABASE_URL:
        engine = create_engine(
            DATABASE_URL,
            future=True,
            connect_args=_sqlite_args,
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(DATABASE_URL, future=True, connect_args=_sqlite_args)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        # Improve concurrent read/write behavior for local-dev SQLite.
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
        finally:
            cursor.close()
else:
    engine = create_engine(
        DATABASE_URL,
        future=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=settings.database_pool_pre_ping,
        pool_recycle=settings.database_pool_recycle,
        pool_timeout=settings.database_pool_timeout,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
_initialized = False


def init_db() -> None:
    global _initialized
    from src.core.db import models as _models  # noqa: F401 — register ORM tables on Base.metadata

    if engine.dialect.name == "postgresql":
        # Several API and worker processes start together; without a lock they race to create
        # the same tables and one fails with a duplicate-key error on pg_type.
        with engine.begin() as conn:
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(815001)")
            Base.metadata.create_all(bind=conn)
    else:
        Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        rebuild_sqlite_run_tasks_key(engine)
    _initialized = True


def rebuild_sqlite_run_tasks_key(bind) -> bool:
    """Rebuild ``run_tasks`` when it still has the old single-column key. Returns True if it was rebuilt.

    Older databases keyed the table on ``id`` alone, so every run after the first failed to save its
    checklist ("UNIQUE constraint failed: run_tasks.id"). SQLite cannot alter a primary key in place.
    """
    from src.core.db.models import RunTask

    with bind.begin() as conn:
        info = conn.exec_driver_sql("PRAGMA table_info(run_tasks)").fetchall()
        if not info or {row[1] for row in info if row[5]} != {"id"}:
            return False
        conn.exec_driver_sql("ALTER TABLE run_tasks RENAME TO run_tasks_legacy")
        for index in conn.exec_driver_sql("PRAGMA index_list(run_tasks_legacy)").fetchall():
            if index[3] == "c":  # created with CREATE INDEX; names are global in SQLite, so free them
                conn.exec_driver_sql(f'DROP INDEX "{index[1]}"')
        RunTask.__table__.create(conn)
        shared = [c.name for c in RunTask.__table__.columns if c.name in {row[1] for row in info}]
        cols = ", ".join(f'"{c}"' for c in shared)
        conn.exec_driver_sql(f"INSERT INTO run_tasks ({cols}) SELECT {cols} FROM run_tasks_legacy")
        conn.exec_driver_sql("DROP TABLE run_tasks_legacy")
    return True


def get_db() -> Generator[Session, None, None]:
    if not _initialized:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Multi-step unit of work with explicit commit/rollback (use outside FastAPI Depends)."""
    if not _initialized:
        init_db()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
