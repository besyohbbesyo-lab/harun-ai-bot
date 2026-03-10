# tests/test_message_bolme.py
# _metni_parcalara_bol() ve _onay_isle() fonksiyonlari icin dar unit testler
# Calistirma: pytest -v tests/test_message_bolme.py

import os
import sys
from unittest.mock import MagicMock, patch

# Projenin kok dizininden calistirabilmek icin path ayari
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.message import _metni_parcalara_bol

LIMIT = 4000  # MAX_TELEGRAM_MESSAGE_LEN


class TestMetniParcalarabol:
    def test_bos_string_tek_eleman_doner(self):
        """Bos veya sadece bosluktan olusan metin icin [''] donmeli."""
        assert _metni_parcalara_bol("") == [""]
        assert _metni_parcalara_bol("   ") == [""]

    def test_limit_altindaki_metin_tek_parca(self):
        """Limit altindaki metin tek parcada donmeli, degismemeli."""
        metin = "Kisa bir cevap."
        result = _metni_parcalara_bol(metin, limit=LIMIT)
        assert result == [metin]
        assert len(result) == 1

    def test_cift_satir_tercihli_bolme(self):
        """Bolunum noktasi olarak once \\n\\n tercih edilmeli."""
        parca1 = "A" * 100
        parca2 = "B" * 100
        metin = parca1 + "\n\n" + parca2
        result = _metni_parcalara_bol(metin, limit=150)
        assert len(result) == 2
        assert result[0] == parca1
        assert result[1] == parca2

    def test_tek_satir_tercihli_bolme(self):
        """\\n\\n yoksa \\n tercih edilmeli."""
        parca1 = "A" * 100
        parca2 = "B" * 100
        metin = parca1 + "\n" + parca2
        result = _metni_parcalara_bol(metin, limit=150)
        assert len(result) == 2
        assert result[0] == parca1
        assert result[1] == parca2

    def test_bosluk_tercihli_bolme(self):
        """Satir sonu yoksa bosluktan bolmeli."""
        parca1 = "bir " * 25  # 100 karakter
        parca2 = "iki " * 25  # 100 karakter
        metin = (parca1 + parca2).strip()
        result = _metni_parcalara_bol(metin, limit=105)
        assert len(result) >= 2
        for parca in result:
            assert len(parca) <= 105

    def test_hic_bolme_noktasi_olmayan_uzun_kelime(self):
        """Bosluk/satir sonu olmayan tek uzun kelimede hard-cut yapilmali."""
        uzun = "X" * 500
        result = _metni_parcalara_bol(uzun, limit=100)
        assert len(result) >= 5
        for parca in result:
            assert len(parca) <= 100

    def test_tum_parcalar_limit_altinda(self):
        """Gercekci uzun metinde hic bir parca limiti asmamali."""
        paragraflar = []
        for i in range(20):
            paragraflar.append(f"Paragraf {i}: " + "kelime " * 50)
        metin = "\n\n".join(paragraflar)
        result = _metni_parcalara_bol(metin, limit=LIMIT)
        assert len(result) >= 1
        for parca in result:
            assert len(parca) <= LIMIT, f"Parca limiti asti: {len(parca)} karakter"


class TestOnayIsle:
    """_onay_isle() fonksiyonu icin unit testler.
    pc, otomasyon ve OTOMASYON_AKTIF mock'lanarak test edilir.
    """

    def test_bilinmeyen_komut_mesaj_doner(self):
        """Taninmayan komut icin hata mesaji donmeli."""
        import asyncio

        import handlers.message as hm

        sonuc = asyncio.run(hm._onay_isle({"komut": "bilinmeyen", "arguman": ""}))
        assert "Bilinmeyen" in sonuc

    def test_bos_dict_bilinmeyen_doner(self):
        """Bos dict geldiginde de bilinmeyen mesaji donmeli."""
        import asyncio

        import handlers.message as hm

        sonuc = asyncio.run(hm._onay_isle({}))
        assert "Bilinmeyen" in sonuc

    def test_gonder_komutu_mesaj_doner(self):
        """gonder komutu dogrudan sabit mesaj donmeli, pc'ye gitme."""
        import asyncio

        import handlers.message as hm

        sonuc = asyncio.run(hm._onay_isle({"komut": "gonder", "arguman": "dosya.txt"}))
        assert "/gonder" in sonuc

    def test_egitim_komutu_mesaj_doner(self):
        """egitim komutu dogrudan sabit mesaj donmeli."""
        import asyncio

        import handlers.message as hm

        sonuc = asyncio.run(hm._onay_isle({"komut": "egitim", "arguman": ""}))
        assert "/egitim" in sonuc

    def test_sifirla_komutu_mesaj_doner(self):
        """sifirla komutu dogrudan sabit mesaj donmeli."""
        import asyncio

        import handlers.message as hm

        sonuc = asyncio.run(hm._onay_isle({"komut": "sifirla", "arguman": ""}))
        assert "Sifirlama" in sonuc

    def test_tikla_otomasyon_pasif(self):
        """OTOMASYON_AKTIF=False iken tikla komutu 'aktif degil' donmeli."""
        import asyncio

        import handlers.message as hm

        with patch.object(hm, "OTOMASYON_AKTIF", False):
            sonuc = asyncio.run(hm._onay_isle({"komut": "tikla", "arguman": "100,200"}))
        assert "aktif degil" in sonuc

    def test_yaz_otomasyon_pasif(self):
        """OTOMASYON_AKTIF=False iken yaz komutu 'aktif degil' donmeli."""
        import asyncio

        import handlers.message as hm

        with patch.object(hm, "OTOMASYON_AKTIF", False):
            sonuc = asyncio.run(hm._onay_isle({"komut": "yaz", "arguman": "merhaba"}))
        assert "aktif degil" in sonuc

    def test_mkdir_pc_cagrilir(self):
        """mkdir komutunda pc.create_folder cagrilmali ve sonucu donmeli."""
        import asyncio

        import handlers.message as hm

        mock_pc = MagicMock()
        mock_pc.create_folder.return_value = "Klasor olusturuldu."
        with patch.object(hm, "pc", mock_pc):
            sonuc = asyncio.run(hm._onay_isle({"komut": "mkdir", "arguman": "yeni_klasor"}))
        mock_pc.create_folder.assert_called_once_with("yeni_klasor")
        assert sonuc == "Klasor olusturuldu."


class TestYetkiKontrol:
    """_yetki_kontrol() fonksiyonu icin unit testler. (satir 74-79)"""

    def test_yetkisiz_kullanici_false_doner(self):
        """check_auth False donunce _yetki_kontrol False donmeli."""
        import asyncio
        from unittest.mock import AsyncMock

        import handlers.message as hm

        mock_update = MagicMock()
        mock_update.message.chat_id = 9999

        with patch.object(hm, "check_auth", return_value=False), patch.object(hm, "log_yaz"):
            mock_update.message.reply_text = AsyncMock()
            sonuc = asyncio.run(hm._yetki_kontrol(mock_update))

        assert sonuc is False
        mock_update.message.reply_text.assert_called_once()

    def test_yetkili_kullanici_true_doner(self):
        """check_auth True donunce _yetki_kontrol True donmeli."""
        import asyncio
        from unittest.mock import AsyncMock

        import handlers.message as hm

        mock_update = MagicMock()
        mock_update.message.chat_id = 6481156818

        with patch.object(hm, "check_auth", return_value=True):
            mock_update.message.reply_text = AsyncMock()
            sonuc = asyncio.run(hm._yetki_kontrol(mock_update))

        assert sonuc is True
        mock_update.message.reply_text.assert_not_called()


class TestOnayIsleEkDallar:
    """_onay_isle() icin pc/otomasyon dallari — satir 93-119"""

    def test_mkfile_pc_cagrilir(self):
        """mkfile komutunda pc.create_file cagrilmali."""
        import asyncio

        import handlers.message as hm

        mock_pc = MagicMock()
        mock_pc.create_file.return_value = "Dosya olusturuldu."
        with patch.object(hm, "pc", mock_pc):
            sonuc = asyncio.run(hm._onay_isle({"komut": "mkfile", "arguman": "test.txt"}))
        mock_pc.create_file.assert_called_once_with("test.txt")
        assert sonuc == "Dosya olusturuldu."

    def test_open_pc_cagrilir(self):
        """open komutunda pc.open_program cagrilmali."""
        import asyncio

        import handlers.message as hm

        mock_pc = MagicMock()
        mock_pc.open_program.return_value = "Program acildi."
        with patch.object(hm, "pc", mock_pc):
            sonuc = asyncio.run(hm._onay_isle({"komut": "open", "arguman": "notepad"}))
        mock_pc.open_program.assert_called_once_with("notepad")
        assert sonuc == "Program acildi."

    def test_tikla_otomasyon_aktif(self):
        """OTOMASYON_AKTIF=True iken tikla komutu otomasyon.tikla cagirmali."""
        import asyncio

        import handlers.message as hm

        mock_otomasyon = MagicMock()
        mock_otomasyon.tikla.return_value = "Tiklandi."
        with (
            patch.object(hm, "OTOMASYON_AKTIF", True),
            patch.object(hm, "otomasyon", mock_otomasyon),
        ):
            sonuc = asyncio.run(hm._onay_isle({"komut": "tikla", "arguman": "100, 200"}))
        mock_otomasyon.tikla.assert_called_once_with(100, 200)
        assert sonuc == "Tiklandi."

    def test_tus_otomasyon_pasif(self):
        """OTOMASYON_AKTIF=False iken tus komutu 'aktif degil' donmeli."""
        import asyncio

        import handlers.message as hm

        with patch.object(hm, "OTOMASYON_AKTIF", False):
            sonuc = asyncio.run(hm._onay_isle({"komut": "tus", "arguman": "enter"}))
        assert "aktif degil" in sonuc

    def test_web_otomasyon_pasif(self):
        """OTOMASYON_AKTIF=False iken web komutu 'aktif degil' donmeli."""
        import asyncio

        import handlers.message as hm

        with patch.object(hm, "OTOMASYON_AKTIF", False):
            sonuc = asyncio.run(hm._onay_isle({"komut": "web", "arguman": "https://example.com"}))
        assert "aktif degil" in sonuc


class TestReplyTextGuvenli:
    """_reply_text_guvenli() fonksiyonu icin unit testler. (satir 59-62)"""

    def test_kisa_metin_tek_parca_gonderilir(self):
        """Limit altindaki metin reply_text'e tek seferde gonderilmeli."""
        import asyncio
        from unittest.mock import AsyncMock

        import handlers.message as hm

        mock_message = MagicMock()
        mock_message.reply_text = AsyncMock()

        asyncio.run(hm._reply_text_guvenli(mock_message, "Kisa cevap."))

        mock_message.reply_text.assert_called_once_with("Kisa cevap.")

    def test_uzun_metin_birden_fazla_parca_gonderilir(self):
        """Limit aşan metin reply_text'e birden fazla kez cagrilmali."""
        import asyncio
        from unittest.mock import AsyncMock

        import handlers.message as hm

        mock_message = MagicMock()
        mock_message.reply_text = AsyncMock()

        uzun_metin = "kelime " * 700  # ~4900 karakter, 4000 limitini asar

        asyncio.run(hm._reply_text_guvenli(mock_message, uzun_metin))

        assert mock_message.reply_text.call_count >= 2

    def test_bos_metin_bir_kez_cagrilir(self):
        """Bos metin icin reply_text yine de bir kez cagrilmali."""
        import asyncio
        from unittest.mock import AsyncMock

        import handlers.message as hm

        mock_message = MagicMock()
        mock_message.reply_text = AsyncMock()

        asyncio.run(hm._reply_text_guvenli(mock_message, ""))

        mock_message.reply_text.assert_called_once_with("")

    def test_her_parca_limit_altinda_gonderilir(self):
        """Gonderilen hic bir parca limiti asmamali."""
        import asyncio
        from unittest.mock import AsyncMock

        import handlers.message as hm

        mock_message = MagicMock()
        mock_message.reply_text = AsyncMock()

        uzun_metin = "A" * 10000
        kucuk_limit = 500

        asyncio.run(hm._reply_text_guvenli(mock_message, uzun_metin, limit=kucuk_limit))

        for cagri in mock_message.reply_text.call_args_list:
            gonderilen = cagri[0][0]
            assert len(gonderilen) <= kucuk_limit


# ---------------------------------------------------------------------------
# handle_message testleri icin ortak mock kurulum yardimcisi
# ---------------------------------------------------------------------------
from unittest.mock import AsyncMock

import pytest


def _handle_message_mock_setup(
    mesaj_metni="Merhaba",
    chat_id=6481156818,
    check_auth_val=True,
    rate_limit_val=(True, ""),
    injection_val=(True, ""),
    onay_val=(False, False),
    ask_ai_val="Test cevabi.",
    egitim_onay_val=False,
):
    """handle_message icin standart mock update + patch context olusturur."""
    mock_update = MagicMock()
    mock_update.message.text = mesaj_metni
    mock_update.message.chat_id = chat_id
    mock_update.message.from_user.id = chat_id
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()

    patches = {
        "check_auth": patch("handlers.message.check_auth", return_value=check_auth_val),
        "log_yaz": patch("handlers.message.log_yaz"),
        "rate_limit_kontrol": patch(
            "handlers.message.rate_limit_kontrol", return_value=rate_limit_val
        ),
        "injection_kontrol": patch(
            "handlers.message.injection_kontrol", return_value=injection_val
        ),
        "injection_logla": patch("handlers.message.injection_logla"),
        "onay_kontrol": patch(
            "handlers.message.onay_kontrol", new=AsyncMock(return_value=onay_val)
        ),
        "ask_ai": patch("handlers.message.ask_ai", new=AsyncMock(return_value=ask_ai_val)),
        "egitim_onay_kontrol": patch(
            "handlers.message.egitim_onay_kontrol", new=AsyncMock(return_value=egitim_onay_val)
        ),
        "kullanici_soru_kaydet": patch("handlers.message.kullanici_soru_kaydet"),
        "chat_id_kaydet": patch("handlers.message.chat_id_kaydet"),
        "memory": patch("handlers.message.memory"),
        "egitim": patch("handlers.message.egitim"),
        "reward_sys": patch("handlers.message.reward_sys"),
        "etm": patch("handlers.message.etm"),
        "egitim_store": patch("handlers.message.egitim_store"),
    }
    return mock_update, mock_context, patches


class TestHandleMessageGreeting:
    """handle_message — selamlasma ve erken cikis dallari (satir 135-161)"""

    def test_yetkisiz_kullanici_erken_cikis(self):
        """Yetkisiz kullanicida reply_text bir kez cagrilip fonksiyon donmeli."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="merhaba", check_auth_val=False
        )
        with patches["check_auth"], patches["log_yaz"]:
            asyncio.run(hm.handle_message(mock_update, mock_context))

        # Yetkisiz mesaji gonderildi, ask_ai cagrilmadi
        mock_update.message.reply_text.assert_called_once()
        assert "yetki" in mock_update.message.reply_text.call_args[0][0].lower()

    def test_selamlasma_ask_ai_ye_gitmiyor(self):
        """'merhaba' mesajinda ask_ai cagrilmamali, sabit cevap donmeli."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(mesaj_metni="merhaba")
        with patches["check_auth"], patches["log_yaz"], patches["ask_ai"] as mock_ask:
            asyncio.run(hm.handle_message(mock_update, mock_context))

        mock_ask.assert_not_called()
        mock_update.message.reply_text.assert_called_once()
        assert "Merhaba" in mock_update.message.reply_text.call_args[0][0]

    def test_selam_varyanti_greeting_tetikler(self):
        """'selam' mesaji da greeting dalini tetiklemeli."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(mesaj_metni="selam")
        with patches["check_auth"], patches["log_yaz"], patches["ask_ai"] as mock_ask:
            asyncio.run(hm.handle_message(mock_update, mock_context))

        mock_ask.assert_not_called()

    def test_slash_komut_erken_cikis(self):
        """/start gibi slash komutlarda ask_ai cagrilmamali."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(mesaj_metni="/start")
        with patches["check_auth"], patches["log_yaz"], patches["ask_ai"] as mock_ask:
            asyncio.run(hm.handle_message(mock_update, mock_context))

        mock_ask.assert_not_called()

    def test_rate_limit_asiminda_uyari_mesaji(self):
        """Rate limit asilinca uyari mesaji gonderilmeli, ask_ai cagrilmamali."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="normal soru",
            rate_limit_val=(False, "rate_limit"),
        )
        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_logla"],
            patches["ask_ai"] as mock_ask,
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        mock_ask.assert_not_called()
        cagri_metni = mock_update.message.reply_text.call_args[0][0]
        assert "Cok fazla" in cagri_metni or "fazla" in cagri_metni.lower()

    def test_injection_tespitinde_engelleme_mesaji(self):
        """Prompt injection tespitinde engelleme mesaji gonderilmeli."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="zararli prompt",
            injection_val=(False, "injection_tespit"),
        )
        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["injection_logla"],
            patches["ask_ai"] as mock_ask,
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        mock_ask.assert_not_called()
        cagri_metni = mock_update.message.reply_text.call_args[0][0]
        assert "engellendi" in cagri_metni.lower() or "Guvenlik" in cagri_metni

    def test_normal_mesaj_ask_ai_cagrilir(self):
        """Normal mesajda ask_ai cagrilmali ve cevap gonderilmeli."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="Python nedir?",
            ask_ai_val="Python bir programlama dilidir.",
        )
        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["ask_ai"] as mock_ask,
            patches["egitim_onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
            patches["memory"],
            patches["egitim"],
            patches["reward_sys"],
            patches["etm"],
            patches["egitim_store"],
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        mock_ask.assert_called_once()
        assert mock_ask.call_args[0][0] == "Python nedir?"


class TestHandleMessageAskAiException:
    """ask_ai exception dalini test eder (satir 295-302)."""

    def test_ask_ai_exception_hata_mesaji_gonderilir(self):
        """ask_ai exception atarsa kullaniciya hata mesaji gider."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="Python nedir?",
        )
        # ask_ai exception atsin
        failing_ask = patch(
            "handlers.message.ask_ai",
            new=AsyncMock(side_effect=RuntimeError("api patladi")),
        )
        # _metrics mock
        mock_met = MagicMock()
        metrics_patch = patch.object(hm, "_metrics", mock_met)

        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["egitim_onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
            failing_ask,
            metrics_patch,
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        # Hata mesaji gonderildi
        son_cagri = mock_update.message.reply_text.call_args[0][0]
        assert "Hata" in son_cagri


class TestHandleMessageTamAkis:
    """handle_message tam basarili akis — _son_yanit, memory, egitim, ETM, egitim_store (satir 304-452)."""

    def test_tam_basarili_akis_egitim_store_kaydeder(self):
        """Normal mesaj: ask_ai basarili, reward hesaplanir, egitim_store'a kaydedilir."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="Python programlama nedir acikla",
            ask_ai_val="Python genel amacli bir programlama dilidir ve cok yaygindir.",
        )

        # reward_sys.son_smoothed() gercek float donmeli
        mock_reward = MagicMock()
        mock_reward.son_smoothed.return_value = 0.75
        patches["reward_sys"] = patch("handlers.message.reward_sys", mock_reward)

        # egitim_store gercekci mock
        mock_estore = MagicMock()
        mock_estore.kaydet_ornek.return_value = None
        mock_estore.gate_kontrol.return_value = {"gated": False, "new_count": 0}
        patches["egitim_store"] = patch("handlers.message.egitim_store", mock_estore)

        # _metrics mock
        mock_met = MagicMock()
        metrics_patch = patch.object(hm, "_metrics", mock_met)

        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["ask_ai"],
            patches["egitim_onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
            patches["memory"],
            patches["egitim"],
            patches["reward_sys"],
            patches["etm"],
            patches["egitim_store"],
            metrics_patch,
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        # egitim_store.kaydet_ornek cagrildi
        mock_estore.kaydet_ornek.assert_called_once()
        # _metrics.mesaj_sayac cagrildi
        mock_met.mesaj_sayac.assert_called_once()

    def test_egitim_filter_disabled_hala_kaydeder(self):
        """EGITIM_FILTER_ENABLED=0 iken egitim filtre atlanir, yine kaydedilir."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="kisa test mesaji burada",
            ask_ai_val="Yeterince uzun bir cevap olmali ki filtreden gecsin burada.",
        )

        mock_reward = MagicMock()
        mock_reward.son_smoothed.return_value = 0.6
        patches["reward_sys"] = patch("handlers.message.reward_sys", mock_reward)

        mock_estore = MagicMock()
        mock_estore.kaydet_ornek.return_value = None
        mock_estore.gate_kontrol.return_value = {"gated": False}
        patches["egitim_store"] = patch("handlers.message.egitim_store", mock_estore)

        env_patch = patch.dict(os.environ, {"EGITIM_FILTER_ENABLED": "0"})

        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["ask_ai"],
            patches["egitim_onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
            patches["memory"],
            patches["egitim"],
            patches["reward_sys"],
            patches["etm"],
            patches["egitim_store"],
            env_patch,
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        mock_estore.kaydet_ornek.assert_called_once()

    def test_egitim_filter_noise_keyword_engeller(self):
        """Noise keyword mesaji ('test') egitim_store'a kaydedilmemeli."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="test",  # greeting degilse noise olarak engellenmeli
            ask_ai_val="Bu bir test cevabi.",
        )

        # "test" greeting listesinde degil ama 4 karakterden kisa degil,
        # fakat noise_keyword setinde var
        # Ama once greetings kontrolune takilabilir... hayir "test" greetings'te yok.
        # slash ile baslamiyor. Rate limit + injection OK.
        # Ama "test" noise_keyword olarak engellenmeli (satir 364-377)

        mock_reward = MagicMock()
        mock_reward.son_smoothed.return_value = 0.5
        patches["reward_sys"] = patch("handlers.message.reward_sys", mock_reward)

        mock_estore = MagicMock()
        mock_estore.kaydet_ornek.return_value = None
        mock_estore.gate_kontrol.return_value = {"gated": False}
        patches["egitim_store"] = patch("handlers.message.egitim_store", mock_estore)

        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["ask_ai"],
            patches["egitim_onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
            patches["memory"],
            patches["egitim"],
            patches["reward_sys"],
            patches["etm"],
            patches["egitim_store"],
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        # "test" noise keyword → egitim_store.kaydet_ornek cagrilMAMALI
        mock_estore.kaydet_ornek.assert_not_called()

    def test_egitim_gate_gated_bildirim_gonderir(self):
        """gate_kontrol gated=True donunce kullaniciya bildirim gider."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="Python fonksiyonlari nasil yazilir detayli anlat",
            ask_ai_val="Python fonksiyonlari def anahtar kelimesi ile tanimlanir ve parametreleri vardir.",
        )

        mock_reward = MagicMock()
        mock_reward.son_smoothed.return_value = 0.85
        patches["reward_sys"] = patch("handlers.message.reward_sys", mock_reward)

        mock_estore = MagicMock()
        mock_estore.kaydet_ornek.return_value = None
        mock_estore.gate_kontrol.return_value = {"gated": True, "new_count": 5}
        patches["egitim_store"] = patch("handlers.message.egitim_store", mock_estore)

        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["ask_ai"],
            patches["egitim_onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
            patches["memory"],
            patches["egitim"],
            patches["reward_sys"],
            patches["etm"],
            patches["egitim_store"],
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        # Gate bildirimi gonderildi
        cagrilar = [c[0][0] for c in mock_update.message.reply_text.call_args_list]
        assert any("egitim" in c.lower() or "inceleme" in c.lower() for c in cagrilar)


class TestSesliMesajHandler:
    """sesli_mesaj_handler() dallarini test eder (satir 455-537)."""

    def test_ses_aktif_degil_uyari_mesaji(self):
        """SES_AKTIF=False iken uyari mesaji gonderilir."""
        import asyncio

        import handlers.message as hm

        mock_update = MagicMock()
        mock_update.message.chat_id = 6481156818
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        with (
            patch.object(hm, "check_auth", return_value=True),
            patch.object(hm, "SES_AKTIF", False),
        ):
            asyncio.run(hm.sesli_mesaj_handler(mock_update, mock_context))

        cagri = mock_update.message.reply_text.call_args[0][0]
        assert "aktif degil" in cagri.lower() or "Sesli" in cagri

    def test_ses_yetkisiz_kullanici(self):
        """Yetkisiz kullanici sesli mesaj handler'a giremez."""
        import asyncio

        import handlers.message as hm

        mock_update = MagicMock()
        mock_update.message.chat_id = 9999
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        with (
            patch.object(hm, "check_auth", return_value=False),
            patch.object(hm, "log_yaz"),
        ):
            asyncio.run(hm.sesli_mesaj_handler(mock_update, mock_context))

        cagri = mock_update.message.reply_text.call_args[0][0]
        assert "yetki" in cagri.lower()

    def test_ses_basarili_akis(self):
        """SES_AKTIF=True ve basarili STT pipeline → AI yaniti gonderilir."""
        import asyncio

        import handlers.message as hm

        mock_update = MagicMock()
        mock_update.message.chat_id = 6481156818
        mock_update.message.reply_text = AsyncMock()
        mock_update.message.voice.file_id = "test_file_id"

        mock_context = MagicMock()
        mock_dosya = MagicMock()
        mock_dosya.download_to_drive = AsyncMock()
        mock_context.bot.get_file = AsyncMock(return_value=mock_dosya)

        mock_ses = MagicMock()
        mock_ses.isleme_pipeline.return_value = {
            "basarili": True,
            "metin": "Bu bir test sesidir",
            "hata": None,
        }

        with (
            patch.object(hm, "check_auth", return_value=True),
            patch.object(hm, "SES_AKTIF", True),
            patch.object(hm, "ses_plugin", mock_ses),
            patch.object(hm, "BASE_DIR", MagicMock(__truediv__=MagicMock(return_value=MagicMock(parent=MagicMock())))),
            patch.object(hm, "ask_ai", new=AsyncMock(return_value="AI yaniti burada.")),
            patch.object(hm, "memory"),
            patch.object(hm, "egitim"),
            patch.object(hm, "reward_sys"),
            patch.object(hm, "log_yaz"),
        ):
            asyncio.run(hm.sesli_mesaj_handler(mock_update, mock_context))

        # AI yaniti gonderildi
        cagrilar = [c[0][0] for c in mock_update.message.reply_text.call_args_list]
        assert any("AI yaniti" in c for c in cagrilar)

    def test_ses_stt_anlasilamadi(self):
        """STT basarisiz: anlasilamadi hatasi → uyari mesaji."""
        import asyncio

        import handlers.message as hm

        mock_update = MagicMock()
        mock_update.message.chat_id = 6481156818
        mock_update.message.reply_text = AsyncMock()
        mock_update.message.voice.file_id = "test_file_id"

        mock_context = MagicMock()
        mock_dosya = MagicMock()
        mock_dosya.download_to_drive = AsyncMock()
        mock_context.bot.get_file = AsyncMock(return_value=mock_dosya)

        mock_ses = MagicMock()
        mock_ses.isleme_pipeline.return_value = {
            "basarili": False,
            "metin": "",
            "hata": "anlasilamadi",
        }

        with (
            patch.object(hm, "check_auth", return_value=True),
            patch.object(hm, "SES_AKTIF", True),
            patch.object(hm, "ses_plugin", mock_ses),
            patch.object(hm, "BASE_DIR", MagicMock(__truediv__=MagicMock(return_value=MagicMock(parent=MagicMock())))),
            patch.object(hm, "log_yaz"),
        ):
            asyncio.run(hm.sesli_mesaj_handler(mock_update, mock_context))

        cagrilar = [c[0][0] for c in mock_update.message.reply_text.call_args_list]
        assert any("anlayamadim" in c.lower() or "net" in c.lower() for c in cagrilar)

    def test_ses_stt_genel_hata(self):
        """STT basarisiz: genel hata → hata mesaji."""
        import asyncio

        import handlers.message as hm

        mock_update = MagicMock()
        mock_update.message.chat_id = 6481156818
        mock_update.message.reply_text = AsyncMock()
        mock_update.message.voice.file_id = "test_file_id"

        mock_context = MagicMock()
        mock_dosya = MagicMock()
        mock_dosya.download_to_drive = AsyncMock()
        mock_context.bot.get_file = AsyncMock(return_value=mock_dosya)

        mock_ses = MagicMock()
        mock_ses.isleme_pipeline.return_value = {
            "basarili": False,
            "metin": "",
            "hata": "codec_error",
        }

        with (
            patch.object(hm, "check_auth", return_value=True),
            patch.object(hm, "SES_AKTIF", True),
            patch.object(hm, "ses_plugin", mock_ses),
            patch.object(hm, "BASE_DIR", MagicMock(__truediv__=MagicMock(return_value=MagicMock(parent=MagicMock())))),
            patch.object(hm, "log_yaz"),
        ):
            asyncio.run(hm.sesli_mesaj_handler(mock_update, mock_context))

        cagrilar = [c[0][0] for c in mock_update.message.reply_text.call_args_list]
        assert any("hata" in c.lower() for c in cagrilar)


class TestHandleMessageOnayAkisi:
    """Onay kontrol → _onay_isle akisi (satir 222-238)."""

    def test_onay_onaylandi_islem_calistirilir(self):
        """Kullanici 'evet' deyince onaylanan komut calistirilir."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="evet",
        )
        # onay_kontrol → (True, True) = onay bekliyordu ve onaylandi
        patches["onay_kontrol"] = patch(
            "handlers.message.onay_kontrol",
            new=AsyncMock(return_value=(True, True)),
        )
        mock_onay_al = patch(
            "handlers.message.onay_al",
            return_value={"komut": "gonder", "arguman": "dosya.txt"},
        )
        mock_onay_temizle = patch("handlers.message.onay_temizle")

        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
            mock_onay_al,
            mock_onay_temizle,
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        cagrilar = [c[0][0] for c in mock_update.message.reply_text.call_args_list]
        assert any("onaylandi" in c.lower() or "Islem" in c for c in cagrilar)

    def test_onay_iptal_edildi(self):
        """Kullanici 'hayir' deyince islem iptal mesaji gonderilir."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="hayir",
        )
        patches["onay_kontrol"] = patch(
            "handlers.message.onay_kontrol",
            new=AsyncMock(return_value=(True, False)),
        )

        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        cagrilar = [c[0][0] for c in mock_update.message.reply_text.call_args_list]
        assert any("iptal" in c.lower() for c in cagrilar)


class TestHandleMessageMemnuniyetsizlik:
    """Memnuniyetsizlik tespiti (satir 269-282)."""

    def test_memnuniyetsizlik_basarisiz_kaydedilir(self):
        """'yanlis' mesaji gelince onceki yanit basarisiz kaydedilir."""
        import asyncio

        import handlers.message as hm

        mock_update, mock_context, patches = _handle_message_mock_setup(
            mesaj_metni="yanlis cevap verdin",
            ask_ai_val="Ozur dilerim, tekrar deneyeyim.",
        )

        # _son_yanit'a onceki bir cevap koy
        son_yanit_data = {
            6481156818: {
                "soru": "Python nedir?",
                "yanit": "Python bir yilandir.",
                "gorev_turu": "sohbet",
            }
        }
        mock_egitim = MagicMock()

        with (
            patches["check_auth"],
            patches["log_yaz"],
            patches["rate_limit_kontrol"],
            patches["injection_kontrol"],
            patches["onay_kontrol"],
            patches["ask_ai"],
            patches["egitim_onay_kontrol"],
            patches["kullanici_soru_kaydet"],
            patches["chat_id_kaydet"],
            patches["memory"],
            patch("handlers.message.egitim", mock_egitim),
            patches["reward_sys"],
            patches["etm"],
            patches["egitim_store"],
            patch.object(hm, "_son_yanit", son_yanit_data),
        ):
            asyncio.run(hm.handle_message(mock_update, mock_context))

        mock_egitim.basarisiz_kaydet.assert_called_once()
