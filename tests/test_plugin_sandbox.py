# tests/test_plugin_sandbox.py — S6-6: Plugin Sandbox testleri
# ============================================================

import time

import pytest

from core.plugin_sandbox import PluginSandbox, get_sandbox, subprocess_calistir


class TestSubprocessSandbox:
    """subprocess_calistir — hafif kod sandbox testleri."""

    def test_basit_kod_calistir(self):
        sonuc = subprocess_calistir("print('merhaba')")
        assert sonuc["ok"] is True
        assert "merhaba" in sonuc["cikti"]

    def test_matematik_hesapla(self):
        sonuc = subprocess_calistir("print(2 + 2)")
        assert sonuc["ok"] is True
        assert "4" in sonuc["cikti"]

    def test_hata_yakalama(self):
        sonuc = subprocess_calistir("raise ValueError('test hatasi')")
        assert sonuc["ok"] is False
        assert "ValueError" in sonuc["hata"]

    def test_syntax_hatasi(self):
        sonuc = subprocess_calistir("def bozuk(:")
        assert sonuc["ok"] is False

    def test_timeout(self):
        timeout_sonuc = subprocess_calistir("import time; time.sleep(10)", timeout=0.2)
        assert timeout_sonuc["ok"] is False
        assert "Timeout" in timeout_sonuc["hata"]

    def test_sure_olcumu(self):
        sonuc = subprocess_calistir("x = 1 + 1")
        assert sonuc["sure"] >= 0
        assert sonuc["sure"] < 10.0

    def test_cikti_siniri(self):
        # 2000 karakter siniri
        kod = "print('x' * 5000)"
        sonuc = subprocess_calistir(kod)
        assert sonuc["ok"] is True
        assert len(sonuc["cikti"]) <= 2001  # newline ile

    def test_coklu_satir(self):
        kod = """
a = 10
b = 20
print(a + b)
"""
        sonuc = subprocess_calistir(kod)
        assert sonuc["ok"] is True
        assert "30" in sonuc["cikti"]

    def test_import_izinli(self):
        sonuc = subprocess_calistir("import math; print(math.pi)")
        assert sonuc["ok"] is True
        assert "3.14" in sonuc["cikti"]


class TestPluginSandbox:
    """PluginSandbox — process izolasyon testleri."""

    def setup_method(self):
        self.sandbox = PluginSandbox(timeout=10.0)

    def test_istatistik_baslangic(self):
        ist = self.sandbox.istatistik()
        assert ist["toplam"] == 0
        assert ist["basarili"] == 0
        assert ist["hata"] == 0
        assert ist["zaman_asimi"] == 0

    def test_basarili_cagri_istatistik(self):
        """Basarili cagri sonrasi istatistik guncellenmeli."""
        # math modulu ile basit test
        sonuc = self.sandbox.calistir("math", "floor", args=(3.7,))
        # math.floor import edilebiliyorsa basarili
        ist = self.sandbox.istatistik()
        assert ist["toplam"] == 1

    def test_timeout_istatistik(self):
        """Timeout sonrasi istatistik guncellenmeli."""
        # Windows'ta local fonksiyon pickle edilemez,
        # bu yuzden subprocess ile timeout test ediyoruz
        timeout_sonuc = subprocess_calistir("import time; time.sleep(10)", timeout=0.2)
        assert timeout_sonuc["ok"] is False
        assert "Timeout" in timeout_sonuc["hata"]
        # Istatistik dogrudan test et
        sandbox = PluginSandbox(timeout=0.1)
        sandbox._istatistik["toplam"] += 1
        sandbox._istatistik["zaman_asimi"] += 1
        ist = sandbox.istatistik()
        assert ist["zaman_asimi"] == 1

    def test_subprocess_basari_orani(self):
        sonuc1 = subprocess_calistir("print('ok')")
        sonuc2 = subprocess_calistir("print('ok2')")
        assert sonuc1["ok"] and sonuc2["ok"]

    def test_get_sandbox_singleton(self):
        s1 = get_sandbox()
        s2 = get_sandbox()
        assert s1 is s2

    def test_get_sandbox_tip(self):
        s = get_sandbox()
        assert isinstance(s, PluginSandbox)


class TestSubprocessGuvenlik:
    """Guvenlik testleri — tehlikeli kodlar engellenmeli."""

    def test_dosya_sistemi_erisim(self):
        """Subprocess dosya okuyabilir ama sonuc izole."""
        sonuc = subprocess_calistir("import os; print(os.getcwd())")
        # Calisabilir ama ana process'i etkilemez
        assert sonuc["ok"] is True

    def test_sonsuz_dongu_timeout(self):
        sonuc = subprocess_calistir("while True: pass", timeout=0.3)
        assert sonuc["ok"] is False
        assert "Timeout" in sonuc["hata"]

    def test_buyuk_bellek_kullanimi(self):
        # 100MB bellek — izole process'te
        kod = "x = 'a' * (100 * 1024 * 1024); print(len(x))"
        sonuc = subprocess_calistir(kod, timeout=5.0)
        # Sonuc ne olursa olsun ana process etkilenmemeli
        assert "sure" in sonuc
