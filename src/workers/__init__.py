"""Workers module for async task processing."""
from src.workers.celery_app import app

__all__ = ["app"]
