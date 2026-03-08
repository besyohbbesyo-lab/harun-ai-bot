# core/tracing.py — S7-1: OpenTelemetry Tracing
# Her API cagrisina trace ID ekler, Jaeger ile gorsellestirir
# opentelemetry-sdk yoksa graceful degrade eder
# ============================================================

from __future__ import annotations

import functools
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from core.config import log_yaz

# ── OTel yukleme (opsiyonel) ──────────────────────────────────
_otel_aktif = False
_tracer = None

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Jaeger exporter dene
    try:
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter

        _jaeger_aktif = True
    except ImportError:
        _jaeger_aktif = False

    # TracerProvider kur
    resource = Resource.create({"service.name": "harun-ai-bot"})
    provider = TracerProvider(resource=resource)

    if _jaeger_aktif:
        jaeger = JaegerExporter(
            agent_host_name="localhost",
            agent_port=6831,
        )
        provider.add_span_processor(BatchSpanProcessor(jaeger))
        log_yaz("[Tracing] Jaeger exporter aktif (localhost:6831)", "INFO")

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("harun-ai")
    _otel_aktif = True
    log_yaz("[Tracing] OpenTelemetry aktif", "INFO")

except ImportError:
    log_yaz("[Tracing] opentelemetry-sdk bulunamadi, fallback mod", "WARNING")


# ── Hafif Span (OTel yokken) ──────────────────────────────────


class HafifSpan:
    """
    OTel olmadığında kullanılan minimal span implementasyonu.
    Aynı arayüzü sağlar, loglara yazar.
    """

    def __init__(self, isim: str, ebeveyn_id: str | None = None):
        self.isim = isim
        self.trace_id = ebeveyn_id or str(uuid.uuid4())[:16]
        self.span_id = str(uuid.uuid4())[:8]
        self.baslangic = time.time()
        self.etiketler: dict = {}
        self.hatali = False

    def set_attribute(self, anahtar: str, deger: Any):
        self.etiketler[anahtar] = deger

    def record_exception(self, hata: Exception):
        self.hatali = True
        self.etiketler["hata"] = str(hata)

    def set_status(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sure = (time.time() - self.baslangic) * 1000
        durum = "HATA" if self.hatali or exc_type else "OK"
        log_yaz(
            f"[Trace] {self.isim} | {durum} | {sure:.1f}ms "
            f"| trace={self.trace_id} span={self.span_id}",
            "DEBUG",
        )
        return False


# ── Ana Tracing API ───────────────────────────────────────────


@contextmanager
def span(isim: str, etiketler: dict | None = None):
    """
    Trace span context manager.

    Kullanim:
        async with span("groq_api_cagri", {"model": "llama3"}):
            sonuc = await groq.chat(...)

        with span("rag_retrieve", {"query": sorgu}):
            hits = retrieve(sorgu)
    """
    if _otel_aktif and _tracer:
        with _tracer.start_as_current_span(isim) as s:
            if etiketler:
                for k, v in etiketler.items():
                    s.set_attribute(k, str(v))
            try:
                yield s
            except Exception as e:
                s.record_exception(e)
                try:
                    from opentelemetry.trace import StatusCode

                    s.set_status(StatusCode.ERROR, str(e))
                except Exception:
                    pass
                raise
    else:
        with HafifSpan(isim) as s:
            if etiketler:
                for k, v in (etiketler or {}).items():
                    s.set_attribute(k, str(v))
            try:
                yield s
            except Exception as e:
                s.record_exception(e)
                raise


def trace_et(isim: str | None = None, etiketler: dict | None = None):
    """
    Fonksiyonlar icin trace decorator (sync ve async destekli).

    Kullanim:
        @trace_et("groq_api")
        async def groq_cagri(...): ...

        @trace_et()
        def retrieve(...): ...
    """

    def decorator(func: Callable) -> Callable:
        span_ismi = isim or f"{func.__module__}.{func.__qualname__}"

        if _is_async(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with span(span_ismi, etiketler):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with span(span_ismi, etiketler):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def _is_async(func: Callable) -> bool:
    import asyncio

    return asyncio.iscoroutinefunction(func)


def aktif_trace_id() -> str:
    """Mevcut trace ID'yi doner (loglama icin)."""
    if _otel_aktif:
        try:
            from opentelemetry import trace as otel_trace

            ctx = otel_trace.get_current_span().get_span_context()
            return format(ctx.trace_id, "032x") if ctx.is_valid else "no-trace"
        except Exception:
            pass
    return "no-trace"


def tracing_durumu() -> dict:
    """Tracing sistem durumunu doner."""
    return {
        "aktif": _otel_aktif,
        "backend": "jaeger"
        if (_otel_aktif and _jaeger_aktif)
        else "otel-no-exporter"
        if _otel_aktif
        else "fallback-log",
        "jaeger_endpoint": "localhost:6831" if _otel_aktif else None,
    }
