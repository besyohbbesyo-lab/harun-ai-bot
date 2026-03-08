# tests/test_resilience.py — CircuitBreaker + Retry testleri
# ============================================================
# pytest -v tests/test_resilience.py
# ============================================================

import asyncio
import time

import pytest

from core.resilience import CircuitBreaker, CircuitOpenError, retry_async

# ─────────────────────────────────────────────────────────────
# BÖLÜM 1: CircuitBreaker DURUM TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestCircuitBreakerDurumlar:
    """CLOSED → OPEN → HALF_OPEN → CLOSED döngüsü."""

    def _yeni_cb(self, threshold=3, timeout=60):
        return CircuitBreaker(name="Test", threshold=threshold, timeout=timeout)

    def test_baslangicta_closed(self):
        """Yeni CB CLOSED durumda başlamalı."""
        cb = self._yeni_cb()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failures == 0

    @pytest.mark.asyncio
    async def test_basarili_cagri_closed_kaliyor(self):
        """Başarılı çağrı sonrası CLOSED kalmalı."""
        cb = self._yeni_cb()

        async def basarili():
            return "ok"

        await cb.call(basarili)
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failures == 0

    @pytest.mark.asyncio
    async def test_threshold_kadar_hata_closed_kaliyor(self):
        """threshold-1 hata sonrası hâlâ CLOSED olmalı."""
        cb = self._yeni_cb(threshold=3)

        async def hatali():
            raise ValueError("test hata")

        for _ in range(2):  # threshold-1 = 2
            try:
                await cb.call(hatali)
            except ValueError:
                pass

        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failures == 2

    @pytest.mark.asyncio
    async def test_threshold_dolunca_open(self):
        """threshold kadar hata sonrası OPEN olmalı."""
        cb = self._yeni_cb(threshold=3)

        async def hatali():
            raise ValueError("test hata")

        for _ in range(3):
            try:
                await cb.call(hatali)
            except (ValueError, CircuitOpenError):
                pass

        assert cb.state == CircuitBreaker.OPEN
        assert cb.opened_at is not None

    @pytest.mark.asyncio
    async def test_open_durumda_circuit_open_error(self):
        """OPEN durumda CircuitOpenError fırlatmalı."""
        cb = self._yeni_cb(threshold=1)

        async def hatali():
            raise ValueError("hata")

        try:
            await cb.call(hatali)
        except (ValueError, CircuitOpenError):
            pass

        with pytest.raises(CircuitOpenError):
            await cb.call(hatali)

    @pytest.mark.asyncio
    async def test_timeout_sonrasi_half_open(self):
        """Timeout sonrası OPEN → HALF_OPEN geçişi."""
        cb = self._yeni_cb(threshold=1, timeout=0.1)

        async def hatali():
            raise ValueError("hata")

        try:
            await cb.call(hatali)
        except (ValueError, CircuitOpenError):
            pass

        # Timeout bekle
        await asyncio.sleep(0.2)
        cb._gecis_kontrol()
        assert cb.state == CircuitBreaker.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_basarili_closed(self):
        """HALF_OPEN'da başarılı çağrı → CLOSED."""
        cb = self._yeni_cb(threshold=1, timeout=0.1)

        async def hatali():
            raise ValueError("hata")

        async def basarili():
            return "ok"

        try:
            await cb.call(hatali)
        except (ValueError, CircuitOpenError):
            pass

        await asyncio.sleep(0.2)
        cb._gecis_kontrol()

        await cb.call(basarili)
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failures == 0

    @pytest.mark.asyncio
    async def test_half_open_hatali_open(self):
        """HALF_OPEN'da hatalı çağrı → tekrar OPEN."""
        cb = self._yeni_cb(threshold=1, timeout=0.1)

        async def hatali():
            raise ValueError("hata")

        try:
            await cb.call(hatali)
        except (ValueError, CircuitOpenError):
            pass

        await asyncio.sleep(0.2)
        cb._gecis_kontrol()
        assert cb.state == CircuitBreaker.HALF_OPEN

        try:
            await cb.call(hatali)
        except (ValueError, CircuitOpenError):
            pass

        assert cb.state == CircuitBreaker.OPEN


# ─────────────────────────────────────────────────────────────
# BÖLÜM 2: HARD TIMEOUT TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestHardTimeout:
    """asyncio.timeout hard limit testleri."""

    @pytest.mark.asyncio
    async def test_hard_timeout_asimi(self):
        """Hard timeout aşımında TimeoutError fırlatmalı."""
        cb = CircuitBreaker(name="TimeoutTest", threshold=5, timeout=60)

        async def yavas_fn():
            await asyncio.sleep(5)  # 5 saniye bekle
            return "ok"

        with pytest.raises((TimeoutError, asyncio.TimeoutError, Exception)):
            await cb.call(yavas_fn, hard_timeout=0.1)

    @pytest.mark.asyncio
    async def test_hard_timeout_sifir_devre_disi(self):
        """hard_timeout=0 ise timeout uygulanmamalı."""
        cb = CircuitBreaker(name="NoTimeoutTest", threshold=5, timeout=60)

        async def hizli_fn():
            await asyncio.sleep(0.05)
            return "tamam"

        result = await cb.call(hizli_fn, hard_timeout=0)
        assert result == "tamam"

    @pytest.mark.asyncio
    async def test_sync_fn_calistirilir(self):
        """Senkron fonksiyon executor'da çalıştırılmalı."""
        cb = CircuitBreaker(name="SyncTest", threshold=5, timeout=60)

        def sync_fn():
            return "sync sonuc"

        result = await cb.call(sync_fn)
        assert result == "sync sonuc"


# ─────────────────────────────────────────────────────────────
# BÖLÜM 3: DURUM RAPORU TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestDurumRaporu:
    """durum() ve cb_durum_raporu() testleri."""

    def test_durum_dict_donmeli(self):
        """durum() dict dönmeli."""
        cb = CircuitBreaker(name="RaporTest", threshold=3, timeout=60)
        d = cb.durum()
        assert isinstance(d, dict)
        assert "name" in d
        assert "state" in d
        assert "failures" in d
        assert "threshold" in d

    def test_durum_raporu_tum_cblar(self):
        """cb_durum_raporu() tüm CB'leri içermeli."""
        from core.resilience import cb_durum_raporu

        rapor = cb_durum_raporu()
        assert "Groq" in rapor
        assert "Gemini" in rapor
        assert "Ollama" in rapor

    def test_repr_closed(self):
        """CLOSED durumda repr doğru olmalı."""
        cb = CircuitBreaker(name="Repr", threshold=3, timeout=60)
        assert "CLOSED" in repr(cb)
        assert "Repr" in repr(cb)


# ─────────────────────────────────────────────────────────────
# BÖLÜM 4: RETRY DECORATOR TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestRetryAsync:
    """retry_async decorator testleri."""

    @pytest.mark.asyncio
    async def test_ilk_denemede_basari(self):
        """İlk denemede başarı olursa tek çağrı yapılmalı."""
        sayac = {"n": 0}

        @retry_async(max_attempts=3)
        async def fn():
            sayac["n"] += 1
            return "ok"

        result = await fn()
        assert result == "ok"
        assert sayac["n"] == 1

    @pytest.mark.asyncio
    async def test_ikinci_denemede_basari(self):
        """İlk başarısız, ikinci başarılı olursa 2 çağrı yapılmalı."""
        sayac = {"n": 0}

        @retry_async(max_attempts=3, base_delay=0.01)
        async def fn():
            sayac["n"] += 1
            if sayac["n"] < 2:
                raise ValueError("henüz değil")
            return "ok"

        result = await fn()
        assert result == "ok"
        assert sayac["n"] == 2

    @pytest.mark.asyncio
    async def test_max_attempts_asimi_hata_firlatir(self):
        """Tüm denemeler başarısız olursa hata fırlatmalı."""
        sayac = {"n": 0}

        @retry_async(max_attempts=3, base_delay=0.01)
        async def fn():
            sayac["n"] += 1
            raise RuntimeError("sürekli hata")

        with pytest.raises(RuntimeError):
            await fn()
        assert sayac["n"] == 3

    @pytest.mark.asyncio
    async def test_belirli_exception_tipi(self):
        """Sadece belirtilen exception tipini retry etmeli."""
        sayac = {"n": 0}

        @retry_async(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        async def fn():
            sayac["n"] += 1
            raise TypeError("bu retry edilmez")

        with pytest.raises(TypeError):
            await fn()
        assert sayac["n"] == 1  # retry edilmedi
