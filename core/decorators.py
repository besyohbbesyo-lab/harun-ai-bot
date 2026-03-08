# core/decorators.py - DRY: Tekrarlanan kaliplari ortadan kaldiran
# decorator ve yardimci fonksiyonlar

import functools

from telegram import Update
from telegram.ext import ContextTypes


def yetki_gerekli(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from handlers.message import _yetki_kontrol

        if not await _yetki_kontrol(update):
            return
        # S3-2: Rol bazli yetki kontrolu
        try:
            from rol_yetki import komut_izinli_mi

            komut_adi = func.__name__.replace("_command", "")
            user_id = update.message.chat_id
            if not komut_izinli_mi(user_id, komut_adi):
                await update.message.reply_text(f"Bu komutu kullanma yetkiniz yok. (/{komut_adi})")
                return
        except ImportError:
            pass  # rol_yetki yoksa eski davranis devam eder
        return await func(update, context)

    return wrapper


def otomasyon_gerekli(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core.globals import OTOMASYON_AKTIF
        from handlers.message import _yetki_kontrol

        if not await _yetki_kontrol(update):
            return
        if not OTOMASYON_AKTIF:
            await update.message.reply_text("Otomasyon aktif degil. pip install pyautogui")
            return
        return await func(update, context)

    return wrapper


def gorev_kaydet(gorev_aciklama, sonuc, gorev_turu, basari=True):
    from core.globals import memory, reward_sys

    try:
        reward = reward_sys.son_smoothed()
        memory.gorev_kaydet(
            gorev_aciklama[:100], sonuc[:200], gorev_turu, reward=reward, basari=basari
        )
    except Exception:
        pass


def gorev_kaydet_ve_egitim(soru, yanit, gorev_turu, basari=True):
    from core.globals import egitim, memory, reward_sys

    try:
        reward = reward_sys.son_smoothed()
        memory.gorev_kaydet(soru[:100], yanit[:200], gorev_turu, reward=reward, basari=basari)
        egitim.kaydet(soru, yanit, gorev_turu, reward=reward)
    except Exception:
        pass
