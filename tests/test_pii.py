# tests/test_pii.py — PII Maskeleme & Log Testleri
# ============================================================
# pytest -v tests/test_pii.py
# ============================================================

import tempfile
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────
# BÖLÜM 1: PII MASKELEME TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestPIIMaskeleme:
    """maskele_pii() fonksiyonu testleri."""

    def test_groq_api_key_maskelenir(self):
        """Groq API key maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "API key: gsk_abc123def456ghi789jkl012mno"
        sonuc = maskele_pii(mesaj)
        assert "gsk_" not in sonuc
        assert "***GSK_KEY***" in sonuc

    def test_openai_api_key_maskelenir(self):
        """OpenAI API key maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "OpenAI key: sk-abc123def456ghi789jkl012mno345"
        sonuc = maskele_pii(mesaj)
        assert "sk-" not in sonuc
        assert "***SK_KEY***" in sonuc

    def test_bot_token_maskelenir(self):
        """Telegram bot token maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "Bot token: 1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"
        sonuc = maskele_pii(mesaj)
        assert "1234567890:" not in sonuc
        assert "***BOT_TOKEN***" in sonuc

    def test_email_maskelenir(self):
        """Email adresi maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "Email: harun@example.com ile iletişime geçin"
        sonuc = maskele_pii(mesaj)
        assert "harun@example.com" not in sonuc
        assert "***EMAIL***" in sonuc

    def test_telefon_tr_maskelenir(self):
        """Türkiye telefon numarası maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "Ara: 05321234567"
        sonuc = maskele_pii(mesaj)
        assert "05321234567" not in sonuc

    def test_telefon_uluslararasi_maskelenir(self):
        """Uluslararası telefon numarası maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "Tel: +905321234567"
        sonuc = maskele_pii(mesaj)
        assert "+905321234567" not in sonuc

    def test_ip_adresi_maskelenir(self):
        """IP adresi maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "Server IP: 192.168.1.100 adresinden bağlantı"
        sonuc = maskele_pii(mesaj)
        assert "192.168.1.100" not in sonuc
        assert "***IP***" in sonuc

    def test_bearer_token_maskelenir(self):
        """Bearer token maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "Header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        sonuc = maskele_pii(mesaj)
        assert "eyJhbGci" not in sonuc
        assert "***BEARER***" in sonuc

    def test_genel_secret_maskelenir(self):
        """Genel secret pattern maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "api_key=aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgH"
        sonuc = maskele_pii(mesaj)
        assert "aBcDeFgHiJkLmNoPqRsTuVwXyZ" not in sonuc
        assert "***SECRET***" in sonuc

    def test_normal_metin_degismez(self):
        """PII içermeyen normal metin değişmemeli."""
        from log_utils import maskele_pii

        mesaj = "Kullanıcı mesaj gönderdi: Merhaba, nasılsın?"
        sonuc = maskele_pii(mesaj)
        assert sonuc == mesaj

    def test_bos_mesaj(self):
        """Boş mesaj boş dönmeli."""
        from log_utils import maskele_pii

        assert maskele_pii("") == ""
        assert maskele_pii(None) is None

    def test_coklu_pii_tek_mesajda(self):
        """Bir mesajda birden fazla PII maskelenmeli."""
        from log_utils import maskele_pii

        mesaj = "User harun@test.com IP 10.0.0.1 key gsk_testkey12345678901234"
        sonuc = maskele_pii(mesaj)
        assert "harun@test.com" not in sonuc
        assert "10.0.0.1" not in sonuc
        assert "gsk_" not in sonuc


# ─────────────────────────────────────────────────────────────
# BÖLÜM 2: LOG ROTATION TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestLogRotation:
    """_log_rotasyon() fonksiyonu testleri."""

    def test_kucuk_dosya_rotate_edilmez(self):
        """MAX_LOG_BOYUTU altındaki dosya rotate edilmemeli."""
        from log_utils import _log_rotasyon

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dosya = Path(tmpdir) / "test_log.txt"
            log_dosya.write_text("kısa log")
            _log_rotasyon(log_dosya)
            # Dosya hala aynı yerde olmalı
            assert log_dosya.exists()
            assert log_dosya.read_text() == "kısa log"

    def test_buyuk_dosya_rotate_edilir(self):
        """MAX_LOG_BOYUTU üstündeki dosya rotate edilmeli."""
        from log_utils import MAX_LOG_BOYUTU, _log_rotasyon

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dosya = Path(tmpdir) / "bot_log.txt"
            # MAX boyutundan büyük dosya oluştur
            log_dosya.write_text("x" * (MAX_LOG_BOYUTU + 1000))
            _log_rotasyon(log_dosya)
            # Ana dosya silinmiş (rename ile .1'e taşınmış) olmalı
            yedek = Path(tmpdir) / "bot_log.1.txt"
            assert yedek.exists()

    def test_olmayan_dosya_hata_vermez(self):
        """Olmayan dosya için rotation hata vermemeli."""
        from log_utils import _log_rotasyon

        # Var olmayan dosya — hata fırlatmamalı
        _log_rotasyon(Path("/tmp/olmayan_dosya_12345.txt"))


# ─────────────────────────────────────────────────────────────
# BÖLÜM 3: guvenli_log_yaz() TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestGuvenliLogYaz:
    """guvenli_log_yaz() fonksiyonu testleri."""

    def test_temel_log_yazma(self):
        """Log dosyasına yazılabilmeli."""
        from log_utils import guvenli_log_yaz

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dosya = Path(tmpdir) / "test.txt"
            guvenli_log_yaz("Test mesajı", log_dosya, "INFO")
            icerik = log_dosya.read_text(encoding="utf-8")
            assert "Test mesajı" in icerik
            assert "[INFO]" in icerik

    def test_log_pii_maskelenir(self):
        """Log yazarken PII maskelenmeli."""
        from log_utils import guvenli_log_yaz

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dosya = Path(tmpdir) / "test.txt"
            guvenli_log_yaz("API key: gsk_AbCdEfGhIjKlMnOpQrStUvWx", log_dosya)
            icerik = log_dosya.read_text(encoding="utf-8")
            assert "gsk_" not in icerik
            assert "***GSK_KEY***" in icerik

    def test_log_seviye_turleri(self):
        """Tüm log seviyeleri yazılabilmeli."""
        from log_utils import guvenli_log_yaz

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dosya = Path(tmpdir) / "test.txt"
            for seviye in ["INFO", "UYARI", "HATA", "GUVENLIK"]:
                guvenli_log_yaz(f"Test {seviye}", log_dosya, seviye)
            icerik = log_dosya.read_text(encoding="utf-8")
            assert "[INFO]" in icerik
            assert "[UYARI]" in icerik
            assert "[HATA]" in icerik
            assert "[GUVENLIK]" in icerik

    def test_log_zaman_damgasi_var(self):
        """Log satırında zaman damgası olmalı."""
        import re

        from log_utils import guvenli_log_yaz

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dosya = Path(tmpdir) / "test.txt"
            guvenli_log_yaz("Zaman testi", log_dosya)
            icerik = log_dosya.read_text(encoding="utf-8")
            # Format: [2026-03-03 14:30:00]
            assert re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", icerik)

    def test_log_hata_durumunda_sessiz(self):
        """Yazılamayan dosya hata fırlatmamalı."""
        from log_utils import guvenli_log_yaz

        # Geçersiz path — hata fırlatmamalı, sessiz kalmalı
        guvenli_log_yaz("test", Path("/olmayan/dizin/log.txt"))
