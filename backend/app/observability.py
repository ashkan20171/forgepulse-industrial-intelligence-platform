from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from .config import settings
def configure_observability(app):
    if settings.ENVIRONMENT == 'test': return
    provider=TracerProvider(resource=Resource.create({'service.name':'ashkan-industrial-iot-api','service.version':settings.APP_VERSION}))
    trace.set_tracer_provider(provider)
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,insecure=True)))
    FastAPIInstrumentor.instrument_app(app)
