"""Keep every test away from the databases and services named in a developer's `.env`.

This runs before any test module imports the app. Tests that really need a service or key (`live_llm`) take it
from the shell environment. Collection aborts if the app's engine is not SQLite, whatever caused it.
"""

import os

import pytest

os.environ["ADVISE_WORKBENCH_IGNORE_DOTENV"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# Workstream A: disable exact token counting in tests (no API calls)
os.environ["MEMORY_TOKEN_COUNT_EXACT"] = "0"


def pytest_collection_finish(session: pytest.Session) -> None:
    from src.core.db.session import engine

    backend = engine.url.get_backend_name()
    if backend != "sqlite":
        pytest.exit(f"Refusing to run tests: the app's database is {backend}, not the test SQLite.", returncode=2)
