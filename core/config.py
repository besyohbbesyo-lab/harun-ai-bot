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
_UPTIME_DOSYA = BASE_DIR / "data" / "uptime.json"


def baslangic_zamanini_kaydet():
    """Bot baslatilinca cagrilir — zamani hem bellek hem diske yazar."""
    global BASLANGIC_ZAMANI
    BASLANGIC_ZAMANI = datetime.now()
    try:
        import json

        _UPTIME_DOSYA.parent.mkdir(parents=True, exist_ok=True)
        _UPTIME_DOSYA.write_text(
            json.dumps({"baslangic": BASLANGIC_ZAMANI.isoformat()}), encoding="utf-8"
        )
    except Exception:
        pass


def _uptime_diskten_oku():
    """BASLANGIC_ZAMANI None ise diskten okumaya calis."""
    global BASLANGIC_ZAMANI
    try:
        import json

        if _UPTIME_DOSYA.exists():
            veri = json.loads(_UPTIME_DOSYA.read_text(encoding="utf-8"))
            BASLANGIC_ZAMANI = datetime.fromisoformat(veri["baslangic"])
    except Exception:
        pass


def uptime_hesapla() -> str:
    """Uptime stringi doner — bellekte yoksa diskten okur."""
    if BASLANGIC_ZAMANI is None:
        _uptime_diskten_oku()
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
