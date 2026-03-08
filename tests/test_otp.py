# tests/test_otp.py — OTP Onay Sistemi & Risk Sınıfı Testleri
# ============================================================
# pytest -v tests/test_otp.py
# ============================================================

import time

import pytest

# ─────────────────────────────────────────────────────────────
# BÖLÜM 1: OTP ÜRETİM VE DOĞRULAMA TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestOTPYonetici:
    """OTPYonetici sınıfı testleri."""

    def _yeni_otp(self):
        from pyautogui_plugin import OTPYonetici

        return OTPYonetici()

    def test_otp_uret_6_karakter(self):
        """OTP kodu 6 hex karakter olmalı."""
        otp = self._yeni_otp()
        sonuc = otp.otp_uret("test işlemi")
        assert len(sonuc["kod"]) == 6
        # Hex karakter kontrolü
        int(sonuc["kod"], 16)  # Hata fırlatırsa hex değildir

    def test_otp_uret_her_seferinde_farkli(self):
        """Her üretimde farklı kod gelmeli."""
        otp = self._yeni_otp()
        kod1 = otp.otp_uret("test1")["kod"]
        kod2 = otp.otp_uret("test2")["kod"]
        # Çok düşük ihtimalle aynı olabilir ama pratikte farklı
        # 16^6 = 16.7M olasılık — güvenli test
        # Birden fazla deneme ile kontrol
        kodlar = {otp.otp_uret(f"test{i}")["kod"] for i in range(10)}
        assert len(kodlar) > 1  # En az 2 farklı kod

    def test_otp_dogrula_dogru_kod(self):
        """Doğru kod ile onay geçmeli."""
        otp = self._yeni_otp()
        sonuc = otp.otp_uret("program_ac notepad")
        dogrulama = otp.otp_dogrula(sonuc["kod"])
        assert dogrulama["gecerli"] is True
        assert "Onaylandi" in dogrulama["sebep"]

    def test_otp_dogrula_yanlis_kod(self):
        """Yanlış kod ile onay reddedilmeli."""
        otp = self._yeni_otp()
        otp.otp_uret("test")
        dogrulama = otp.otp_dogrula("ffffff")
        assert dogrulama["gecerli"] is False
        assert "Yanlis" in dogrulama["sebep"]

    def test_otp_tek_kullanimlik(self):
        """OTP kullanıldıktan sonra tekrar kullanılamamalı."""
        otp = self._yeni_otp()
        sonuc = otp.otp_uret("test")
        kod = sonuc["kod"]

        # İlk doğrulama geçmeli
        d1 = otp.otp_dogrula(kod)
        assert d1["gecerli"] is True

        # İkinci doğrulama başarısız olmalı
        d2 = otp.otp_dogrula(kod)
        assert d2["gecerli"] is False
        assert "Bekleyen" in d2["sebep"]

    def test_otp_yanlis_koddan_sonra_temizlenir(self):
        """Yanlış kod girilince OTP temizlenmeli (tek deneme)."""
        otp = self._yeni_otp()
        sonuc = otp.otp_uret("test")
        dogru_kod = sonuc["kod"]

        # Yanlış kod gir
        otp.otp_dogrula("000000")

        # Artık doğru kod da çalışmamalı
        d = otp.otp_dogrula(dogru_kod)
        assert d["gecerli"] is False

    def test_otp_timeout(self):
        """Süre aşımında OTP geçersiz olmalı."""
        otp = self._yeni_otp()
        sonuc = otp.otp_uret("test")
        kod = sonuc["kod"]

        # Zamanı geçmişe çek (timeout simülasyonu)
        otp._bekleyen_otp["zaman"] = time.time() - 31  # 31 saniye önce

        dogrulama = otp.otp_dogrula(kod)
        assert dogrulama["gecerli"] is False
        assert "suresi doldu" in dogrulama["sebep"]

    def test_bekleyen_var_mi_true(self):
        """Bekleyen OTP varsa True dönmeli."""
        otp = self._yeni_otp()
        otp.otp_uret("test")
        assert otp.bekleyen_var_mi() is True

    def test_bekleyen_var_mi_false(self):
        """Bekleyen OTP yoksa False dönmeli."""
        otp = self._yeni_otp()
        assert otp.bekleyen_var_mi() is False

    def test_bekleyen_var_mi_timeout_sonrasi(self):
        """Timeout sonrası bekleyen False olmalı."""
        otp = self._yeni_otp()
        otp.otp_uret("test")
        otp._bekleyen_otp["zaman"] = time.time() - 31
        assert otp.bekleyen_var_mi() is False

    def test_iptal(self):
        """İptal sonrası bekleyen temizlenmeli."""
        otp = self._yeni_otp()
        otp.otp_uret("test")
        otp.iptal()
        assert otp.bekleyen_var_mi() is False

    def test_bekleyen_yokken_dogrulama(self):
        """Bekleyen OTP yokken doğrulama başarısız olmalı."""
        otp = self._yeni_otp()
        d = otp.otp_dogrula("abc123")
        assert d["gecerli"] is False

    def test_otp_case_insensitive(self):
        """OTP doğrulama büyük/küçük harf duyarsız olmalı."""
        otp = self._yeni_otp()
        sonuc = otp.otp_uret("test")
        kod = sonuc["kod"]
        # Büyük harfle gönder
        dogrulama = otp.otp_dogrula(kod.upper())
        assert dogrulama["gecerli"] is True

    def test_otp_bosluk_trim(self):
        """OTP doğrulamada boşluklar temizlenmeli."""
        otp = self._yeni_otp()
        sonuc = otp.otp_uret("test")
        kod = sonuc["kod"]
        dogrulama = otp.otp_dogrula(f"  {kod}  ")
        assert dogrulama["gecerli"] is True


# ─────────────────────────────────────────────────────────────
# BÖLÜM 2: RISK SEVİYESİ TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestRiskSeviyeleri:
    """Risk sınıflandırma testleri."""

    def test_tikla_low_risk(self):
        from pyautogui_plugin import risk_seviyesi_al

        assert risk_seviyesi_al("tikla") == "low"

    def test_yaz_medium_risk(self):
        from pyautogui_plugin import risk_seviyesi_al

        assert risk_seviyesi_al("yaz") == "medium"

    def test_tus_bas_medium_risk(self):
        from pyautogui_plugin import risk_seviyesi_al

        assert risk_seviyesi_al("tus_bas") == "medium"

    def test_program_ac_high_risk(self):
        from pyautogui_plugin import risk_seviyesi_al

        assert risk_seviyesi_al("program_ac") == "high"

    def test_web_git_high_risk(self):
        from pyautogui_plugin import risk_seviyesi_al

        assert risk_seviyesi_al("web_git") == "high"

    def test_otomasyon_critical_risk(self):
        from pyautogui_plugin import risk_seviyesi_al

        assert risk_seviyesi_al("otomasyon") == "critical"

    def test_bilinmeyen_komut_high_varsayilan(self):
        """Bilinmeyen komutlar high risk kabul edilmeli."""
        from pyautogui_plugin import risk_seviyesi_al

        assert risk_seviyesi_al("bilinmeyen_komut") == "high"

    def test_otp_gerekli_high_ve_critical(self):
        """High ve critical komutlar OTP gerektirmeli."""
        from pyautogui_plugin import otp_gerekli_mi

        assert otp_gerekli_mi("program_ac") is True
        assert otp_gerekli_mi("web_git") is True
        assert otp_gerekli_mi("otomasyon") is True

    def test_otp_gerekli_degil_low_medium(self):
        """Low ve medium komutlar OTP gerektirmemeli."""
        from pyautogui_plugin import otp_gerekli_mi

        assert otp_gerekli_mi("tikla") is False
        assert otp_gerekli_mi("yaz") is False
        assert otp_gerekli_mi("tus_bas") is False


# ─────────────────────────────────────────────────────────────
# BÖLÜM 3: URL & PROGRAM GÜVENLİK TESTLERİ
# ─────────────────────────────────────────────────────────────


class TestURLveProgram:
    """URL ve program güvenlik doğrulama testleri."""

    def test_guvenli_url(self):
        from pyautogui_plugin import _guvenli_url_mi

        assert _guvenli_url_mi("https://www.google.com") is True
        assert _guvenli_url_mi("http://example.com/path?q=test") is True

    def test_tehlikeli_url_shell_karakterleri(self):
        from pyautogui_plugin import _guvenli_url_mi

        assert _guvenli_url_mi("http://evil.com; rm -rf /") is False
        assert _guvenli_url_mi("http://evil.com | cat /etc/passwd") is False
        assert _guvenli_url_mi("http://evil.com`whoami`") is False

    def test_bos_url(self):
        from pyautogui_plugin import _guvenli_url_mi

        assert _guvenli_url_mi("") is False
        assert _guvenli_url_mi(None) is False

    def test_http_olmayan_url(self):
        from pyautogui_plugin import _guvenli_url_mi

        assert _guvenli_url_mi("ftp://files.com") is False
        assert _guvenli_url_mi("javascript:alert(1)") is False

    def test_cok_uzun_url(self):
        from pyautogui_plugin import _guvenli_url_mi

        assert _guvenli_url_mi("https://x.com/" + "a" * 3000) is False

    def test_guvenli_program(self):
        from pyautogui_plugin import _guvenli_program_mi

        assert _guvenli_program_mi("notepad") is True
        assert _guvenli_program_mi("calc.exe") is True
        assert _guvenli_program_mi("chrome") is True

    def test_yasakli_program(self):
        from pyautogui_plugin import _guvenli_program_mi

        assert _guvenli_program_mi("powershell") is False
        assert _guvenli_program_mi("cmd.exe") is False
        assert _guvenli_program_mi("regedit") is False

    def test_path_injection_program(self):
        from pyautogui_plugin import _guvenli_program_mi

        assert _guvenli_program_mi("notepad; rm -rf /") is False
        assert _guvenli_program_mi("..\\..\\system32\\cmd.exe") is False
        assert _guvenli_program_mi("notepad && whoami") is False
