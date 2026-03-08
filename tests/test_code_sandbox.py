# tests/test_code_sandbox.py — Code Sandbox Güvenlik Testleri
# ============================================================
# pytest -v tests/test_code_sandbox.py
# ============================================================

import pytest

# ─────────────────────────────────────────────────────────────
# BÖLÜM 1: AST DOĞRULAMA TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestASTDogrulama:
    """CodeRunner._validate_ast() testleri."""

    def _runner(self):
        from code_plugin import CodeRunner

        return CodeRunner()

    # --- Temiz kodlar (geçmeli) ---

    @pytest.mark.parametrize(
        "kod",
        [
            "print('Merhaba')",
            "x = 2 + 2\nprint(x)",
            "for i in range(10):\n    print(i)",
            "def topla(a, b):\n    return a + b\nprint(topla(3, 5))",
            "sayilar = [1, 2, 3]\nprint(sum(sayilar))",
            "import math\nprint(math.pi)",
            "import json\nprint(json.dumps({'a': 1}))",
        ],
    )
    def test_temiz_kod_gecmeli(self, kod):
        """Güvenli kodlar AST doğrulamasından geçmeli."""
        runner = self._runner()
        # Hata fırlatmazsa geçti demektir
        runner._validate_ast(kod)

    # --- Yasaklı import'lar (engellenmeli) ---

    @pytest.mark.parametrize(
        "kod,modul",
        [
            ("import os", "os"),
            ("import subprocess", "subprocess"),
            ("import socket", "socket"),
            ("import shutil", "shutil"),
            ("from os import system", "os"),
            ("from subprocess import call", "subprocess"),
            ("import pickle", "pickle"),
            ("from urllib import request", "urllib"),
            ("import requests", "requests"),
            ("import ctypes", "ctypes"),
            ("import sys", "sys"),
        ],
    )
    def test_yasakli_import_engellenmeli(self, kod, modul):
        """Yasaklı modül import'ları engellenmeli."""
        runner = self._runner()
        with pytest.raises(ValueError, match="import yasak"):
            runner._validate_ast(kod)

    # --- Yasaklı fonksiyon çağrıları (engellenmeli) ---

    @pytest.mark.parametrize(
        "kod,fonk",
        [
            ("open('dosya.txt')", "open"),
            ("eval('2+2')", "eval"),
            ("exec('print(1)')", "exec"),
            ("compile('x=1', '', 'exec')", "compile"),
            ("__import__('os')", "__import__"),
            ("breakpoint()", "breakpoint"),
        ],
    )
    def test_yasakli_cagri_engellenmeli(self, kod, fonk):
        """Yasaklı fonksiyon çağrıları engellenmeli."""
        runner = self._runner()
        with pytest.raises(ValueError, match="yasak"):
            runner._validate_ast(kod)

    # --- Yasaklı dunder attribute'lar ---

    @pytest.mark.parametrize(
        "kod",
        [
            "x.__class__",
            "x.__subclasses__()",
            "x.__globals__",
            "x.__code__",
            "x.__dict__",
        ],
    )
    def test_yasakli_dunder_engellenmeli(self, kod):
        """Yasaklı dunder attribute erişimleri engellenmeli."""
        runner = self._runner()
        # "x" tanımsız olsa da AST parse edebilir
        with pytest.raises(ValueError, match="yasak"):
            runner._validate_ast(f"x = 1\n{kod}")

    # --- Syntax hatası ---

    def test_syntax_hatasi(self):
        """Syntax hatası olan kod reddedilmeli."""
        runner = self._runner()
        with pytest.raises(ValueError, match="AST analiz hatasi"):
            runner._validate_ast("def f(\n")


# ─────────────────────────────────────────────────────────────
# BÖLÜM 2: GİRDİ LİMİT TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestGirdiLimitleri:
    """CodeRunner._validate_limits() testleri."""

    def _runner(self):
        from code_plugin import CodeRunner

        return CodeRunner()

    def test_bos_kod_reddedilmeli(self):
        """Boş kod reddedilmeli."""
        runner = self._runner()
        with pytest.raises(ValueError, match="bos"):
            runner._validate_limits("")

    def test_sadece_bosluk_reddedilmeli(self):
        """Sadece boşluk olan kod reddedilmeli."""
        runner = self._runner()
        with pytest.raises(ValueError, match="bos"):
            runner._validate_limits("   \n  \n  ")

    def test_cok_uzun_kod_reddedilmeli(self):
        """MAX_CHARS'dan uzun kod reddedilmeli."""
        runner = self._runner()
        uzun_kod = "x = 1\n" * 2000  # 5000+ karakter
        with pytest.raises(ValueError, match="uzun"):
            runner._validate_limits(uzun_kod)

    def test_cok_satirli_kod_reddedilmeli(self):
        """MAX_LINES'dan fazla satır reddedilmeli."""
        runner = self._runner()
        cok_satir = "\n".join(f"x{i} = {i}" for i in range(250))
        with pytest.raises(ValueError, match="satirli"):
            runner._validate_limits(cok_satir)

    def test_null_byte_reddedilmeli(self):
        """NUL byte içeren kod reddedilmeli."""
        runner = self._runner()
        with pytest.raises(ValueError, match="NUL"):
            runner._validate_limits("print('test')\x00")

    def test_normal_kod_gecmeli(self):
        """Normal uzunlukta kod geçmeli."""
        runner = self._runner()
        # Hata fırlatmazsa geçti
        runner._validate_limits("print('merhaba')")


# ─────────────────────────────────────────────────────────────
# BÖLÜM 3: KOD TEMİZLEME TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestSanitizeCode:
    """CodeRunner._sanitize_code() testleri."""

    def _runner(self):
        from code_plugin import CodeRunner

        return CodeRunner()

    def test_markdown_fence_temizleme(self):
        """```python fences temizlenmeli."""
        runner = self._runner()
        kod = "```python\nprint('test')\n```"
        sonuc = runner._sanitize_code(kod)
        assert "```" not in sonuc
        assert "print('test')" in sonuc

    def test_bos_kod(self):
        """Boş kod boş dönmeli."""
        runner = self._runner()
        assert runner._sanitize_code("") == ""
        assert runner._sanitize_code(None) == ""

    def test_ok_satir_temizleme(self):
        """[OK] ile başlayan satırlar temizlenmeli."""
        runner = self._runner()
        kod = "[OK] Güvenli\nprint('test')"
        sonuc = runner._sanitize_code(kod)
        assert "[OK]" not in sonuc
        assert "print('test')" in sonuc

    def test_newline_normalizasyon(self):
        """\\r\\n ve \\r normalize edilmeli."""
        runner = self._runner()
        kod = "x = 1\r\ny = 2\rz = 3"
        sonuc = runner._sanitize_code(kod)
        assert "\r" not in sonuc
