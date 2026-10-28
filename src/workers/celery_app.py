"""Celery application for the document ingestion pipeline."""

import ssl

from celery import Celery
from celery.signals import worker_init

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
)

# TLS links (amqps:// broker, rediss:// results) to the shared services are verified against SSL_CA_FILE.
_tls = {"cert_reqs": ssl.CERT_REQUIRED, **({"ca_certs": settings.ssl_ca_file} if settings.ssl_ca_file else {})}
if settings.celery_broker_url.startswith("amqps://"):
    app.conf.broker_use_ssl = _tls
if settings.celery_result_backend.startswith("rediss://"):
    app.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED, **(
        {"ssl_ca_certs": settings.ssl_ca_file} if settings.ssl_ca_file else {})}


@worker_init.connect
def _start_telemetry(**_kwargs) -> None:
    # Same OpenObserve traces/logs/metrics as the backend (no-op when OPENOBSERVE_ENABLED is false).
    from src.core.observability.otel_tracing import init_otel_if_enabled

    init_otel_if_enabled()


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
