# log_utils.py - Guvenli Loglama Modulu (Asama 2 Gorev 7)
# --------------------------------------------------------
# 1) PII Maskeleme: Email, telefon, API key, token, IP adresi
# 2) Log Rotation: max 10MB, 5 yedek dosya
# 3) Structured format: [ZAMAN] [SEVIYE] mesaj

import os
import re
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# PII MASKELEME PATTERNLERİ
# ─────────────────────────────────────────────────────────────

_PII_PATTERNS = [
    # API Key'ler (Groq: gsk_, OpenAI: sk-, genel)
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "***GSK_KEY***"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "***SK_KEY***"),
    # Telegram Bot Token (sayı:alfanumerik)
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"), "***BOT_TOKEN***"),
    # Email adresleri
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}"), "***EMAIL***"),
    # Telefon numaralari (Turkiye: 05xx, +90, uluslararasi)
    (re.compile(r"(?:\+90|0)[\s-]?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"), "***TELEFON***"),
    (re.compile(r"\+?\d{10,15}"), "***TELEFON***"),
    # IP adresleri
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "***IP***"),
    # Bearer token / Authorization header
    (re.compile(r"Bearer\s+[A-Za-z0-9_.~+/=-]{20,}", re.IGNORECASE), "***BEARER***"),
    # Genel uzun secret pattern (32+ karakter hex/base64)
    (
        re.compile(
            r'(?:key|token|secret|password|api_key|apikey)[\s=:]+["\']?[A-Za-z0-9+/=_-]{32,}["\']?',
            re.IGNORECASE,
        ),
        "***SECRET***",
    ),
]


def maskele_pii(mesaj: str) -> str:
    """Mesajdaki PII/secret bilgileri maskeler."""
    if not mesaj:
        return mesaj
    for pattern, replacement in _PII_PATTERNS:
        mesaj = pattern.sub(replacement, mesaj)
    return mesaj


# ─────────────────────────────────────────────────────────────
# LOG ROTATION
# ─────────────────────────────────────────────────────────────

# Config'den log ayarlarini oku
try:
    from bot_config import CFG

    _log_cfg = CFG.get("log", {})
    MAX_LOG_BOYUTU = _log_cfg.get("max_boyut_mb", 10) * 1024 * 1024
    MAX_YEDEK_SAYISI = _log_cfg.get("max_yedek", 5)
except Exception:
    MAX_LOG_BOYUTU = 10 * 1024 * 1024  # 10 MB
    MAX_YEDEK_SAYISI = 5


def _log_rotasyon(log_dosyasi: Path):
    """Log dosyasi MAX_LOG_BOYUTU'nu asarsa rotate et.
    bot_log.txt → bot_log.1.txt → bot_log.2.txt → ... → bot_log.5.txt (silinir)
    """
    try:
        if not log_dosyasi.exists():
            return
        if log_dosyasi.stat().st_size < MAX_LOG_BOYUTU:
            return

        stem = log_dosyasi.stem  # "bot_log"
        suffix = log_dosyasi.suffix  # ".txt"
        parent = log_dosyasi.parent

        # En eski yedeği sil
        en_eski = parent / f"{stem}.{MAX_YEDEK_SAYISI}{suffix}"
        if en_eski.exists():
            en_eski.unlink()

        # Mevcut yedekleri kaydır: 4→5, 3→4, 2→3, 1→2
        for i in range(MAX_YEDEK_SAYISI - 1, 0, -1):
            eski = parent / f"{stem}.{i}{suffix}"
            yeni = parent / f"{stem}.{i + 1}{suffix}"
            if eski.exists():
                eski.rename(yeni)

        # Ana dosyayı .1 yap
        birinci = parent / f"{stem}.1{suffix}"
        log_dosyasi.rename(birinci)

    except Exception:
        pass  # Rotation hatası botu durdurmamalı


# ─────────────────────────────────────────────────────────────
# ANA LOG FONKSIYONU
# ─────────────────────────────────────────────────────────────


def guvenli_log_yaz(mesaj: str, log_dosyasi: Path, seviye: str = "INFO"):
    """PII maskeli ve rotation destekli log yazma.

    Args:
        mesaj: Log mesaji (PII otomatik maskelenir)
        log_dosyasi: Hedef log dosyasi Path'i
        seviye: Log seviyesi (INFO, UYARI, HATA, GUVENLIK)
    """
    try:
        # 1. PII maskele
        temiz_mesaj = maskele_pii(mesaj)

        # 2. Rotation kontrol
        _log_rotasyon(log_dosyasi)

        # 3. Yaz
        zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_dosyasi, "a", encoding="utf-8") as f:
            f.write(f"[{zaman}] [{seviye}] {temiz_mesaj}\n")
    except Exception:
        pass  # Log hatası botu durdurmamalı
