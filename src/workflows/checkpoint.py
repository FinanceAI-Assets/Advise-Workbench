"""Where the LangGraph orchestrator keeps run checkpoints."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.workflows.config import checkpoint_store

_LOCK = threading.Lock()
_SAVER: Any = None

# Application types the coordinator keeps in the run state. LangGraph only restores types it has been
# told about; others log a warning today and will be refused by later versions, which would break
# resuming a run after a restart. Add a type here when a restart log names a new one.
CHECKPOINT_TYPES: tuple[tuple[str, str], ...] = (
    ("src.deliverables.branding_service", "BrandingLevel"),
    ("src.deliverables.branding_service", "ColorPalette"),
    ("src.deliverables.branding_service", "BrandingContext"),
    ("src.agents.content_enrichment", "UserIntent"),
    ("src.agents.content_enrichment", "ProcessAnalytics"),
    ("src.agents.content_enrichment", "RiskProfile"),
    ("src.agents.content_enrichment", "ContentEnrichment"),
    ("src.deliverables.deliverable", "DeliverableMetadata"),
)


def checkpoint_serde() -> Any:
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)


def checkpoint_path() -> Path:
    return Path(settings.workspace_root) / ".checkpoints" / "run_graph.sqlite"


def get_checkpointer() -> Any:
    """One shared checkpoint saver per process (run worker threads share it)."""
    global _SAVER
    with _LOCK:
        if _SAVER is not None:
            return _SAVER
        if checkpoint_store() == "postgres":
            from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            if not settings.database_url.startswith("postgresql"):
                raise ValueError("RUN_CHECKPOINT_STORE=postgres needs a PostgreSQL DATABASE_URL")
            url = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
            # A small pool: run worker threads checkpoint at the same time.
            pool = ConnectionPool(url, min_size=1, max_size=5, kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
            saver = PostgresSaver(pool, serde=checkpoint_serde())
            saver.setup()
        else:
            from langgraph.checkpoint.sqlite import SqliteSaver

            path = checkpoint_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            saver = SqliteSaver(sqlite3.connect(str(path), check_same_thread=False), serde=checkpoint_serde())
            saver.setup()
        _SAVER = saver
        return _SAVER


def reset_checkpointer() -> None:
    """Forget the shared saver (tests point the workspace somewhere else)."""
    global _SAVER
    with _LOCK:
        _SAVER = None
