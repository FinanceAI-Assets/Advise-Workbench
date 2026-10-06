"""run_tasks is keyed on (id, run_id): the fixed checklist ids repeat in every run."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.core.db.models import Base, RunTask
from src.core.db.session import rebuild_sqlite_run_tasks_key
from src.workflows.run_tasks import sync_run_tasks_from_snapshot

TODOS = [
    {"id": "context", "label": "Assemble context & memory", "status": "done"},
    {"id": "plan", "label": "Plan output order", "status": "done"},
    {"id": "qa", "label": "Quality review loop", "status": "pending"},
]


def test_two_runs_can_save_the_same_checklist_ids(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'tasks.db'}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        sync_run_tasks_from_snapshot(session, project_id="p_1", run_id="run_a", todos=TODOS)
        session.commit()
        sync_run_tasks_from_snapshot(session, project_id="p_1", run_id="run_b", todos=TODOS)
        session.commit()
        rows = session.scalars(select(RunTask).order_by(RunTask.run_id, RunTask.id)).all()
    assert [(r.run_id, r.id) for r in rows] == [
        ("run_a", "context"), ("run_a", "plan"), ("run_a", "qa"),
        ("run_b", "context"), ("run_b", "plan"), ("run_b", "qa"),
    ]


def test_old_single_column_key_is_rebuilt_and_rows_are_kept(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}", future=True)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # recreate the table the way older databases have it
        conn.exec_driver_sql("DROP TABLE run_tasks")
        conn.exec_driver_sql(
            "CREATE TABLE run_tasks (id VARCHAR(64) NOT NULL PRIMARY KEY, run_id VARCHAR(64) NOT NULL, "
            "project_id VARCHAR(64) NOT NULL, title TEXT NOT NULL, description TEXT, phase VARCHAR(16) NOT NULL, "
            "status VARCHAR(16) NOT NULL, started_at DATETIME, completed_at DATETIME, duration_ms INTEGER, "
            "depends_on_json TEXT NOT NULL, swarm_team_id VARCHAR(64), assigned_teammate_id VARCHAR(64), "
            "priority INTEGER NOT NULL, skills_used_json TEXT NOT NULL, tools_invoked_json TEXT NOT NULL, "
            "output_json TEXT NOT NULL, blocked_reason TEXT, requires_approval BOOLEAN NOT NULL, "
            "retry_count INTEGER NOT NULL, estimated_duration_sec INTEGER, created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
        conn.exec_driver_sql("CREATE INDEX ix_run_tasks_run_status ON run_tasks (run_id, status)")
        conn.exec_driver_sql(
            "INSERT INTO run_tasks (id, run_id, project_id, title, phase, status, depends_on_json, priority, "
            "skills_used_json, tools_invoked_json, output_json, requires_approval, retry_count, created_at, updated_at) "
            "VALUES ('context', 'run_old', 'p_1', 'Assemble context', 'observe', 'completed', '[]', 0, '[]', '[]', '{}', 0, 0, "
            "'2026-10-05 00:00:00', '2026-10-05 00:00:00')"
        )

    assert rebuild_sqlite_run_tasks_key(engine) is True
    assert rebuild_sqlite_run_tasks_key(engine) is False  # already upgraded: nothing to do

    with Session(engine) as session:
        sync_run_tasks_from_snapshot(session, project_id="p_1", run_id="run_new", todos=TODOS)
        session.commit()
        ids = sorted((r.run_id, r.id) for r in session.scalars(select(RunTask)).all())
    assert ("run_old", "context") in ids and ("run_new", "context") in ids
