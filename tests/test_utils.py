# tests/test_utils.py — core/utils.py testleri
# pytest -v tests/test_utils.py

import os
import tempfile
from pathlib import Path

import pytest


class TestNormalizeProvider:
    def test_none_varsayilan_doner(self):
        from core.utils import normalize_provider

        p = normalize_provider(None)
        assert "name" in p
        assert "mode" in p
        assert p["mode"] == "cloud"

    def test_bos_dict_varsayilan_doner(self):
        from core.utils import normalize_provider

        p = normalize_provider({})
        assert "name" in p
        assert "mode" in p

    def test_isim_name_donusumu(self):
        from core.utils import normalize_provider

        p = normalize_provider({"isim": "Groq", "mode": "cloud"})
        assert p["name"] == "Groq"
        assert "isim" not in p

    def test_name_varsa_degismez(self):
        from core.utils import normalize_provider

        p = normalize_provider({"name": "Gemini", "mode": "cloud"})
        assert p["name"] == "Gemini"

    def test_mode_yoksa_eklenir(self):
        from core.utils import normalize_provider

        p = normalize_provider({"name": "Groq"})
        assert p["mode"] == "cloud"

    def test_orijinal_bozulmaz(self):
        from core.utils import normalize_provider

        orijinal = {"isim": "Groq", "mode": "cloud"}
        normalize_provider(orijinal)
        assert "isim" in orijinal  # orijinal değişmemeli

    def test_ekstra_alanlar_korunur(self):
        from core.utils import normalize_provider

        p = normalize_provider({"name": "Groq", "mode": "cloud", "model": "llama-3"})
        assert p["model"] == "llama-3"


class TestSonDosyayiBul:
    def test_dosya_bulur(self, tmp_path):
        from core.utils import son_dosyayi_bul

        (tmp_path / "rapor.pdf").write_text("test")
        sonuc = son_dosyayi_bul(tmp_path, "pdf")
        assert sonuc is not None
        assert sonuc.suffix == ".pdf"

    def test_en_yeni_doner(self, tmp_path):
        import time

        from core.utils import son_dosyayi_bul

        (tmp_path / "eski.pdf").write_text("eski")
        time.sleep(0.05)
        (tmp_path / "yeni.pdf").write_text("yeni")
        sonuc = son_dosyayi_bul(tmp_path, "pdf")
        assert sonuc.name == "yeni.pdf"

    def test_prefix_filtreler(self, tmp_path):
        from core.utils import son_dosyayi_bul

        (tmp_path / "rapor_2024.pdf").write_text("rapor")
        (tmp_path / "fatura_2024.pdf").write_text("fatura")
        sonuc = son_dosyayi_bul(tmp_path, "pdf", prefix="rapor")
        assert sonuc.name == "rapor_2024.pdf"

    def test_dosya_yoksa_none(self, tmp_path):
        from core.utils import son_dosyayi_bul

        sonuc = son_dosyayi_bul(tmp_path, "pdf")
        assert sonuc is None

    def test_olmayan_dizin_none(self):
        from core.utils import son_dosyayi_bul

        sonuc = son_dosyayi_bul(Path("/olmayan/dizin"), "pdf")
        assert sonuc is None

    def test_prefix_eslesme_yoksa_none(self, tmp_path):
        from core.utils import son_dosyayi_bul

        (tmp_path / "fatura.pdf").write_text("f")
        sonuc = son_dosyayi_bul(tmp_path, "pdf", prefix="rapor")
        assert sonuc is None


class TestLogYaz:
    def test_hata_vermez(self):
        from core.utils import log_yaz

        # Hata fırlatmamalı
        log_yaz("test mesajı")
        log_yaz("hata mesajı", "ERROR")
        log_yaz("uyarı", "WARN")

    def test_log_dosyasiz_calisir(self):
        from core.utils import log_yaz, set_log_dosyasi

        set_log_dosyasi(None)
        log_yaz("log dosyası yok")  # hata fırlatmamalı
