import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_JAEGER_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318/v1/traces")
_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "rag-api")
_IS_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes")

_tracing_setup = False


def _ensure_provider():
    global _tracing_setup
    if _tracing_setup or _IS_TESTING:
        return
    resource = Resource(attributes={SERVICE_NAME: _SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=_JAEGER_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracing_setup = True


def init_tracing():
    _ensure_provider()


def init_celery_tracing():
    _ensure_provider()
    CeleryInstrumentor().instrument()


def instrument_fastapi(app):
    if _IS_TESTING:
        return
    FastAPIInstrumentor.instrument_app(app)


def instrument_sqlalchemy(engine):
    if _IS_TESTING:
        return
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def instrument_celery(celery_app):
    if _IS_TESTING:
        return
    CeleryInstrumentor().instrument()
