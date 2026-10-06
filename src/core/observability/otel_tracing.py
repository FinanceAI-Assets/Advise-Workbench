"""OpenTelemetry bootstrap: traces, metrics and logs, sent to OpenObserve when it is enabled.

Two ways to switch it on (both off by default):

- ``OPENOBSERVE_ENABLED=true``: traces, metrics and logs go to OpenObserve over OTLP/HTTP
  (see docs/06-deployment-operations/observability.md).
- ``OTEL_SDK_ENABLED=true``: traces only, to ``OTEL_EXPORTER_OTLP_ENDPOINT`` or the console.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from src.core.config import settings
from src.core.observability import metrics as app_metrics

_log = logging.getLogger("advise_workbench.otel")
_initialized = False
_providers: list[Any] = []


def openobserve_enabled() -> bool:
    return bool(getattr(settings, "openobserve_enabled", False))


def _enabled() -> bool:
    return openobserve_enabled() or bool(getattr(settings, "otel_sdk_enabled", False))


def _openobserve_target() -> tuple[str, dict[str, str]]:
    """Base OTLP address and request headers for the configured OpenObserve organisation."""
    base = f"{str(settings.openobserve_url).rstrip('/')}/api/{settings.openobserve_org}"
    token = base64.b64encode(f"{settings.openobserve_user}:{settings.openobserve_password}".encode()).decode("ascii")
    return base, {"Authorization": f"Basic {token}", "stream-name": settings.openobserve_stream}


def init_otel_if_enabled() -> None:
    """No-op unless OpenObserve or the OTel SDK is switched on and the packages are installed."""
    global _initialized
    if not _enabled() or _initialized:
        return
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError:
        _log.warning("telemetry is enabled but opentelemetry-sdk is not installed; skipping OTel init")
        return

    service_name = str(getattr(settings, "otel_service_name", "") or "advise-workbench-backend")
    resource = Resource.create({"service.name": service_name, "deployment.environment": settings.advise_workbench_env})
    provider = TracerProvider(resource=resource)

    exporter: Any = None
    if openobserve_enabled():
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,  # type: ignore[import-not-found]
        )

        base, headers = _openobserve_target()
        exporter = OTLPSpanExporter(endpoint=f"{base}/v1/traces", headers=headers)
        _init_openobserve_metrics_and_logs(resource, base, headers)
        _log.info("OpenObserve telemetry configured: %s (stream %s)", base, settings.openobserve_stream)
    else:
        endpoint = str(getattr(settings, "otel_exporter_otlp_endpoint", "") or "").strip()
        if endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint)
                _log.info("OpenTelemetry OTLP exporter configured: %s", endpoint)
            except ImportError:
                _log.warning("OTLP endpoint set but opentelemetry-exporter-otlp is not installed")
    if exporter is None:
        exporter = ConsoleSpanExporter()
        _log.info("OpenTelemetry using ConsoleSpanExporter")

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _providers.append(provider)
    _initialized = True
    _log.info("OpenTelemetry TracerProvider initialized")


def _init_openobserve_metrics_and_logs(resource: Any, base: str, headers: dict[str, str]) -> None:
    from opentelemetry import metrics  # type: ignore[import-not-found]
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter  # type: ignore[import-not-found]
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,  # type: ignore[import-not-found]
    )
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler  # type: ignore[import-not-found]
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor  # type: ignore[import-not-found]
    from opentelemetry.sdk.metrics import MeterProvider  # type: ignore[import-not-found]
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader  # type: ignore[import-not-found]

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{base}/v1/metrics", headers=headers),
        export_interval_millis=max(1, int(settings.openobserve_metrics_interval_sec)) * 1000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)
    app_metrics.set_otel_meter(meter_provider.get_meter("advise_workbench"))

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{base}/v1/logs", headers=headers)))
    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)
    # The exporters' own HTTP client logs every request; sending those back would never end.
    for noisy in ("urllib3", "opentelemetry"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _providers.extend([meter_provider, logger_provider])


def flush_telemetry() -> None:
    """Send what is still buffered (called at shutdown and by the smoke script)."""
    for provider in _providers:
        try:
            provider.force_flush()
        except Exception as exc:  # noqa: BLE001 — telemetry must never break the app
            _log.warning("telemetry flush failed: %s", exc)


def get_tracer(name: str = "advise_workbench"):
    """Return an OTel tracer, or a no-op stand-in when OTel is disabled."""
    if not _enabled():
        return _NoopTracer()
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]

        return trace.get_tracer(name)
    except Exception:
        return _NoopTracer()


@contextmanager
def start_span(name: str, *, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
    """Context manager for a span; no-op when OTel is disabled."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes and hasattr(span, "set_attribute"):
            for k, v in attributes.items():
                try:
                    span.set_attribute(k, v)
                except Exception:  # noqa: S110 — attribute types vary by OTel backend
                    pass
        yield span


def current_span() -> Any:
    """The span that is open in this thread, or a no-op stand-in."""
    if not _enabled():
        return _NoopSpan()
    from opentelemetry import trace  # type: ignore[import-not-found]

    return trace.get_current_span()


def with_trace_context(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap ``fn`` so that, run in another thread, its spans stay in the caller's trace."""
    if not _enabled():
        return fn
    from opentelemetry import context  # type: ignore[import-not-found]

    parent = context.get_current()

    def run(*args: Any, **kwargs: Any) -> Any:
        token = context.attach(parent)
        try:
            return fn(*args, **kwargs)
        finally:
            context.detach(token)

    return run


class _NoopSpan:
    def set_attribute(self, *_a: Any, **_k: Any) -> None:
        return None

    def __enter__(self) -> "_NoopSpan":
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None


class _NoopTracer:
    def start_as_current_span(self, name: str, **_kwargs: Any) -> _NoopSpan:
        return _NoopSpan()
