# core/config.py — S5-3: globals.py refactoring
# Sorumluluk: Ortam degiskenleri, yollar, log altyapisi

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from log_utils import guvenli_log_yaz

load_dotenv()

# ── Ortam Degiskenleri ────────────────────────────────────────
TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── Yollar ───────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
MASAUSTU = Path.home() / "Desktop"
LOG_DOSYASI = BASE_DIR / "bot_log.txt"


# ── Log Fonksiyonu ────────────────────────────────────────────
def log_yaz(mesaj: str, seviye: str = "INFO"):
    """Bot loglarini PII maskeli ve rotation destekli yaz."""
    try:
        guvenli_log_yaz(mesaj, LOG_DOSYASI, seviye)
    except Exception:
        pass


# ── Uptime ────────────────────────────────────────────────────
BASLANGIC_ZAMANI = None


def baslangic_zamanini_kaydet():
    global BASLANGIC_ZAMANI
    BASLANGIC_ZAMANI = datetime.now()


def uptime_hesapla() -> str:
    if BASLANGIC_ZAMANI is None:
        return "Bilinmiyor"
    gecen = datetime.now() - BASLANGIC_ZAMANI
    saat = int(gecen.total_seconds() // 3600)
    dakika = int((gecen.total_seconds() % 3600) // 60)
    return f"{saat} saat {dakika} dakika"


# ── Yardimci ─────────────────────────────────────────────────
def son_dosyayi_bul(desktop_dir: Path, ext: str, prefix: str | None = None) -> Path | None:
    if not desktop_dir.exists():
        return None
    pat = f"{prefix}*.{ext}" if prefix else f"*.{ext}"
    dosyalar = list(desktop_dir.glob(pat))
    if not dosyalar:
        return None
    dosyalar.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dosyalar[0]
