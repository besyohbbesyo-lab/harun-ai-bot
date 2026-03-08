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
