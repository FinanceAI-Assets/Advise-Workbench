"""Tests for Celery app instantiation and configuration."""
import pytest
from src.workers.celery_app import app, debug_task

def test_celery_app_created():
    assert app is not None
    assert app.main == "advise_workbench"

def test_celery_app_broker():
    assert app.conf.get("broker_url") is not None

def test_celery_app_backend():
    assert app.conf.get("result_backend") is not None

def test_celery_serialization():
    assert app.conf.get("task_serializer") == "json"
    assert app.conf.get("result_serializer") == "json"

def test_celery_timezone():
    assert app.conf.get("timezone") == "UTC"

def test_debug_task():
    assert debug_task is not None
