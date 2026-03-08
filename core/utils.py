# core/utils.py - Yardimci fonksiyonlar
# normalize_provider, log_yaz, son_dosyayi_bul

from pathlib import Path

from bot_config import CFG
from log_utils import guvenli_log_yaz

# LOG_DOSYASI sonradan set edilir (circular import onlemi)
LOG_DOSYASI = None


def set_log_dosyasi(path: Path):
    global LOG_DOSYASI
    LOG_DOSYASI = path


def normalize_provider(p: dict | None) -> dict:
    """Provider sozlugunu canonical semaya donustur.
    Eski 'isim' anahtarini 'name' olarak normalize eder.
    Boylece KeyError riski ortadan kalkar."""
    if not p:
        _groq = CFG.get("groq", {})
        return {
            "name": "Groq",
            "mode": "cloud",
            "api_key": "",
            "model": _groq.get("default_model", "llama-3.1-8b-instant"),
            "max_tokens": _groq.get("default_max_tokens", 2000),
        }
    p = dict(p)  # kopya — orijinali bozma
    if "isim" in p and "name" not in p:
        p["name"] = p.pop("isim")
    if "mode" not in p:
        p["mode"] = "cloud"
    return p


def _safe_active_provider(rotator_obj):
    """
    Farkli api_rotator surumleriyle uyum icin:
    - aktif_provider_al()
    - get_active_provider()
    - active_provider
    Her zaman normalize_provider() ile canonical sema doner.
    """
    if rotator_obj is None:
        return normalize_provider(None)
    if hasattr(rotator_obj, "aktif_provider_al"):
        return normalize_provider(rotator_obj.aktif_provider_al())
    if hasattr(rotator_obj, "get_active_provider"):
        return normalize_provider(rotator_obj.get_active_provider())
    # en son fallback
    return normalize_provider(None)


def log_yaz(mesaj: str, seviye: str = "INFO"):
    """Bot loglarini PII maskeli ve rotation destekli yaz."""
    try:
        guvenli_log_yaz(mesaj, LOG_DOSYASI, seviye)
    except Exception:
        pass


def son_dosyayi_bul(desktop_dir: Path, ext: str, prefix: str | None = None) -> Path | None:
    """Desktop altında en yeni dosyayı bulur. prefix verilirse onunla başlayanları filtreler."""
    if not desktop_dir.exists():
        return None
    pat = f"{prefix}*.{ext}" if prefix else f"*.{ext}"
    dosyalar = list(desktop_dir.glob(pat))
    if not dosyalar:
        return None
    dosyalar.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dosyalar[0]
