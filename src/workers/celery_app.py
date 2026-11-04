"""Celery application for the document ingestion pipeline."""

import logging
import ssl
import sys

from celery import Celery
from celery.signals import after_setup_logger, worker_init, worker_ready

from src.core.config import settings

INGESTION_QUEUE = "document_ingestion"

app = Celery(
    main="advise_workbench",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.workers.pipeline",
        "src.workers.library_tasks",
        "src.workers.document_intake_tasks",
        "src.workers.document_parsing_tasks",
        "src.workers.document_embedding_tasks",
        "src.workers.document_knowledge_tasks",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={"src.workers.*": {"queue": INGESTION_QUEUE}},
    task_default_queue=INGESTION_QUEUE,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    # Wait for the broker to confirm every publish (each stage queues the next): a send over a dropped connection
    # then raises and is retried, instead of being lost and leaving the job stuck at its last stage.
    broker_transport_options={"confirm_publish": True, "confirm_timeout": 30},
)

# TLS links (amqps:// broker, rediss:// results) to the shared services are verified against SSL_CA_FILE.
_tls = {"cert_reqs": ssl.CERT_REQUIRED, **({"ca_certs": settings.ssl_ca_file} if settings.ssl_ca_file else {})}
if settings.celery_broker_url.startswith("amqps://"):
    app.conf.broker_use_ssl = _tls
if settings.celery_result_backend.startswith("rediss://"):
    app.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED, **(
        {"ssl_ca_certs": settings.ssl_ca_file} if settings.ssl_ca_file else {})}


@after_setup_logger.connect
def _quiet_http_clients(**_kwargs) -> None:
    # Keep the worker console to the pipeline's stage lines ([S3], [PARSE], [CHUNK], [EMBED], [PIPELINE]): the S3,
    # Qdrant and embedding clients would otherwise log every HTTP request.
    for name in ("httpx", "httpcore", "botocore", "boto3", "urllib3", "s3transfer"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # Status lines printed with emoji must not fail a task when the log file cannot encode them (Windows cp1252).
    for stream in {sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__} - {None}:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")


@worker_ready.connect
def _log_ready(**_kwargs) -> None:
    from src.core.config import log_document_pipeline_config

    log_document_pipeline_config("worker")
    logging.getLogger("advise_workbench.worker").info(
        "[WORKER] ready: consuming queue %s; each upload logs [S3] -> [PARSE] -> [CHUNK] -> [EMBED] -> [PIPELINE]",
        INGESTION_QUEUE,
    )


@worker_init.connect
def _start_telemetry(**_kwargs) -> None:
    # Same OpenObserve traces/logs/metrics as the backend (no-op when OPENOBSERVE_ENABLED is false).
    from src.core.observability.otel_tracing import init_otel_if_enabled

    init_otel_if_enabled()


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
