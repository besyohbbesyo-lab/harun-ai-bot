# core/webhook_validator.py — S5-7: Telegram Webhook Dogrulama
# Telegram'dan gelen update'lerin gercek oldugunu dogrular
# ============================================================

from __future__ import annotations

import hashlib
import hmac
import json
import time

from core.config import TOKEN, log_yaz


def _bot_token_hash() -> str:
    """Telegram'in secret_token hesaplama yontemine gore hash uret."""
    return hashlib.sha256(TOKEN.encode()).hexdigest()


def telegram_imza_dogrula(
    payload: bytes,
    x_telegram_bot_api_secret_token: str | None,
    secret_token: str | None = None,
) -> bool:
    """
    Webhook modunda Telegram'in gonderdigi X-Telegram-Bot-Api-Secret-Token
    headerini dogrular.

    Args:
        payload: Ham HTTP body (bytes)
        x_telegram_bot_api_secret_token: Request header degeri
        secret_token: setWebhook() sirasinda tanimlanan secret (opsiyonel)

    Returns:
        True  → imza gecerli
        False → sahte veya bozuk istek
    """
    if not x_telegram_bot_api_secret_token:
        log_yaz("[Webhook] Secret token eksik — istek reddedildi", "WARNING")
        return False

    beklenen = secret_token or _bot_token_hash()[:32]
    sonuc = hmac.compare_digest(x_telegram_bot_api_secret_token.encode(), beklenen.encode())
    if not sonuc:
        log_yaz("[Webhook] Gecersiz secret token — sahte istek!", "ERROR")
    return sonuc


def update_dogrula(update_dict: dict) -> tuple[bool, str | None]:
    """
    Polling modunda gelen Update nesnesinin temel alanlarini dogrular.
    Sahte veya bozuk update'leri filtreler.

    Returns:
        (gecerli: bool, hata_aciklamasi: str | None)
    """
    # update_id zorunlu ve pozitif olmali
    uid = update_dict.get("update_id")
    if not isinstance(uid, int) or uid <= 0:
        return False, f"Gecersiz update_id: {uid}"

    # En az bir icerik alani olmali
    icerik_alanlari = {
        "message",
        "edited_message",
        "channel_post",
        "callback_query",
        "inline_query",
        "voice",
        "document",
        "photo",
        "video",
    }
    if not any(k in update_dict for k in icerik_alanlari):
        return False, "Update'de taninan icerik alani yok"

    # Mesaj varsa user_id kontrolu
    mesaj = update_dict.get("message") or update_dict.get("edited_message")
    if mesaj:
        gonderen = mesaj.get("from") or {}
        user_id = gonderen.get("id")
        if user_id and (not isinstance(user_id, int) or user_id <= 0):
            return False, f"Gecersiz user_id: {user_id}"

        # Tarihe gore eski mesajlari reddet (24 saatten eskiyse)
        tarih = mesaj.get("date", 0)
        if tarih and (time.time() - tarih) > 86400:
            log_yaz(f"[Webhook] Eski mesaj reddedildi: {tarih}", "WARNING")
            return False, "Mesaj 24 saatten eski"

    return True, None


def update_logla(update_dict: dict, gecerli: bool, hata: str | None = None):
    """Update dogrulama sonucunu logla."""
    uid = update_dict.get("update_id", "?")
    msaj = update_dict.get("message", {})
    uid2 = (msaj.get("from") or {}).get("id", "?")

    if gecerli:
        log_yaz(f"[Webhook] Update {uid} kabul edildi (user={uid2})", "DEBUG")
    else:
        log_yaz(f"[Webhook] Update {uid} REDDEDILDI: {hata} (user={uid2})", "WARNING")
