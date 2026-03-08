# tests/test_metrics.py
import time
from unittest.mock import MagicMock, patch

import pytest

from monitoring.metrics import BotMetrics


@pytest.fixture
def m():
    """Her test için temiz BotMetrics örneği."""
    bot = BotMetrics()
    return bot


# --- mesaj_sayac ---


def test_mesaj_sayac_artar(m):
    m.mesaj_sayac()
    assert m._mesaj_sayisi == 1


def test_mesaj_sayac_gorev_turu(m):
    m.mesaj_sayac(gorev_turu="sohbet")
    assert m._gorev_sayisi["sohbet"] == 1


def test_mesaj_sayac_user_id(m):
    m.mesaj_sayac(user_id=42)
    assert 42 in m._aktif_kullanicilar


def test_mesaj_sayac_birden_fazla(m):
    m.mesaj_sayac()
    m.mesaj_sayac()
    m.mesaj_sayac()
    assert m._mesaj_sayisi == 3


# --- hata_sayac ---


def test_hata_sayac_artar(m):
    m.hata_sayac("Groq")
    assert m._hata_sayisi["Groq"] == 1
    assert m._basarisiz_sayisi == 1


def test_hata_sayac_birden_fazla_provider(m):
    m.hata_sayac("Groq")
    m.hata_sayac("Llama")
    assert m._hata_sayisi["Groq"] == 1
    assert m._hata_sayisi["Llama"] == 1


# --- basari_kaydet ---


def test_basari_kaydet(m):
    m.basari_kaydet()
    assert m._basari_sayisi == 1


# --- yanit_sure_kaydet ---


def test_yanit_sure_kaydet(m):
    m.yanit_sure_kaydet(1.5)
    assert len(m._yanit_sureleri) == 1
    assert m._yanit_sureleri[0]["sure"] == 1.5


def test_yanit_sure_gorev_turu(m):
    m.yanit_sure_kaydet(2.0, gorev_turu="arama")
    assert m._yanit_sureleri[0]["gorev"] == "arama"


# --- token_kaydet ---


def test_token_kaydet(m):
    m.token_kaydet(100)
    assert m._token_kullanim == 100


def test_token_kaydet_birikim(m):
    m.token_kaydet(100)
    m.token_kaydet(200)
    assert m._token_kullanim == 300


# --- aktif_kullanici_sayisi ---


def test_aktif_kullanici_var(m):
    m.mesaj_sayac(user_id=1)
    m.mesaj_sayac(user_id=2)
    assert m.aktif_kullanici_sayisi() == 2


def test_aktif_kullanici_eski_kayit(m):
    m._aktif_kullanicilar[99] = time.time() - 400  # 400 sn önce → pencere dışı
    assert m.aktif_kullanici_sayisi(pencere_sn=300) == 0


# --- ortalama_yanit_suresi ---


def test_ortalama_yanit_suresi_bos(m):
    assert m.ortalama_yanit_suresi() == 0.0


def test_ortalama_yanit_suresi_hesap(m):
    m.yanit_sure_kaydet(1.0)
    m.yanit_sure_kaydet(3.0)
    assert m.ortalama_yanit_suresi() == 2.0


# --- basari_orani ---


def test_basari_orani_bos(m):
    assert m.basari_orani() == 1.0


def test_basari_orani_hesap(m):
    m.basari_kaydet()
    m.basari_kaydet()
    m.hata_sayac()
    assert abs(m.basari_orani() - 2 / 3) < 0.001


# --- uptime_sn ---


def test_uptime_sn_pozitif(m):
    assert m.uptime_sn() >= 0.0


# --- ozet ---


def test_ozet_anahtarlar(m):
    o = m.ozet()
    assert "mesaj_sayisi" in o
    assert "basari_orani" in o
    assert "uptime_sn" in o
    assert "prometheus" in o


def test_ozet_degerler(m):
    m.mesaj_sayac(gorev_turu="sohbet")
    m.hata_sayac("Groq")
    m.basari_kaydet()
    m.token_kaydet(50)
    o = m.ozet()
    assert o["mesaj_sayisi"] == 1
    assert o["token_kullanim"] == 50
    assert "sohbet" in o["gorev_dagilimi"]


# --- ozet_metni ---


def test_ozet_metni_string(m):
    result = m.ozet_metni()
    assert isinstance(result, str)
    assert "mesaj" in result.lower()


def test_ozet_metni_hata_dagilimi(m):
    m.hata_sayac("Groq")
    result = m.ozet_metni()
    assert "Groq" in result


# --- sifirla ---


def test_sifirla(m):
    m.mesaj_sayac()
    m.hata_sayac("X")
    m.token_kaydet(100)
    m.sifirla()
    assert m._mesaj_sayisi == 0
    assert m._token_kullanim == 0
    assert len(m._hata_sayisi) == 0


# --- prometheus_baslat (_PROM=False) ---


def test_prometheus_baslat_prom_yuklu_degil(m):
    result = m.prometheus_baslat()
    assert result is False


# --- _prom_yukle ---


def test_prom_yukle_basarili():
    fake_counter = MagicMock()
    fake_histogram = MagicMock()
    fake_gauge = MagicMock()
    fake_module = MagicMock()
    fake_module.Counter = MagicMock(return_value=fake_counter)
    fake_module.Histogram = MagicMock(return_value=fake_histogram)
    fake_module.Gauge = MagicMock(return_value=fake_gauge)

    import monitoring.metrics as mm

    original_prom = mm._PROM
    mm._PROM = False

    with patch.dict("sys.modules", {"prometheus_client": fake_module}):
        result = mm._prom_yukle()

    mm._PROM = original_prom
    assert result is True


def test_prom_yukle_zaten_aktif():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = True
    result = mm._prom_yukle()
    mm._PROM = original
    assert result is True


def test_prom_yukle_import_hata():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = False
    with patch.dict("sys.modules", {"prometheus_client": None}):
        result = mm._prom_yukle()
    mm._PROM = original
    assert result is False


# --- Prometheus dalları (mesaj_sayac, hata_sayac, vb.) ---


def test_mesaj_sayac_prom_aktif():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = True
    fake = MagicMock()
    mm._msg_counter = fake
    m = BotMetrics()
    m.mesaj_sayac(gorev_turu="test")
    fake.labels.assert_called_once_with(gorev_turu="test")
    mm._PROM = original


def test_hata_sayac_prom_aktif():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = True
    fake = MagicMock()
    mm._error_counter = fake
    m = BotMetrics()
    m.hata_sayac("TestProvider")
    fake.labels.assert_called_once_with(provider="TestProvider")
    mm._PROM = original


def test_yanit_sure_prom_aktif():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = True
    fake = MagicMock()
    mm._latency_hist = fake
    m = BotMetrics()
    m.yanit_sure_kaydet(1.5)
    fake.observe.assert_called_once_with(1.5)
    mm._PROM = original


def test_token_kaydet_prom_aktif():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = True
    fake = MagicMock()
    mm._token_gauge = fake
    m = BotMetrics()
    m.token_kaydet(200)
    fake.set.assert_called()
    mm._PROM = original


def test_aktif_kullanici_prom_aktif():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = True
    fake = MagicMock()
    mm._active_users = fake
    m = BotMetrics()
    m.mesaj_sayac(user_id=5)
    m.aktif_kullanici_sayisi()
    fake.set.assert_called()
    mm._PROM = original


def test_prometheus_baslat_prom_aktif():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = True
    fake_module = MagicMock()
    with patch.dict("sys.modules", {"prometheus_client": fake_module}):
        with patch("prometheus_client.start_http_server"):
            m = BotMetrics()
            result = m.prometheus_baslat(port=9999)
    mm._PROM = original
    assert result is True


def test_prometheus_baslat_exception():
    import monitoring.metrics as mm

    original = mm._PROM
    mm._PROM = True
    with patch("prometheus_client.start_http_server", side_effect=Exception("port hatası")):
        m = BotMetrics()
        result = m.prometheus_baslat(port=9999)
    mm._PROM = original
    assert result is False
