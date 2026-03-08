# tests/test_bulkhead.py — S6-7: Bulkhead + Timeout testleri
# ============================================================

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


class TestBulkhead:
    def setup_method(self):
        """Her testten önce semaphore'u sıfırla."""
        import core.bulkhead as b

        b._semaphore = None

    def test_bulkhead_durumu(self):
        from core.bulkhead import bulkhead_durumu

        durum = bulkhead_durumu()
        assert durum["max_eszamanli"] == 3
        assert durum["bos_slot"] == 3
        assert durum["kullanilan_slot"] == 0

    @pytest.mark.asyncio
    async def test_basarili_cagri(self):
        from core.bulkhead import bulkhead_cagri

        async def mock_coro():
            return "ok"

        sonuc = await bulkhead_cagri(mock_coro())
        assert sonuc == "ok"

    @pytest.mark.asyncio
    async def test_slot_siniri(self):
        """3 slot doluyken 4. istek BulkheadDolu firlatmali."""
        import core.bulkhead as b
        from core.bulkhead import BulkheadDolu, bulkhead_cagri

        b._semaphore = asyncio.Semaphore(3)

        engel = asyncio.Event()

        async def bekleyen():
            await engel.wait()
            return "tamam"

        # 3 slot doldur
        gorev1 = asyncio.create_task(bulkhead_cagri(bekleyen()))
        gorev2 = asyncio.create_task(bulkhead_cagri(bekleyen()))
        gorev3 = asyncio.create_task(bulkhead_cagri(bekleyen()))
        await asyncio.sleep(0.05)

        # 4. istek reddedilmeli
        with pytest.raises(BulkheadDolu):
            await bulkhead_cagri(bekleyen(), bekleme_suresi=0.1)

        engel.set()
        await asyncio.gather(gorev1, gorev2, gorev3)

    @pytest.mark.asyncio
    async def test_timeout_asilmasi(self):
        """HTTP_TIMEOUT aşılırsa asyncio.TimeoutError fırlatmalı."""
        import core.bulkhead as b
        from core.bulkhead import bulkhead_cagri

        orijinal = b.HTTP_TIMEOUT
        b.HTTP_TIMEOUT = 0.05  # 50ms

        async def yavash():
            await asyncio.sleep(1.0)
            return "asla"

        with pytest.raises(asyncio.TimeoutError):
            await bulkhead_cagri(yavash())

        b.HTTP_TIMEOUT = orijinal

    @pytest.mark.asyncio
    async def test_bulkhead_decorator(self):
        from core.bulkhead import bulkhead

        @bulkhead(bekleme_suresi=2.0)
        async def korunan_fonksiyon(x):
            return x * 2

        assert await korunan_fonksiyon(5) == 10

    @pytest.mark.asyncio
    async def test_slot_serbest_birakilir(self):
        """Cagri bittikten sonra slot serbest birakilmali."""
        from core.bulkhead import bulkhead_cagri, bulkhead_durumu

        async def hizli():
            return "hizli"

        await bulkhead_cagri(hizli())
        durum = bulkhead_durumu()
        assert durum["bos_slot"] == 3  # slot geri verildi

    @pytest.mark.asyncio
    async def test_hata_durumunda_slot_serbest(self):
        """Hata olsa bile slot serbest birakilmali."""
        from core.bulkhead import bulkhead_cagri, bulkhead_durumu

        async def hatali():
            raise ValueError("test hatasi")

        with pytest.raises(ValueError):
            await bulkhead_cagri(hatali())

        durum = bulkhead_durumu()
        assert durum["bos_slot"] == 3

    @pytest.mark.asyncio
    async def test_eszamanli_basarili_cagriler(self):
        """3 esz zamanli cagri basariyla tamamlanmali."""
        from core.bulkhead import bulkhead_cagri

        async def hizli(n):
            await asyncio.sleep(0.01)
            return n

        sonuclar = await asyncio.gather(
            bulkhead_cagri(hizli(1)),
            bulkhead_cagri(hizli(2)),
            bulkhead_cagri(hizli(3)),
        )
        assert sorted(sonuclar) == [1, 2, 3]

    def test_httpx_client_timeout(self):
        import httpx

        from core.bulkhead import CONNECT_TIMEOUT, READ_TIMEOUT, httpx_client

        client = httpx_client()
        assert isinstance(client, httpx.AsyncClient)
