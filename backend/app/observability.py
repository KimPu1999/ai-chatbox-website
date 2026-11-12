"""Optional OpenTelemetry setup with privacy-safe defaults."""

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def instrument_app(app: FastAPI) -> None:
    """Instrument FastAPI when enabled; keep local/test installs dependency-safe."""
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.otel_enabled:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.otel_service_name}),
            sampler=TraceIdRatioBased(settings.otel_sample_ratio),
        )
        if settings.otel_exporter_endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
        else:
            exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,health/ready,api/v1/health",
        )
        logger.info("OpenTelemetry enabled service=%s", settings.otel_service_name)
    except ImportError:
        logger.warning("OTEL_ENABLED is true but OpenTelemetry packages are unavailable")


def safe_generation_attributes(
    model: str, status: str, latency_ms: float
) -> dict[str, str | float]:
    """Return low-cardinality AI telemetry attributes; content and user IDs are excluded."""
    return {
        "ai.model": model[:100],
        "ai.status": status[:32],
        "ai.latency_ms": round(latency_ms, 2),
    }
