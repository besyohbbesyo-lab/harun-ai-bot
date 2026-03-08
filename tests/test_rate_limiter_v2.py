# tests/test_rate_limiter_v2.py — S7-4: Rate Limiter v2 testleri
# ============================================================

import asyncio
import time

import pytest

from core.rate_limiter_v2 import (
    KOTA_ADMIN,
    KOTA_BURST,
    KOTA_PREMIUM,
    KOTA_VARSAYILAN,
    Kota,
    SlidingWindowLimiter,
    get_limiter,
)


class TestSlidingWindow:
    def setup_method(self):
        self.limiter = SlidingWindowLimiter()
        self.kota = Kota(istek_sayisi=3, pencere_sn=60, ad="test")

    def test_ilk_istek_izinli(self):
        izin, bilgi = self.limiter.kontrol_et("user1", self.kota)
        assert izin is True
        assert bilgi["kalan"] == 2

    def test_limit_dolunca_engelle(self):
        for _ in range(3):
            self.limiter.kontrol_et("user2", self.kota)
        izin, bilgi = self.limiter.kontrol_et("user2", self.kota)
        assert izin is False
        assert bilgi["kalan"] == 0
        assert bilgi["bekleme_sn"] > 0

    def test_farkli_kullanicilar_bagimsiz(self):
        for _ in range(3):
            self.limiter.kontrol_et("userA", self.kota)
        izin, _ = self.limiter.kontrol_et("userB", self.kota)
        assert izin is True

    def test_pencere_dolunca_sifirlanir(self):
        kota = Kota(istek_sayisi=2, pencere_sn=0.1, ad="kisa")
        for _ in range(2):
            self.limiter.kontrol_et("user3", kota)
        time.sleep(0.15)  # Pencere gecsin
        izin, _ = self.limiter.kontrol_et("user3", kota)
        assert izin is True

    def test_kalan_istek_sayisi(self):
        _, bilgi = self.limiter.kontrol_et("user4", self.kota)
        assert bilgi["mevcut_istek"] == 1
        assert bilgi["kalan"] == 2

    def test_engelleme_sayaci(self):
        for _ in range(4):
            self.limiter.kontrol_et("user5", self.kota)
        ist = self.limiter.istatistik("user5")
        assert ist["engellendi"] == 1

    def test_ozel_kota_ata(self):
        self.limiter.ozel_kota_ata("vip_user", KOTA_PREMIUM)
        for _ in range(20):
            izin, _ = self.limiter.kontrol_et("vip_user")
        assert izin is True  # Premium: 50 istek

    def test_sifirla_kullanici(self):
        for _ in range(3):
            self.limiter.kontrol_et("user6", self.kota)
        self.limiter.sifirla("user6")
        izin, _ = self.limiter.kontrol_et("user6", self.kota)
        assert izin is True

    def test_sifirla_tumu(self):
        self.limiter.kontrol_et("u1", self.kota)
        self.limiter.kontrol_et("u2", self.kota)
        self.limiter.sifirla()
        ist = self.limiter.istatistik()
        assert ist["toplam_kullanici"] == 0

    def test_istatistik_genel(self):
        self.limiter.kontrol_et("u1", self.kota)
        self.limiter.kontrol_et("u2", self.kota)
        ist = self.limiter.istatistik()
        assert ist["toplam_kullanici"] == 2
        assert ist["toplam_istek"] == 2

    def test_istatistik_kullanici(self):
        self.limiter.kontrol_et("u3", self.kota)
        ist = self.limiter.istatistik("u3")
        assert ist["toplam"] == 1
        assert ist["kullanici"] == "u3"

    @pytest.mark.asyncio
    async def test_async_kontrol(self):
        izin, bilgi = await self.limiter.kontrol_et_async("async_user", self.kota)
        assert izin is True

    @pytest.mark.asyncio
    async def test_async_limit(self):
        for _ in range(3):
            await self.limiter.kontrol_et_async("async_limit", self.kota)
        izin, _ = await self.limiter.kontrol_et_async("async_limit", self.kota)
        assert izin is False

    @pytest.mark.asyncio
    async def test_eszamanli_async(self):
        """Eszamanli async istekler race condition olmamali."""
        sonuclar = await asyncio.gather(
            *[self.limiter.kontrol_et_async("concurrent", self.kota) for _ in range(5)]
        )
        izinler = [s[0] for s in sonuclar]
        assert izinler.count(True) == 3
        assert izinler.count(False) == 2


class TestKotaTanimlari:
    def test_varsayilan_kota(self):
        assert KOTA_VARSAYILAN.istek_sayisi == 10
        assert KOTA_VARSAYILAN.pencere_sn == 60

    def test_premium_kota(self):
        assert KOTA_PREMIUM.istek_sayisi == 50

    def test_admin_kota(self):
        assert KOTA_ADMIN.istek_sayisi == 200

    def test_burst_kota(self):
        assert KOTA_BURST.pencere_sn == 10

    def test_singleton(self):
        l1 = get_limiter()
        l2 = get_limiter()
        assert l1 is l2
