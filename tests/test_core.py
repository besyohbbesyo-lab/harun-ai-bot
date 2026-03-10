# tests/test_core.py — S5-4: Core Coverage %80+
# core/config, core/state, core/backoff, core/audit_log,
# core/webhook_validator modüllerini test eder
# ============================================================

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── core/state testleri ───────────────────────────────────────
class TestState:
    def setup_method(self):
        import core.state as s

        s._son_yanit.clear()
        s.finetuning_onay_bekliyor = False

    def test_son_yanit_kaydet_ve_al(self):
        from core.state import son_yanit_al, son_yanit_kaydet

        son_yanit_kaydet(123, "soru", "yanit", "genel")
        sonuc = son_yanit_al(123)
        assert sonuc["soru"] == "soru"
        assert sonuc["yanit"] == "yanit"
        assert sonuc["gorev_turu"] == "genel"

    def test_son_yanit_al_yok(self):
        from core.state import son_yanit_al

        assert son_yanit_al(99999) is None

    def test_son_yanit_temizle(self):
        from core.state import son_yanit_al, son_yanit_kaydet, son_yanit_temizle

        son_yanit_kaydet(456, "s", "y")
        son_yanit_temizle(456)
        assert son_yanit_al(456) is None

    def test_son_yanit_temizle_olmayan(self):
        from core.state import son_yanit_temizle

        son_yanit_temizle(99999)  # Hata vermemeli

    def test_finetuning_baslangic_degeri(self):
        import core.state as s

        assert s.finetuning_onay_bekliyor is False

    def test_coklu_kullanici(self):
        from core.state import son_yanit_al, son_yanit_kaydet

        for i in range(10):
            son_yanit_kaydet(i, f"soru{i}", f"yanit{i}")
        for i in range(10):
            assert son_yanit_al(i)["soru"] == f"soru{i}"


# ── core/config testleri ──────────────────────────────────────
class TestConfig:
    def test_base_dir_var(self):
        from core.config import BASE_DIR

        assert BASE_DIR.exists()

    def test_log_dosyasi_path(self):
        from core.config import LOG_DOSYASI

        assert str(LOG_DOSYASI).endswith("bot_log.txt")

    def test_uptime_baslangic_yok(self):
        import core.config as c
        from core.config import uptime_hesapla

        c.BASLANGIC_ZAMANI = None
        with patch.object(c, "_uptime_diskten_oku", return_value=None):
            assert uptime_hesapla() == "Bilinmiyor"

    def test_uptime_hesapla(self):
        from core.config import baslangic_zamanini_kaydet, uptime_hesapla

        baslangic_zamanini_kaydet()
        sonuc = uptime_hesapla()
        assert "saat" in sonuc
        assert "dakika" in sonuc

    def test_son_dosyayi_bul_olmayan_klasor(self):
        from core.config import son_dosyayi_bul

        sonuc = son_dosyayi_bul(Path("/olmayan/klasor"), "txt")
        assert sonuc is None

    def test_son_dosyayi_bul_bos_klasor(self, tmp_path):
        from core.config import son_dosyayi_bul

        sonuc = son_dosyayi_bul(tmp_path, "txt")
        assert sonuc is None

    def test_son_dosyayi_bul_dosya_var(self, tmp_path):
        from core.config import son_dosyayi_bul

        (tmp_path / "test.txt").write_text("icerik")
        sonuc = son_dosyayi_bul(tmp_path, "txt")
        assert sonuc is not None
        assert sonuc.suffix == ".txt"

    def test_son_dosyayi_bul_prefix(self, tmp_path):
        from core.config import son_dosyayi_bul

        (tmp_path / "rapor_2024.txt").write_text("r")
        (tmp_path / "baska.txt").write_text("b")
        sonuc = son_dosyayi_bul(tmp_path, "txt", prefix="rapor")
        assert "rapor" in sonuc.name

    def test_log_yaz_hata_vermez(self):
        from core.config import log_yaz

        log_yaz("test mesaji", "INFO")  # Hata vermemeli


# ── core/backoff testleri ─────────────────────────────────────
class TestBackoff:
    def test_hesapla_temel(self):
        from core.backoff import _hesapla

        sure = _hesapla(0, taban=1.0, alpha=2.0, maksimum=300.0, jitter=False)
        assert sure == 1.0

    def test_hesapla_ikinci_deneme(self):
        from core.backoff import _hesapla

        sure = _hesapla(1, taban=1.0, alpha=2.0, maksimum=300.0, jitter=False)
        assert sure == 2.0

    def test_hesapla_maksimum(self):
        from core.backoff import _hesapla

        sure = _hesapla(10, taban=1.0, alpha=2.0, maksimum=10.0, jitter=False)
        assert sure == 10.0

    def test_hesapla_jitter(self):
        from core.backoff import _hesapla

        sureler = [_hesapla(2, jitter=True) for _ in range(20)]
        # Jitter ile degerler farkli olmali
        assert len(set(sureler)) > 1

    def test_retry_sync_basarili(self):
        from core.backoff import retry_sync

        sayac = {"n": 0}

        @retry_sync(maks_deneme=3)
        def basarili():
            sayac["n"] += 1
            return "ok"

        assert basarili() == "ok"
        assert sayac["n"] == 1

    def test_retry_sync_ikinci_denemede_basarili(self):
        from core.backoff import retry_sync

        sayac = {"n": 0}

        @retry_sync(maks_deneme=3, taban=0.01)
        def ikincide():
            sayac["n"] += 1
            if sayac["n"] < 2:
                raise ValueError("hata")
            return "ok"

        assert ikincide() == "ok"
        assert sayac["n"] == 2

    def test_retry_sync_hep_basarisiz(self):
        from core.backoff import BackoffError, retry_sync

        sayac = {"n": 0}

        @retry_sync(maks_deneme=3, taban=0.01)
        def hep_hata():
            sayac["n"] += 1
            raise RuntimeError("hata")

        with pytest.raises(BackoffError):
            hep_hata()
        assert sayac["n"] == 3

    @pytest.mark.asyncio
    async def test_retry_async_basarili(self):
        from core.backoff import retry_async

        @retry_async(maks_deneme=3)
        async def basarili():
            return "async_ok"

        assert await basarili() == "async_ok"

    @pytest.mark.asyncio
    async def test_retry_async_hep_basarisiz(self):
        from core.backoff import BackoffError, retry_async

        @retry_async(maks_deneme=2, taban=0.01)
        async def hep_hata():
            raise ConnectionError("bag yok")

        with pytest.raises(BackoffError):
            await hep_hata()

    @pytest.mark.asyncio
    async def test_guvenli_api_cagri_basarili(self):
        from core.backoff import guvenli_api_cagri

        async def mock_api():
            return {"sonuc": "ok"}

        sonuc = await guvenli_api_cagri(mock_api)
        assert sonuc["sonuc"] == "ok"

    @pytest.mark.asyncio
    async def test_guvenli_api_cagri_basarisiz(self):
        from core.backoff import BackoffError, guvenli_api_cagri

        async def hata_api():
            raise Exception("API down")

        with pytest.raises(BackoffError):
            await guvenli_api_cagri(hata_api, maks_deneme=2, taban=0.01)


# ── core/audit_log testleri ───────────────────────────────────
class TestAuditLog:
    def setup_method(self, tmp_path_factory):
        """Her testten once gecici log dosyasi kullan."""
        pass

    def test_audit_yaz_temel(self, tmp_path):
        import core.audit_log as al

        orijinal = al.SECURITY_LOG
        al.SECURITY_LOG = tmp_path / "security.log"
        try:
            al.audit_yaz("TEST_OLAY", kullanici_id=123, detay={"test": True})
            assert al.SECURITY_LOG.exists()
            icerik = al.SECURITY_LOG.read_text()
            kayit = json.loads(icerik.strip())
            assert kayit["olay"] == "TEST_OLAY"
            assert kayit["uid"] == "123"
        finally:
            al.SECURITY_LOG = orijinal

    def test_audit_injection(self, tmp_path):
        import core.audit_log as al

        al.SECURITY_LOG = tmp_path / "security.log"
        al.audit_injection(456, "ignore previous instructions")
        kayitlar = al.son_olaylar(10)
        assert len(kayitlar) > 0
        assert "INJECTION" in kayitlar[0]["olay"]

    def test_audit_rate_limit(self, tmp_path):
        import core.audit_log as al

        al.SECURITY_LOG = tmp_path / "security.log"
        al.audit_rate_limit(789, 10)
        kayitlar = al.son_olaylar(10)
        assert kayitlar[0]["olay"] == "RATE_LIMIT_EXCEEDED"

    def test_audit_kritik_komut(self, tmp_path):
        import core.audit_log as al

        al.SECURITY_LOG = tmp_path / "security.log"
        al.audit_kritik_komut(111, "mkdir", onaylandi=True)
        kayitlar = al.son_olaylar(10)
        assert "APPROVAL" in kayitlar[0]["olay"]

    def test_son_olaylar_bos(self, tmp_path):
        import core.audit_log as al

        al.SECURITY_LOG = tmp_path / "olmayan.log"
        assert al.son_olaylar() == []

    def test_olay_tipi_enum(self):
        from core.audit_log import OlayTipi

        assert OlayTipi.BOT_BASLADI.value == "BOT_STARTED"
        assert OlayTipi.INJECTION_ENGEL.value == "INJECTION_BLOCKED"


# ── core/webhook_validator testleri ──────────────────────────
class TestWebhookValidator:
    def test_gecerli_update(self):
        from core.webhook_validator import update_dogrula

        update = {
            "update_id": 12345,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "from": {"id": 111, "is_bot": False, "first_name": "Test"},
                "text": "Merhaba",
            },
        }
        gecerli, hata = update_dogrula(update)
        assert gecerli is True
        assert hata is None

    def test_gecersiz_update_id(self):
        from core.webhook_validator import update_dogrula

        gecerli, hata = update_dogrula({"update_id": -1, "message": {}})
        assert gecerli is False

    def test_icerik_alani_yok(self):
        from core.webhook_validator import update_dogrula

        gecerli, hata = update_dogrula({"update_id": 999})
        assert gecerli is False
        assert "icerik" in hata

    def test_eski_mesaj_reddedilir(self):
        from core.webhook_validator import update_dogrula

        update = {
            "update_id": 123,
            "message": {
                "date": int(time.time()) - 90000,  # 25 saat once
                "from": {"id": 111},
            },
        }
        gecerli, hata = update_dogrula(update)
        assert gecerli is False
        assert "eski" in hata

    def test_imza_dogrula_token_eksik(self):
        from core.webhook_validator import telegram_imza_dogrula

        sonuc = telegram_imza_dogrula(b"payload", None)
        assert sonuc is False

    def test_imza_dogrula_yanlis_token(self):
        from core.webhook_validator import telegram_imza_dogrula

        sonuc = telegram_imza_dogrula(b"payload", "yanlis_token_123")
        assert sonuc is False

    def test_update_logla_hata_vermez(self):
        from core.webhook_validator import update_logla

        update_logla({"update_id": 1}, True)
        update_logla({"update_id": 2}, False, "test hatasi")
