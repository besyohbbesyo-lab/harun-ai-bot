# tests/test_tracing.py — S7-1: Tracing testleri
# ============================================================

import asyncio

import pytest


class TestHafifSpan:
    def test_span_olustur(self):
        from core.tracing import HafifSpan

        s = HafifSpan("test_span")
        assert s.isim == "test_span"
        assert s.trace_id is not None
        assert s.span_id is not None

    def test_span_ebeveyn_id(self):
        from core.tracing import HafifSpan

        s = HafifSpan("test", ebeveyn_id="abc123")
        assert s.trace_id == "abc123"

    def test_attribute_set(self):
        from core.tracing import HafifSpan

        s = HafifSpan("test")
        s.set_attribute("model", "llama3")
        assert s.etiketler["model"] == "llama3"

    def test_exception_kaydet(self):
        from core.tracing import HafifSpan

        s = HafifSpan("test")
        s.record_exception(ValueError("test hatasi"))
        assert s.hatali is True
        assert "test hatasi" in s.etiketler["hata"]

    def test_context_manager(self):
        from core.tracing import HafifSpan

        with HafifSpan("test") as s:
            s.set_attribute("key", "val")
        assert s.etiketler["key"] == "val"

    def test_sure_olcumu(self):
        import time

        from core.tracing import HafifSpan

        with HafifSpan("test") as s:
            time.sleep(0.01)
        assert (time.time() - s.baslangic) >= 0


class TestSpanContextManager:
    def test_basarili_span(self):
        from core.tracing import span

        with span("test_op") as s:
            assert s is not None

    def test_etiketli_span(self):
        from core.tracing import span

        with span("test_op", {"model": "gpt4", "tokens": 100}) as s:
            pass

    def test_hata_yakalar(self):
        from core.tracing import span

        with pytest.raises(ValueError):
            with span("hata_span"):
                raise ValueError("test")

    def test_ic_ice_span(self):
        from core.tracing import span

        with span("dis_span"):
            with span("ic_span"):
                pass

    def test_none_etiket(self):
        from core.tracing import span

        with span("test", None) as s:
            assert s is not None


class TestTraceDecorator:
    def test_sync_decorator(self):
        from core.tracing import trace_et

        @trace_et("test_sync")
        def toplama(a, b):
            return a + b

        assert toplama(2, 3) == 5

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        from core.tracing import trace_et

        @trace_et("test_async")
        async def async_topla(a, b):
            return a + b

        sonuc = await async_topla(3, 4)
        assert sonuc == 7

    def test_decorator_isim_otomatik(self):
        from core.tracing import trace_et

        @trace_et()
        def fonksiyon():
            return "ok"

        assert fonksiyon() == "ok"

    def test_decorator_hata_iletir(self):
        from core.tracing import trace_et

        @trace_et("hata_test")
        def hatali():
            raise RuntimeError("dekorator hata")

        with pytest.raises(RuntimeError):
            hatali()


class TestTracingDurumu:
    def test_durum_yapisi(self):
        from core.tracing import tracing_durumu

        durum = tracing_durumu()
        assert "aktif" in durum
        assert "backend" in durum
        assert "jaeger_endpoint" in durum

    def test_aktif_trace_id(self):
        from core.tracing import aktif_trace_id

        tid = aktif_trace_id()
        assert isinstance(tid, str)
        assert len(tid) > 0
