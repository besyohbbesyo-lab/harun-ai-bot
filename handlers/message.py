# handlers/message.py - Mesaj isleyiciler
# handle_message, sesli_mesaj_handler, _yetki_kontrol, _onay_isle

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from core.globals import *
from core.utils import log_yaz
from memory_plugin import etm
from services.chat_service import ask_ai, auto_moderation_suggest, compute_reward_v2

MAX_TELEGRAM_MESSAGE_LEN = 4000


def _metni_parcalara_bol(text: str, limit: int = MAX_TELEGRAM_MESSAGE_LEN) -> list[str]:
    """Uzun metni Telegram sinirina takilmayacak parcalara boler."""
    text = (text or "").strip()
    if not text:
        return [""]

    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break

        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at == -1 or split_at < limit // 2:
            split_at = limit

        chunk = remaining[:split_at].strip()
        if not chunk:
            chunk = remaining[:limit].strip()
            split_at = len(chunk)

        parts.append(chunk)
        remaining = remaining[split_at:].lstrip()

    return parts


async def _reply_text_guvenli(message, text: str, limit: int = MAX_TELEGRAM_MESSAGE_LEN):
    """Telegram mesaj uzunlugu limitini asan cevaplari bolerek gonderir."""
    for parca in _metni_parcalara_bol(text, limit=limit):
        await message.reply_text(parca)


try:
    from monitoring.metrics import metrics as _metrics
except Exception:
    _metrics = None


async def _yetki_kontrol(update: Update) -> bool:
    """Tum handler'larda kullanilacak yetki kontrolu.
    Yetkisizse kullaniciya mesaj gonderir ve False doner.
    Yetkiliyse True doner."""
    user_id = update.message.chat_id
    if not check_auth(user_id):
        await update.message.reply_text("Bu botu kullanma yetkiniz bulunmamaktadir.")
        log_yaz(f"Yetkisiz erisim: user_id={user_id}", "GUVENLIK")
        return False
    return True


async def _onay_isle(bekleyen: dict) -> str:
    """Onaylanan kritik komutu gercekten calistirir.
    bekleyen: {"komut": str, "arguman": str, "zaman": str}
    Doner: sonuc mesaji (str)
    """
    komut = (bekleyen or {}).get("komut", "")
    arg = (bekleyen or {}).get("arguman", "")

    if komut == "mkdir":
        return pc.create_folder(arg)

    elif komut == "mkfile":
        return pc.create_file(arg)

    elif komut == "open":
        return pc.open_program(arg)

    elif komut == "tikla":
        if not OTOMASYON_AKTIF:
            return "Otomasyon aktif degil."
        parts = arg.split(",")
        x, y = int(parts[0].strip()), int(parts[1].strip())
        return otomasyon.tikla(x, y)

    elif komut == "yaz":
        if not OTOMASYON_AKTIF:
            return "Otomasyon aktif degil."
        return otomasyon.tur_yaz(arg)

    elif komut == "tus":
        if not OTOMASYON_AKTIF:
            return "Otomasyon aktif degil."
        return otomasyon.tus_bas(arg)

    elif komut == "web":
        if not OTOMASYON_AKTIF:
            return "Otomasyon aktif degil."
        return otomasyon.web_git(arg)

    elif komut == "gonder":
        return "Dosya gonderme icin /gonder komutunu tekrar kullanin."

    elif komut == "egitim":
        return "Egitim islemleri icin /egitim komutunu tekrar kullanin."

    elif komut == "sifirla":
        return "Sifirlama icin komutu tekrar kullanin."

    else:
        return f"Bilinmeyen onay komutu: {komut}"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    mesaj = update.message.text

    # SMALL TALK / SELAMLAŞMA: kısa mesajlarda RAG/LLM'e gitme
    raw = (mesaj or "").strip().lower()
    greetings = {
        "merhaba",
        "selam",
        "slm",
        "hey",
        "hi",
        "hello",
        "sa",
        "s.a",
        "selamlar",
        "s.a.",
        "selamün aleyküm",
        "selamun aleykum",
    }
    if raw in greetings or (
        len(raw) <= 12 and any(g == raw or raw.startswith(g + " ") for g in greetings)
    ):
        await update.message.reply_text("Merhaba 🙂 Nasıl yardımcı olayım?")
        return
    if not mesaj or mesaj.startswith("/"):
        return

    user_id = update.message.chat_id

    # ASAMA 15: Rate limiting kontrolu
    try:
        rl_gecti, rl_sebep = rate_limit_kontrol(user_id)
        if not rl_gecti:
            injection_logla(user_id, mesaj[:50], rl_sebep)
            await update.message.reply_text(
                "[!!] Cok fazla mesaj gonderiyorsunuz.\n" "Lutfen 1 dakika bekleyip tekrar deneyin."
            )
            return
    except Exception:
        pass

    # ASAMA 19: Kullanici sorusunu kalip analizine kaydet
    try:
        kullanici_soru_kaydet(mesaj)
        chat_id_kaydet(user_id)
    except Exception:
        pass

    # ASAMA 7: Prompt injection kontrolu
    try:
        temiz, tespit = injection_kontrol(mesaj)
        if not temiz:
            injection_logla(user_id, mesaj, tespit)
            await update.message.reply_text(
                "[!!] Guvenlik uyarisi: Bu mesaj engellendi.\n"
                f"Tespit: {tespit}\n"
                "Lutfen normal bir soru sorun."
            )
            return
    except Exception:
        pass

    # ASAMA 7: Kritik komut onay kontrolu
    try:
        onay_bekliyordu, onaylandi = await onay_kontrol(mesaj, user_id)
        if onay_bekliyordu:
            if onaylandi:
                bekleyen = onay_al(user_id)
                onay_temizle(user_id)
                # Onaylanan islemi gercekten calistir
                try:
                    sonuc = await _onay_isle(bekleyen)
                    await update.message.reply_text(f"Islem onaylandi.\n{sonuc}")
                except Exception as e:
                    await update.message.reply_text(f"Islem onaylandi ama hata olustu: {e}")
            else:
                await update.message.reply_text("Islem iptal edildi.")
            return
    except Exception:
        pass

    # ASAMA 8: Memnuniyetsizlik tespiti
    # Kullanici bir onceki yaniti begenmemisse basarisiz olarak isaretle
    MENMNUNIYETSIZLIK_KELIMELERI = [
        "yanlis",
        "yanlış",
        "hatali",
        "hatalı",
        "yanit veremedin",
        "cevap veremedin",
        "bilmiyorsun",
        "bilmiyordun",
        "yanittı degil",
        "yanıt değil",
        "tekrar anlat",
        "tekrar soyleme",
        "anlayamadim",
        "anlayamadım",
        "cok kotu",
        "çok kötü",
        "berbat",
        "sacma",
        "saçma",
        "yanlis anladın",
        "yanlış anladın",
        "hayir dogru degil",
        "hayır doğru değil",
        "bu yanlis",
        "bu yanlış",
    ]
    try:
        mesaj_lower = mesaj.lower()
        memnun_degil = any(k in mesaj_lower for k in MENMNUNIYETSIZLIK_KELIMELERI)
        if memnun_degil and user_id in _son_yanit:
            onceki = _son_yanit[user_id]
            egitim.basarisiz_kaydet(
                soru=onceki["soru"],
                yanlis_cevap=onceki["yanit"],
                duzeltilmis_cevap="",  # kullanici duzeltme yazmamis
                gorev_turu=onceki["gorev_turu"],
            )
            print(f"[Asama8] Basarisiz yanit kaydedildi: {onceki['soru'][:50]}")
    except Exception:
        pass

    await update.message.reply_text("Dusunuyorum...")

    # Fine-tuning onay kontrolu
    try:
        if await egitim_onay_kontrol(mesaj, update, context):
            return
    except Exception:
        pass

    try:
        response = await ask_ai(mesaj, gorev_turu="sohbet", kullanici_id=user_id)
    except Exception as e:
        if _metrics:
            try:
                _metrics.hata_sayac("ask_ai")
            except Exception:
                pass
        await update.message.reply_text(f"Hata: {e}")
        return

    # ASAMA 8: Bu yaniti bir sonraki mesaj icin sakla
    try:
        _son_yanit[user_id] = {"soru": mesaj, "yanit": response, "gorev_turu": "sohbet"}
        # Cache sismesini onle
        if len(_son_yanit) > 50:
            ilk = next(iter(_son_yanit))
            del _son_yanit[ilk]
    except Exception:
        pass

    try:
        memory.gorev_kaydet(
            mesaj[:100], response[:200], "sohbet", reward=reward_sys.son_smoothed(), basari=True
        )
        egitim.kaydet(mesaj, response, "sohbet", reward=reward_sys.son_smoothed())
    except Exception:
        pass

    # S2-1: ETM'ye kaydet (24 saatlik gecis hafizasi)
    try:
        onem = min(1.0, 0.3 + reward_sys.son_smoothed() * 0.7)
        etm.ekle(
            icerik=f"S: {mesaj[:200]}\nY: {response[:200]}",
            tur="sohbet",
            onem=onem,
            user_id=update.message.chat_id,
        )
    except Exception:
        pass

    # ASAMA 21: EgitimStore'a kaydet + gate kontrol
    # ASAMA 26: Egitim filtreleme — test/ping/deneme/diagnostic mesajlarini dataset'e sokme
    try:
        enabled = (os.getenv("EGITIM_FILTER_ENABLED", "1") or "1").strip()
        if enabled == "0":
            _allow_egitim = True
            _egitim_reason = "disabled"
        else:
            msg_raw = (mesaj or "").strip()
            msg_l = msg_raw.lower()
            ans_raw = (response or "").strip()
            ans_l = ans_raw.lower()

            min_prompt = int(os.getenv("EGITIM_MIN_PROMPT_LEN", "6"))
            min_answer = int(os.getenv("EGITIM_MIN_ANSWER_LEN", "40"))

            _allow_egitim = True
            _egitim_reason = "ok"

            # 1) Slash komutlari (ekstra guvenlik)
            if msg_l.startswith("/"):
                _allow_egitim = False
                _egitim_reason = "command"

            # 2) Cok kisa / anlamsiz mesajlar
            if _allow_egitim and len(msg_l) < min_prompt:
                _allow_egitim = False
                _egitim_reason = "too_short"

            # 3) Net test/ping/deneme varyantlari
            if _allow_egitim and msg_l in {
                "test",
                "ping",
                "deneme",
                "denemeee",
                "ok",
                "aa",
                "aaa",
                ".",
                "..",
                "...",
            }:
                _allow_egitim = False
                _egitim_reason = "noise_keyword"

            # 4) Diagnostic / sistemsel icerik (slash olmasa bile)
            if _allow_egitim:
                diag_hits = [
                    "api_test",
                    "api test",
                    "rotator",
                    "cooldown",
                    "latency",
                    "provider",
                    "uptime",
                    "status",
                    "egitim_stats",
                    "egitim stats",
                    "selftest",
                    "scheduler",
                ]
                if any(k in msg_l for k in diag_hits):
                    _allow_egitim = False
                    _egitim_reason = "diagnostic"

            # 5) Asistan cevabi cok kisa ise (dataset kirlenmesin)
            if _allow_egitim and len(ans_l) < min_answer:
                _allow_egitim = False
                _egitim_reason = "answer_too_short"

            # 6) Cevap icinde sistem bloklari varsa (opsiyonel koruma)
            if _allow_egitim:
                sys_markers = ["[api]", "groq-only rotator", "[guncel web bilgisi]", "[hafiza]"]
                if any(m in ans_l for m in sys_markers):
                    _allow_egitim = False
                    _egitim_reason = "system_marker_in_answer"

        if (os.getenv("EGITIM_FILTER_DEBUG", "0") or "0").strip() == "1":
            print(
                f"[Asama26] egitim_filter allow={_allow_egitim} reason={_egitim_reason} msg='{(mesaj or '')[:40]}'"
            )

        if _allow_egitim:
            # ASAMA 27: reward_v2 hesapla ve store'a iki reward'u birden yaz
            _r1 = float(reward_sys.son_smoothed())
            _r2, _feat = compute_reward_v2(mesaj, response, _r1)
            _feat["auto_suggest"] = auto_moderation_suggest(_r2)
            egitim_store.kaydet_ornek(
                prompt=mesaj,
                answer=response,
                gorev_turu="sohbet",
                user_id=update.message.from_user.id,
                chat_id=update.message.chat_id,
                basari=True,
                smoothed_reward=_r2,  # v2 artık ana sıralama metrik'i
                extra=_feat,  # v1 + sinyaller metadata'da
            )
            gate = egitim_store.gate_kontrol()
            if gate.get("gated"):
                await update.message.reply_text(
                    f"Bildirim: {gate['new_count']} yeni egitim kaydi incelemeye alindi.\n"
                    f"/egitim_incele komutuyla gozden gecirip onaylayabilirsin."
                )
    except Exception:
        pass

    log_yaz(f"Soru: {mesaj[:60]} | Cevap: {response[:60]}")
    if _metrics:
        try:
            _metrics.mesaj_sayac("sohbet", user_id=user_id)
            _metrics.basari_kaydet()
        except Exception:
            pass
    await _reply_text_guvenli(update.message, response)

    try:
        asyncio.create_task(otomatik_egitim_kontrol(update.message.chat_id))
    except Exception:
        pass


async def sesli_mesaj_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    """
    Telegram'dan gelen sesli mesajlari Google STT ile metne cevirir,
    kullaniciya ne anladigini gosterir, ardindan AI yaniti verir.
    """
    if not SES_AKTIF:
        await update.message.reply_text(
            "Sesli mesaj ozelligi aktif degil.\n"
            "ses_plugin.py dosyasinin proje klasorunde oldugunu ve\n"
            "SpeechRecognition + pydub + ffmpeg kurulu oldugunu kontrol et."
        )
        return

    user_id = update.message.chat_id
    await update.message.reply_text("Sesli mesajin isleniyor, lutfen bekle...")

    try:
        # Sesi Telegram sunucusundan indir
        voice = update.message.voice
        dosya = await context.bot.get_file(voice.file_id)

        ogg_yolu = BASE_DIR / "temp_ses" / f"ses_{user_id}_{voice.file_id}.ogg"
        ogg_yolu.parent.mkdir(exist_ok=True)
        await dosya.download_to_drive(str(ogg_yolu))

        # STT pipeline calistir
        sonuc = ses_plugin.isleme_pipeline(ogg_yolu)

        if not sonuc["basarili"]:
            if sonuc["hata"] == "anlasilamadi":
                await update.message.reply_text(
                    "Sesi anlayamadim.\n" "Lutfen daha net ve yakin konusarak tekrar dene."
                )
            else:
                await update.message.reply_text(
                    f"Ses isleme hatasi: {sonuc['hata']}\n" "Tekrar dene veya yazarak gonder."
                )
            return

        algilanan_metin = sonuc["metin"]

        # Kullaniciya ne anladigini goster
        await update.message.reply_text(f'Duyduklarim:\n"{algilanan_metin}"')

        # Metni normal mesaj gibi AI'a ilet
        await update.message.reply_text("Dusunuyorum...")
        response = await ask_ai(algilanan_metin, gorev_turu="sohbet", kullanici_id=user_id)
        await _reply_text_guvenli(update.message, response)

        # Hafiza ve egitim sistemine kaydet
        try:
            memory.gorev_kaydet(
                algilanan_metin[:100],
                response[:200],
                "sesli_mesaj",
                reward=reward_sys.son_smoothed(),
                basari=True,
            )
            egitim.kaydet(
                algilanan_metin, response, "sesli_mesaj", reward=reward_sys.son_smoothed()
            )
        except Exception:
            pass

        # Son yaniti memnuniyetsizlik tespiti icin sakla
        try:
            _son_yanit[user_id] = {
                "soru": algilanan_metin,
                "yanit": response,
                "gorev_turu": "sesli_mesaj",
            }
        except Exception:
            pass

        log_yaz(f"[SES] Algilanan: {algilanan_metin[:60]} | Yanit: {response[:60]}")

    except Exception as e:
        hata_mesaji = f"[BOT] Sesli mesaj handler hatasi: {e}"
        print(hata_mesaji)
        log_yaz(hata_mesaji)
        await update.message.reply_text(
            "Sesli mesaj islenirken beklenmeyen bir hata olustu.\n"
            "Mesajini yazarak da gonderebilirsin."
        )
