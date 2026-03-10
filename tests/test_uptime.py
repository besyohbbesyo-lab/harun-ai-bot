# tests/test_uptime.py — F3-D: Uptime persistence testleri
# pytest -v tests/test_uptime.py

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


class TestUptimePersistence:
    """baslangic_zamanini_kaydet ve uptime_hesapla disk persistence testleri."""

    def test_kaydet_dosyaya_yazar(self, tmp_path, monkeypatch):
        """baslangic_zamanini_kaydet() uptime.json dosyasini olusturur."""
        from core import config

        dosya = tmp_path / "uptime.json"
        monkeypatch.setattr(config, "_UPTIME_DOSYA", dosya)
        monkeypatch.setattr(config, "BASLANGIC_ZAMANI", None)

        config.baslangic_zamanini_kaydet()

        assert dosya.exists()
        veri = json.loads(dosya.read_text(encoding="utf-8"))
        assert "baslangic" in veri
        # Parse edilebilir olmali
        datetime.fromisoformat(veri["baslangic"])

    def test_hesapla_diskten_okur(self, tmp_path, monkeypatch):
        """BASLANGIC_ZAMANI None iken uptime_hesapla diskten okur."""
        from core import config

        dosya = tmp_path / "uptime.json"
        # 2 saat once yazilmis gibi kaydet
        sahte_zaman = datetime.now() - timedelta(hours=2, minutes=15)
        dosya.write_text(
            json.dumps({"baslangic": sahte_zaman.isoformat()}), encoding="utf-8"
        )

        monkeypatch.setattr(config, "_UPTIME_DOSYA", dosya)
        monkeypatch.setattr(config, "BASLANGIC_ZAMANI", None)

        sonuc = config.uptime_hesapla()
        assert "2 saat" in sonuc
        assert "dakika" in sonuc

    def test_dosya_yoksa_bilinmiyor_doner(self, tmp_path, monkeypatch):
        """Disk dosyasi yoksa ve bellek None ise 'Bilinmiyor' doner."""
        from core import config

        dosya = tmp_path / "olmayan_uptime.json"
        monkeypatch.setattr(config, "_UPTIME_DOSYA", dosya)
        monkeypatch.setattr(config, "BASLANGIC_ZAMANI", None)

        sonuc = config.uptime_hesapla()
        assert sonuc == "Bilinmiyor"

    def test_bellekte_varsa_dosyaya_basvurmaz(self, monkeypatch):
        """BASLANGIC_ZAMANI bellekte doluysa diskten okuma yapilmaz."""
        from core import config

        bellekteki = datetime.now() - timedelta(hours=1, minutes=30)
        monkeypatch.setattr(config, "BASLANGIC_ZAMANI", bellekteki)

        sonuc = config.uptime_hesapla()
        assert "1 saat" in sonuc
        assert "30 dakika" in sonuc

    def test_bozuk_dosya_sessizce_gecilir(self, tmp_path, monkeypatch):
        """Bozuk JSON dosyasi varsa exception yutulur, 'Bilinmiyor' doner."""
        from core import config

        dosya = tmp_path / "uptime.json"
        dosya.write_text("BOZUK JSON {{{", encoding="utf-8")

        monkeypatch.setattr(config, "_UPTIME_DOSYA", dosya)
        monkeypatch.setattr(config, "BASLANGIC_ZAMANI", None)

        sonuc = config.uptime_hesapla()
        assert sonuc == "Bilinmiyor"

    def test_kaydet_ve_oku_roundtrip(self, tmp_path, monkeypatch):
        """Kaydet → bellek sifirla → hesapla roundtrip calismali."""
        from core import config

        dosya = tmp_path / "uptime.json"
        monkeypatch.setattr(config, "_UPTIME_DOSYA", dosya)
        monkeypatch.setattr(config, "BASLANGIC_ZAMANI", None)

        # Kaydet
        config.baslangic_zamanini_kaydet()
        kaydedilen = config.BASLANGIC_ZAMANI

        # Bellegi sifirla (restart simulasyonu)
        monkeypatch.setattr(config, "BASLANGIC_ZAMANI", None)

        # Hesapla — diskten okumali
        sonuc = config.uptime_hesapla()
        assert "0 saat" in sonuc
        assert config.BASLANGIC_ZAMANI is not None
