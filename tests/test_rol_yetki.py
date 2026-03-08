# tests/test_rol_yetki.py — rol_yetki modülü testleri
# pytest -v tests/test_rol_yetki.py

import os

import pytest


class TestRolAl:
    def test_tanimli_admin(self):
        from rol_yetki import rol_al, rol_ata

        rol_ata(1001, "admin")
        assert rol_al(1001) == "admin"

    def test_tanimli_user(self):
        from rol_yetki import rol_al, rol_ata

        rol_ata(1002, "user")
        assert rol_al(1002) == "user"

    def test_tanimli_readonly(self):
        from rol_yetki import rol_al, rol_ata

        rol_ata(1003, "readonly")
        assert rol_al(1003) == "readonly"

    def test_tanimsiz_varsayilan_admin(self):
        from rol_yetki import rol_al

        # Hiç atanmamış kullanıcı admin olmalı (geriye uyumluluk)
        assert rol_al(999999999) == "admin"


class TestKomutIzinliMi:
    def setup_method(self):
        from rol_yetki import rol_ata

        rol_ata(2001, "admin")
        rol_ata(2002, "user")
        rol_ata(2003, "readonly")

    def test_admin_her_komutu_calistirir(self):
        from rol_yetki import komut_izinli_mi

        assert komut_izinli_mi(2001, "status") is True
        assert komut_izinli_mi(2001, "guvenlik") is True
        assert komut_izinli_mi(2001, "egitim") is True
        assert komut_izinli_mi(2001, "herhangi_komut") is True

    def test_user_izinli_komutlar(self):
        from rol_yetki import komut_izinli_mi

        assert komut_izinli_mi(2002, "status") is True
        assert komut_izinli_mi(2002, "ara") is True
        assert komut_izinli_mi(2002, "pdf") is True
        assert komut_izinli_mi(2002, "kod") is True
        assert komut_izinli_mi(2002, "plan") is True

    def test_user_sohbet_izni(self):
        from rol_yetki import komut_izinli_mi

        assert komut_izinli_mi(2002, "sohbet") is True
        assert komut_izinli_mi(2002, "sesli_mesaj") is True

    def test_user_yasakli_komutlar(self):
        from rol_yetki import komut_izinli_mi

        assert komut_izinli_mi(2002, "guvenlik") is False
        assert komut_izinli_mi(2002, "egitim") is False

    def test_readonly_sadece_temel(self):
        from rol_yetki import komut_izinli_mi

        assert komut_izinli_mi(2003, "status") is True
        assert komut_izinli_mi(2003, "help") is True
        assert komut_izinli_mi(2003, "start") is True

    def test_readonly_sohbet_izinsiz(self):
        from rol_yetki import komut_izinli_mi

        assert komut_izinli_mi(2003, "sohbet") is False
        assert komut_izinli_mi(2003, "ara") is False
        assert komut_izinli_mi(2003, "kod") is False


class TestRolAta:
    def test_gecerli_rol_atama(self):
        from rol_yetki import rol_al, rol_ata

        assert rol_ata(3001, "user") is True
        assert rol_al(3001) == "user"

    def test_gecersiz_rol_reddedilir(self):
        from rol_yetki import rol_ata

        assert rol_ata(3002, "superuser") is False
        assert rol_ata(3003, "") is False
        assert rol_ata(3004, "yonetici") is False

    def test_rol_degistirme(self):
        from rol_yetki import rol_al, rol_ata

        rol_ata(3005, "readonly")
        assert rol_al(3005) == "readonly"
        rol_ata(3005, "admin")
        assert rol_al(3005) == "admin"


class TestRolKaldir:
    def test_rol_kaldirma(self):
        from rol_yetki import rol_al, rol_ata, rol_kaldir

        rol_ata(4001, "user")
        assert rol_kaldir(4001) is True
        assert rol_al(4001) == "admin"  # varsayılana döner

    def test_olmayan_kullanici_kaldir(self):
        from rol_yetki import rol_kaldir

        assert rol_kaldir(999888777) is False


class TestDurumOzeti:
    def test_ozet_str_donmeli(self):
        from rol_yetki import durum_ozeti

        ozet = durum_ozeti()
        assert isinstance(ozet, str)
        assert len(ozet) > 0

    def test_ozet_roller_iceriyor(self):
        from rol_yetki import durum_ozeti, rol_ata

        rol_ata(5001, "admin")
        ozet = durum_ozeti()
        assert "admin" in ozet
