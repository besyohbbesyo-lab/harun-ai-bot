# core/audit_log.py — S5-8: Audit Log Sistemi
# Guvenlik olaylarini security.log dosyasina yazar
# ============================================================

from __future__ import annotations

import json
import time
from datetime import datetime
from enum import Enum
from pathlib import Path

# ── Log Dosyasi ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
SECURITY_LOG = BASE_DIR / "security.log"
MAX_BOYUT_BYTES = 5 * 1024 * 1024  # 5MB — rotation icin


class OlayTipi(str, Enum):
    # Giris / Kimlik
    GIRIS_BASARILI = "AUTH_SUCCESS"
    GIRIS_BASARISIZ = "AUTH_FAIL"
    YETKISIZ_ERISIM = "UNAUTHORIZED_ACCESS"

    # Injection / Guvenlik
    INJECTION_TESPIT = "INJECTION_DETECTED"
    INJECTION_ENGEL = "INJECTION_BLOCKED"
    RATE_LIMIT_ASIM = "RATE_LIMIT_EXCEEDED"

    # Komut / Islem
    KRITIK_KOMUT = "CRITICAL_COMMAND"
    ONAY_ISTENDI = "APPROVAL_REQUESTED"
    ONAY_VERILDI = "APPROVAL_GRANTED"
    ONAY_REDDEDILDI = "APPROVAL_DENIED"

    # Sistem
    BOT_BASLADI = "BOT_STARTED"
    BOT_DURDU = "BOT_STOPPED"
    API_HATA = "API_ERROR"
    BACKUP_ALINDI = "BACKUP_TAKEN"


def _rotation_kontrol():
    """Dosya 5MB'i astiysa .bak olarak yeniden adlandir."""
    if SECURITY_LOG.exists() and SECURITY_LOG.stat().st_size > MAX_BOYUT_BYTES:
        bak = SECURITY_LOG.with_suffix(".log.bak")
        SECURITY_LOG.rename(bak)


def audit_yaz(
    olay: OlayTipi | str,
    kullanici_id: int | str | None = None,
    detay: dict | str | None = None,
    seviye: str = "INFO",
):
    """
    Guvenlik olayini security.log dosyasina JSON satirı olarak yazar.

    Kullanim:
        audit_yaz(OlayTipi.INJECTION_TESPIT,
                  kullanici_id=123456,
                  detay={"mesaj": "/etc/passwd okuma girişimi"})
    """
    _rotation_kontrol()

    kayit = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "seviye": seviye,
        "olay": olay.value if isinstance(olay, OlayTipi) else str(olay),
        "uid": str(kullanici_id) if kullanici_id is not None else "system",
        "detay": detay if detay else {},
    }

    satir = json.dumps(kayit, ensure_ascii=False)
    try:
        with SECURITY_LOG.open("a", encoding="utf-8") as f:
            f.write(satir + "\n")
    except Exception:
        pass  # Log hatasi botu durdurmasin


def audit_giris(kullanici_id: int, basarili: bool = True):
    """Kimlik dogrulama olayini logla."""
    audit_yaz(
        OlayTipi.GIRIS_BASARILI if basarili else OlayTipi.GIRIS_BASARISIZ,
        kullanici_id=kullanici_id,
        seviye="INFO" if basarili else "WARNING",
    )


def audit_injection(kullanici_id: int, mesaj: str, engellendi: bool = True):
    """Injection tespit/engelleme olayini logla."""
    audit_yaz(
        OlayTipi.INJECTION_ENGEL if engellendi else OlayTipi.INJECTION_TESPIT,
        kullanici_id=kullanici_id,
        detay={"mesaj": mesaj[:200]},  # max 200 karakter
        seviye="WARNING",
    )


def audit_rate_limit(kullanici_id: int, limit: int):
    """Rate limit asimini logla."""
    audit_yaz(
        OlayTipi.RATE_LIMIT_ASIM,
        kullanici_id=kullanici_id,
        detay={"limit": limit},
        seviye="WARNING",
    )


def audit_kritik_komut(kullanici_id: int, komut: str, onaylandi: bool | None = None):
    """Kritik komut calistirilmasini logla."""
    if onaylandi is None:
        olay = OlayTipi.KRITIK_KOMUT
    elif onaylandi:
        olay = OlayTipi.ONAY_VERILDI
    else:
        olay = OlayTipi.ONAY_REDDEDILDI
    audit_yaz(olay, kullanici_id=kullanici_id, detay={"komut": komut}, seviye="WARNING")


def audit_sistem(olay: OlayTipi, detay: dict | None = None):
    """Sistem seviyesi olaylarini logla."""
    audit_yaz(olay, kullanici_id="system", detay=detay, seviye="INFO")


def son_olaylar(n: int = 50) -> list[dict]:
    """
    security.log dosyasindan son n olayi doner.
    /metrics veya /guvenlik komutundan cagrilabilir.
    """
    if not SECURITY_LOG.exists():
        return []
    satirlar = SECURITY_LOG.read_text(encoding="utf-8").strip().splitlines()
    son = satirlar[-n:] if len(satirlar) >= n else satirlar
    sonuc = []
    for s in reversed(son):
        try:
            sonuc.append(json.loads(s))
        except Exception:
            continue
    return sonuc
