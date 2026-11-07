"""Tests must not read the repo-root .env, which names shared databases and services."""

from src.app import main  # noqa: F401  # importing the app is what used to reload .env
from src.core.config import Settings, settings
from src.core.db.session import engine


def test_app_uses_in_memory_sqlite() -> None:
    assert engine.url.get_backend_name() == "sqlite"
    assert engine.url.database == ":memory:"
    assert settings.database_url == "sqlite:///:memory:"


def test_settings_do_not_read_a_dotenv_file() -> None:
    assert not Settings.model_config.get("env_file")
