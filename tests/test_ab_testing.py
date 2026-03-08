# tests/test_ab_testing.py
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import core.ab_testing as ab_mod
from core.ab_testing import (
    ABTestMotoru,
    Varyant,
    VaryantSonuc,
    ab_persistence_ayarla,
    ab_test_al_veya_olustur,
    kullaniciyi_varyanta_zorla,
    testleri_sifirla,
    tum_testler_istatistik,
    tum_testleri_kaydet,
    tum_testleri_yukle,
    tum_testleri_yuklemeyi_dene,
)


@pytest.fixture(autouse=True)
def temizle():
    """Her testten önce global kayıtcıyı sıfırla."""
    testleri_sifirla()
    ab_mod._AB_PERSISTENCE_YOLU = None
    ab_mod._AB_OTOMATIK_KAYDET = False
    yield
    testleri_sifirla()
    ab_mod._AB_PERSISTENCE_YOLU = None
    ab_mod._AB_OTOMATIK_KAYDET = False


# --- Varyant ve VaryantSonuc ---


def test_varyant_olustur():
    v = Varyant(ad="A", agirlik=0.6)
    assert v.ad == "A"
    assert v.aktif is True


def test_varyant_sonuc_olustur():
    s = VaryantSonuc(varyant_adi="A", kullanici_id="u1", basarili=True, sure_ms=100.0)
    assert s.varyant_adi == "A"
    assert s.basarili is True


# --- ab_persistence_ayarla ---


def test_ab_persistence_ayarla(tmp_path):
    yol = tmp_path / "ab.json"
    ab_persistence_ayarla(yol, otomatik_kaydet=True)
    assert ab_mod._AB_PERSISTENCE_YOLU == yol
    assert ab_mod._AB_OTOMATIK_KAYDET is True


# --- _otomatik_kaydet_yap ---


def test_otomatik_kaydet_pasif():
    # _AB_OTOMATIK_KAYDET=False iken sessizce geçmeli
    ab_mod._AB_OTOMATIK_KAYDET = False
    ab_mod._otomatik_kaydet_yap()  # hata çıkmamalı


def test_otomatik_kaydet_aktif(tmp_path):
    yol = tmp_path / "ab.json"
    ab_mod._AB_OTOMATIK_KAYDET = True
    ab_mod._AB_PERSISTENCE_YOLU = yol
    ab_test_al_veya_olustur("test1")
    ab_mod._otomatik_kaydet_yap()
    assert yol.exists()


def test_otomatik_kaydet_hata_toleransi(tmp_path):
    ab_mod._AB_OTOMATIK_KAYDET = True
    ab_mod._AB_PERSISTENCE_YOLU = tmp_path / "ab.json"
    with patch("core.ab_testing.tum_testleri_kaydet", side_effect=Exception("disk hatası")):
        ab_mod._otomatik_kaydet_yap()  # hata fırlatmamalı


# --- tum_testleri_yuklemeyi_dene ---


def test_yuklemeyi_dene_dosya_yok():
    result = tum_testleri_yuklemeyi_dene("/olmayan/yol.json")
    assert result is False


def test_yuklemeyi_dene_yol_none():
    result = tum_testleri_yuklemeyi_dene(None)
    assert result is False


def test_yuklemeyi_dene_basarili(tmp_path):
    yol = tmp_path / "ab.json"
    motor = ABTestMotoru("test1")
    motor._varyantlar.append(Varyant(ad="A"))
    yol.write_text(json.dumps({"test1": motor.to_dict()}), encoding="utf-8")
    result = tum_testleri_yuklemeyi_dene(yol)
    assert result is True


def test_yuklemeyi_dene_bozuk_dosya(tmp_path):
    yol = tmp_path / "ab.json"
    yol.write_text("bozuk json {{{", encoding="utf-8")
    result = tum_testleri_yuklemeyi_dene(yol)
    assert result is False


# --- ABTestMotoru temel işlemler ---


def test_varyant_ekle():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    assert len(motor._varyantlar) == 1


def test_varyant_sec_deterministik():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A", agirlik=0.5))
    motor.varyant_ekle(Varyant(ad="B", agirlik=0.5))
    v1 = motor.varyant_sec("kullanici1")
    v2 = motor.varyant_sec("kullanici1")
    assert v1.ad == v2.ad  # aynı kullanıcı → aynı varyant


def test_varyant_sec_onceden_atanmis():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    motor.varyant_ekle(Varyant(ad="B"))
    v1 = motor.varyant_sec("u1")
    v2 = motor.varyant_sec("u1")
    assert v1.ad == v2.ad


def test_varyant_sec_aktif_yok():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A", aktif=False))
    with pytest.raises(ValueError):
        motor.varyant_sec("u1")


def test_varyant_sec_tek_varyant():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A", agirlik=1.0))
    v = motor.varyant_sec("herhangi")
    assert v.ad == "A"


def test_sonuc_kaydet():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    s = VaryantSonuc(varyant_adi="A", kullanici_id="u1", basarili=True, sure_ms=50.0)
    motor.sonuc_kaydet(s)
    assert len(motor._sonuclar) == 1


# --- istatistik ---


def test_istatistik_bos_varyant():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    ist = motor.istatistik()
    assert ist["varyantlar"]["A"]["toplam"] == 0


def test_istatistik_sonuclu():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    motor.sonuc_kaydet(VaryantSonuc("A", "u1", True, 100.0))
    motor.sonuc_kaydet(VaryantSonuc("A", "u2", False, 200.0))
    ist = motor.istatistik()
    assert ist["varyantlar"]["A"]["toplam"] == 2
    assert ist["varyantlar"]["A"]["basari_orani"] == 0.5


# --- kazanan ---


def test_kazanan_yetersiz_veri():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    assert motor.kazanan() is None


def test_kazanan_yeterli_veri():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    motor.varyant_ekle(Varyant(ad="B"))
    for i in range(10):
        motor.sonuc_kaydet(VaryantSonuc("A", f"u{i}", True, 100.0))
    for i in range(10):
        motor.sonuc_kaydet(VaryantSonuc("B", f"u{i+10}", False, 100.0))
    k = motor.kazanan()
    assert k is not None
    assert k.ad == "A"


# --- varyant_devre_disi_birak ---


def test_varyant_devre_disi_birak():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    motor.varyant_devre_disi_birak("A")
    assert motor._varyantlar[0].aktif is False


# --- to_dict / from_dict ---


def test_to_dict_from_dict():
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    d = motor.to_dict()
    motor2 = ABTestMotoru.from_dict(d)
    assert motor2.test_adi == "test"
    assert len(motor2._varyantlar) == 1


def test_from_dict_test_adi_yok():
    with pytest.raises(ValueError):
        ABTestMotoru.from_dict({"varyantlar": []})


def test_from_dict_dict_degil():
    with pytest.raises(ValueError):
        ABTestMotoru.from_dict("bozuk")


# --- kaydet / yukle ---


def test_kaydet_yukle(tmp_path):
    yol = tmp_path / "motor.json"
    motor = ABTestMotoru("test")
    motor.varyant_ekle(Varyant(ad="A"))
    motor.kaydet(yol)
    motor2 = ABTestMotoru.yukle(yol)
    assert motor2.test_adi == "test"


# --- global fonksiyonlar ---


def test_ab_test_al_veya_olustur_yeni():
    motor = ab_test_al_veya_olustur("yeni_test")
    assert motor.test_adi == "yeni_test"


def test_ab_test_al_veya_olustur_mevcut():
    m1 = ab_test_al_veya_olustur("test")
    m2 = ab_test_al_veya_olustur("test")
    assert m1 is m2


def test_tum_testler_istatistik():
    ab_test_al_veya_olustur("t1")
    ab_test_al_veya_olustur("t2")
    ist = tum_testler_istatistik()
    assert "t1" in ist
    assert "t2" in ist


def test_tum_testleri_kaydet_yukle(tmp_path):
    yol = tmp_path / "tum.json"
    motor = ab_test_al_veya_olustur("test")
    motor.varyant_ekle(Varyant(ad="A"))
    tum_testleri_kaydet(yol)
    testleri_sifirla()
    tum_testleri_yukle(yol)
    assert "test" in ab_mod._testler


def test_tum_testleri_yukle_bozuk_veri(tmp_path):
    yol = tmp_path / "bozuk.json"
    yol.write_text('"string veri"', encoding="utf-8")
    with pytest.raises(ValueError):
        tum_testleri_yukle(yol)


def test_testleri_sifirla():
    ab_test_al_veya_olustur("t1")
    testleri_sifirla()
    assert len(ab_mod._testler) == 0


# --- kullaniciyi_varyanta_zorla ---


def test_kullaniciyi_varyanta_zorla_basarili():
    motor = ab_test_al_veya_olustur("test")
    motor.varyant_ekle(Varyant(ad="A"))
    kullaniciyi_varyanta_zorla("test", "u1", "A")
    assert motor._kullanici_atama["u1"] == "A"


def test_kullaniciyi_varyanta_zorla_varyant_yok():
    ab_test_al_veya_olustur("test")
    with pytest.raises(ValueError):
        kullaniciyi_varyanta_zorla("test", "u1", "OLMAYAN")


def test_kullaniciyi_varyanta_zorla_pasif_varyant():
    motor = ab_test_al_veya_olustur("test")
    motor.varyant_ekle(Varyant(ad="A", aktif=False))
    with pytest.raises(ValueError):
        kullaniciyi_varyanta_zorla("test", "u1", "A")
