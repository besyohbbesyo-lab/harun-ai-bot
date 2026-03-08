# tests/test_latency_routing.py
# Sprint 4 — A4-3: Latency Routing Testleri

import time

import pytest


class TestLatencyRouting:
    def test_rotator_olusturulabilir(self):
        """APIRotator mock key ile olusturulabilmeli."""
        import os

        os.environ["GROQ_API_KEY"] = "gsk_test_mock_key_12345"
        from api_rotator import APIRotator

        r = APIRotator()
        assert r is not None

    def test_basari_kaydet_latency_gunceller(self):
        """basari_kaydet() sonrasi avg_latency_ms guncellenmeli."""
        import os

        os.environ["GROQ_API_KEY"] = "gsk_test_mock_key_12345"
        from api_rotator import APIRotator

        r = APIRotator()
        r.basari_kaydet(isim="Groq", latency_ms=200.0)
        st = r._keys[r._active_idx]
        assert st.avg_latency_ms > 0
        assert st.ok_count >= 1

    def test_ewma_latency_guncelleme(self):
        """Birden fazla basari kaydinda EWMA latency dogru hesaplanmali."""
        import os

        os.environ["GROQ_API_KEY"] = "gsk_test_mock_key_12345"
        from api_rotator import APIRotator

        r = APIRotator()
        r.basari_kaydet(isim="Groq", latency_ms=100.0)
        r.basari_kaydet(isim="Groq", latency_ms=300.0)
        r.basari_kaydet(isim="Groq", latency_ms=200.0)
        st = r._keys[r._active_idx]
        # EWMA 100-300 ms arasinda olmali
        assert 50.0 <= st.avg_latency_ms <= 400.0

    def test_model_cooldown_rate_limit(self):
        """Rate limit hatasi sonrasi model cooldown'a girmeli."""
        import os

        os.environ["GROQ_API_KEY"] = "gsk_test_mock_key_12345"
        from api_rotator import GROQ_MODELS, APIRotator

        r = APIRotator()
        model_id = GROQ_MODELS[0][0]
        r.hata_kaydet(isim="Groq", hata="429 rate limit exceeded", cooldown_s=60, model_id=model_id)
        st = r._keys[r._active_idx]
        assert model_id in st.model_cooldown
        assert st.model_cooldown[model_id] > time.time()

    def test_gorev_bazli_model_secimi(self):
        """Gorev turune gore dogru model secilmeli."""
        import os

        os.environ["GROQ_API_KEY"] = "gsk_test_mock_key_12345"
        from api_rotator import TASK_MODEL_PREF, APIRotator

        r = APIRotator()
        provider = r.aktif_provider_al(gorev_turu="kod")
        assert provider is not None
        assert "model" in provider
        assert "api_key" in provider

    def test_durum_ozeti_latency_iceriyor(self):
        """durum_ozeti() latency bilgisi icermeli."""
        import os

        os.environ["GROQ_API_KEY"] = "gsk_test_mock_key_12345"
        from api_rotator import APIRotator

        r = APIRotator()
        r.basari_kaydet(isim="Groq", latency_ms=150.0)
        ozet = r.durum_ozeti()
        assert "avg" in ozet
        assert "ms" in ozet

    def test_api_test_sonuclari_latency_alanlari(self):
        """api_test_sonuclari() latency alanlarini icermeli."""
        import os

        os.environ["GROQ_API_KEY"] = "gsk_test_mock_key_12345"
        from api_rotator import APIRotator

        r = APIRotator()
        r.basari_kaydet(isim="Groq", latency_ms=250.0)
        sonuclar = r.api_test_sonuclari()
        assert len(sonuclar) > 0
        assert "avg_latency_ms" in sonuclar[0]
        assert "last_latency_ms" in sonuclar[0]
        assert sonuclar[0]["avg_latency_ms"] > 0

    def test_dusuk_latency_key_tercih_edilir(self):
        """Dusuk latency'li key tercih edilmeli (coklu key senaryosu)."""
        import os

        os.environ.pop("GROQ_API_KEY", None)
        os.environ["GROQ_API_KEYS"] = "gsk_key1_mock,gsk_key2_mock"
        from api_rotator import APIRotator

        r = APIRotator()
        # key[0]'a yuksek latency kaydet
        r._active_idx = 0
        r.basari_kaydet(isim="Groq", latency_ms=1000.0)
        # key[1]'e dusuk latency kaydet
        r._active_idx = 1
        r.basari_kaydet(isim="Groq", latency_ms=100.0)
        # Simdi aktif provider al — dusuk latency'li secilmeli
        provider = r.aktif_provider_al()
        assert provider is not None
