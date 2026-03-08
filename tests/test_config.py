# tests/test_config.py — Merkezi Konfigürasyon Testleri
# ============================================================
# pytest -v tests/test_config.py
# ============================================================

import tempfile
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────
# BÖLÜM 1: VARSAYILAN DEĞER TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestVarsayilanDegerler:
    """CFG varsayılan değer testleri."""

    def test_cfg_dict_donmeli(self):
        """CFG bir dict olmalı."""
        from bot_config import CFG

        assert isinstance(CFG, dict)

    def test_groq_bolumu_var(self):
        """CFG'de groq bölümü olmalı."""
        from bot_config import CFG

        assert "groq" in CFG

    def test_ollama_bolumu_var(self):
        """CFG'de ollama bölümü olmalı."""
        from bot_config import CFG

        assert "ollama" in CFG
        assert "url" in CFG["ollama"]
        assert "timeout" in CFG["ollama"]

    def test_guvenlik_bolumu_var(self):
        """CFG'de guvenlik bölümü olmalı."""
        from bot_config import CFG

        assert "guvenlik" in CFG
        assert "rate_limit_pencere" in CFG["guvenlik"]
        assert "rate_limit_maksimum" in CFG["guvenlik"]

    def test_log_bolumu_var(self):
        """CFG'de log bölümü olmalı."""
        from bot_config import CFG

        assert "log" in CFG
        assert "max_boyut_mb" in CFG["log"]
        assert "max_yedek" in CFG["log"]

    def test_bot_bolumu_var(self):
        """CFG'de bot bölümü olmalı."""
        from bot_config import CFG

        assert "bot" in CFG

    def test_model_secim_bolumu_var(self):
        """CFG'de model_secim bölümü olmalı."""
        from bot_config import CFG

        assert "model_secim" in CFG
        assert "lokal_max_tokens" in CFG["model_secim"]
        assert "cloud_min_tokens" in CFG["model_secim"]

    def test_varsayilan_degerler_mantikli(self):
        """Varsayılan değerler mantıklı aralıkta olmalı."""
        from bot_config import CFG

        assert CFG["guvenlik"]["rate_limit_pencere"] > 0
        assert CFG["guvenlik"]["rate_limit_maksimum"] > 0
        assert CFG["ollama"]["timeout"] > 0
        assert CFG["log"]["max_boyut_mb"] > 0
        assert CFG["log"]["max_yedek"] >= 1


# ─────────────────────────────────────────────────────────────
# BÖLÜM 2: DERİN BİRLEŞTİRME TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestDerinBirlestirme:
    """_derin_birlestir() fonksiyonu testleri."""

    def test_bos_kullanici_varsayilan_doner(self):
        """Kullanıcı config boşsa varsayılan aynen dönmeli."""
        from bot_config import _derin_birlestir

        varsayilan = {"a": 1, "b": {"c": 2}}
        sonuc = _derin_birlestir(varsayilan, {})
        assert sonuc == {"a": 1, "b": {"c": 2}}

    def test_ust_duzey_override(self):
        """Üst düzey değerler override edilebilmeli."""
        from bot_config import _derin_birlestir

        varsayilan = {"a": 1, "b": 2}
        kullanici = {"a": 99}
        sonuc = _derin_birlestir(varsayilan, kullanici)
        assert sonuc["a"] == 99
        assert sonuc["b"] == 2

    def test_ic_ice_dict_birlestirme(self):
        """İç içe dict'ler derinlemesine birleşmeli."""
        from bot_config import _derin_birlestir

        varsayilan = {"x": {"y": 1, "z": 2}}
        kullanici = {"x": {"y": 99}}
        sonuc = _derin_birlestir(varsayilan, kullanici)
        assert sonuc["x"]["y"] == 99
        assert sonuc["x"]["z"] == 2  # varsayılan korunmalı

    def test_yeni_anahtar_eklenmeli(self):
        """Kullanıcının eklediği yeni anahtarlar gelmeli."""
        from bot_config import _derin_birlestir

        varsayilan = {"a": 1}
        kullanici = {"b": 2}
        sonuc = _derin_birlestir(varsayilan, kullanici)
        assert sonuc["a"] == 1
        assert sonuc["b"] == 2

    def test_uc_katman_derinlik(self):
        """3 katman derinlikte birleştirme çalışmalı."""
        from bot_config import _derin_birlestir

        varsayilan = {"a": {"b": {"c": 1, "d": 2}}}
        kullanici = {"a": {"b": {"c": 99}}}
        sonuc = _derin_birlestir(varsayilan, kullanici)
        assert sonuc["a"]["b"]["c"] == 99
        assert sonuc["a"]["b"]["d"] == 2


# ─────────────────────────────────────────────────────────────
# BÖLÜM 3: config_yukle() TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestConfigYukle:
    """config_yukle() fonksiyonu testleri."""

    def test_config_yukle_dict_donmeli(self):
        """config_yukle() her zaman dict dönmeli."""
        from bot_config import config_yukle

        sonuc = config_yukle()
        assert isinstance(sonuc, dict)

    def test_config_yukle_bos_donmemeli(self):
        """config_yukle() boş dict dönmemeli."""
        from bot_config import config_yukle

        sonuc = config_yukle()
        assert len(sonuc) > 0

    def test_groq_modelleri_liste(self):
        """Groq modelleri liste olmalı."""
        from bot_config import CFG

        modeller = CFG["groq"]["models"]
        assert isinstance(modeller, list)
        assert len(modeller) > 0

    def test_task_model_pref_dict(self):
        """Task model tercihleri dict olmalı."""
        from bot_config import CFG

        prefs = CFG["groq"]["task_model_pref"]
        assert isinstance(prefs, dict)
        assert "kod" in prefs
        assert "sohbet" in prefs
