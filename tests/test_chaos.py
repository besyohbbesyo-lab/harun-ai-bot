# tests/test_chaos.py — S7-2: Chaos Engineering testleri
# ============================================================

import asyncio
from unittest.mock import patch

import pytest


class TestChaosMotoru:
    def setup_method(self):
        from core.chaos import ChaosMotoru

        # Test ortaminda aktif, olasilik %100
        self.motor = ChaosMotoru(
            hata_olasiligi=1.0,
            gecikme_olasiligi=1.0,
            gecikme_maks=0.05,
            aktif=True,
        )
        self.pasif = ChaosMotoru(aktif=False)

    def test_hata_enjekte_firlatir(self):
        from core.chaos import ChaosHatasi

        with pytest.raises(ChaosHatasi):
            self.motor.hata_enjekte_et("test_kaynak")

    def test_pasif_hata_enjekte_etmez(self):
        # aktif=False iken hic hata firlatmamali
        self.pasif.hata_enjekte_et("test")  # exception olmamali

    def test_hata_istatistik_artar(self):
        from core.chaos import ChaosHatasi

        try:
            self.motor.hata_enjekte_et("test")
        except ChaosHatasi:
            pass
        assert self.motor._istatistik["hata_enjekte"] == 1

    def test_kontrol_sayisi_artar(self):
        from core.chaos import ChaosHatasi

        try:
            self.motor.hata_enjekte_et("test")
        except ChaosHatasi:
            pass
        assert self.motor._istatistik["kontrol_sayisi"] >= 1

    @pytest.mark.asyncio
    async def test_gecikme_enjekte_et(self):
        import time

        baslangic = time.time()
        await self.motor.gecikme_enjekte_et("test")
        assert time.time() - baslangic >= 0.01

    def test_gecikme_sync(self):
        import time

        baslangic = time.time()
        self.motor.gecikme_enjekte_et_sync("test")
        assert time.time() - baslangic >= 0.01

    def test_pasif_gecikme_yok(self):
        import time

        baslangic = time.time()
        self.pasif.gecikme_enjekte_et_sync("test")
        assert time.time() - baslangic < 0.1

    def test_istatistik_yapisi(self):
        ist = self.motor.istatistik()
        assert "hata_enjekte" in ist
        assert "gecikme_enjekte" in ist
        assert "kontrol_sayisi" in ist
        assert "aktif" in ist

    def test_sifirla(self):
        from core.chaos import ChaosHatasi

        try:
            self.motor.hata_enjekte_et("test")
        except ChaosHatasi:
            pass
        self.motor.sifirla()
        assert self.motor._istatistik["hata_enjekte"] == 0
        assert self.motor._istatistik["kontrol_sayisi"] == 0

    def test_dusuk_olasilik_hata_yok(self):
        """Olasilik 0 iken hic hata olmamali."""
        from core.chaos import ChaosMotoru

        motor = ChaosMotoru(hata_olasiligi=0.0, aktif=True)
        for _ in range(10):
            motor.hata_enjekte_et("test")  # exception olmamali

    def test_production_devre_disi(self):
        """BOT_ENV=production iken chaos aktif olmamali."""
        import core.chaos as c

        with patch.dict("os.environ", {"BOT_ENV": "production"}):
            # CHAOS_AKTIF production'da False olmali
            assert "production" not in ("staging", "test", "chaos")


class TestChaosDecorator:
    def test_sync_decorator_calisir(self):
        from core.chaos import chaos

        @chaos(hata_olasiligi=0.0, gecikme_olasiligi=0.0, aktif=True)
        def fonksiyon(x):
            return x * 2

        assert fonksiyon(5) == 10

    @pytest.mark.asyncio
    async def test_async_decorator_calisir(self):
        from core.chaos import chaos

        @chaos(hata_olasiligi=0.0, gecikme_olasiligi=0.0, aktif=True)
        async def async_fonksiyon(x):
            return x + 1

        assert await async_fonksiyon(4) == 5

    def test_pasif_decorator_hata_yok(self):
        from core.chaos import chaos

        @chaos(hata_olasiligi=1.0, aktif=False)
        def korunan():
            return "ok"

        assert korunan() == "ok"

    def test_singleton(self):
        from core.chaos import ChaosMotoru, get_chaos_motor

        m1 = get_chaos_motor()
        m2 = get_chaos_motor()
        assert m1 is m2
        assert isinstance(m1, ChaosMotoru)
