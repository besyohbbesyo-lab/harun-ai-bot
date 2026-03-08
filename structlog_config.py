# structlog_config.py - S3-1: Yapilandirilmis loglama
# ============================================================
# Tum bot loglarini JSON formatinda, seviye bazli yonetir.
# Dosya + konsol ciktisi, gunluk rotasyon.
# ============================================================

import json
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

try:
    from bot_config import CFG

    _log_cfg = CFG.get("logging", {})
except Exception:
    _log_cfg = {}

# ── Prometheus-uyumlu basit sayaç (prometheus_client opsiyonel) ──
try:
    from prometheus_client import Counter, Histogram
    from prometheus_client import start_http_server as _prom_start

    _PROM_LOG_COUNTER = Counter("harun_log_total", "Toplam log kaydi", ["seviye"])
    _PROM_ENABLED = True
except ImportError:
    _PROM_ENABLED = False
    _PROM_LOG_COUNTER = None

BASE_DIR = Path(__file__).parent.resolve()
LOG_DIR = BASE_DIR / _log_cfg.get("dizin", "logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_SEVIYE = _log_cfg.get("seviye", "INFO").upper()
KONSOL_LOG = _log_cfg.get("konsol", True)
DOSYA_LOG = _log_cfg.get("dosya", True)
MAX_LOG_SATIR = int(_log_cfg.get("max_satir", 10000))

# Seviye numaralari
SEVIYELER = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40, "CRITICAL": 50}

# Son loglar (dashboard icin)
_son_loglar = deque(maxlen=100)


def _seviye_num(seviye: str) -> int:
    return SEVIYELER.get(seviye.upper(), 20)


def _bugunun_log_dosyasi() -> Path:
    tarih = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"bot_{tarih}.log"


class BotLogger:
    """Yapilandirilmis bot log sistemi."""

    def __init__(self):
        self.min_seviye = _seviye_num(LOG_SEVIYE)
        self._sayac = {"DEBUG": 0, "INFO": 0, "WARN": 0, "ERROR": 0}

    def _log(self, seviye: str, mesaj: str, trace_id: str = None, **ekstra):
        sev_num = _seviye_num(seviye)
        if sev_num < self.min_seviye:
            return

        self._sayac[seviye] = self._sayac.get(seviye, 0) + 1

        # Prometheus sayac
        if _PROM_ENABLED and _PROM_LOG_COUNTER:
            try:
                _PROM_LOG_COUNTER.labels(seviye=seviye).inc()
            except Exception:
                pass

        kayit = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "seviye": seviye,
            "mesaj": mesaj,
        }
        if trace_id:
            kayit["trace_id"] = trace_id
        if ekstra:
            kayit["ekstra"] = ekstra

        # Deque'ye ekle (dashboard icin)
        _son_loglar.append(kayit)

        # Konsol
        if KONSOL_LOG:
            renk = {"DEBUG": "", "INFO": "", "WARN": "⚠ ", "ERROR": "❌ ", "CRITICAL": "🔥 "}
            prefix = renk.get(seviye, "")
            ek_str = ""
            if ekstra:
                ek_str = " " + " ".join(f"{k}={v}" for k, v in ekstra.items())
            trace_str = f" [{trace_id}]" if trace_id else ""
            print(f"[{kayit['ts'][11:]}] [{seviye}]{prefix}{trace_str} {mesaj}{ek_str}")

        # Dosya
        if DOSYA_LOG:
            try:
                dosya = _bugunun_log_dosyasi()
                with open(dosya, "a", encoding="utf-8") as f:
                    f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def debug(self, mesaj, trace_id=None, **kw):
        self._log("DEBUG", mesaj, trace_id=trace_id, **kw)

    def info(self, mesaj, trace_id=None, **kw):
        self._log("INFO", mesaj, trace_id=trace_id, **kw)

    def warn(self, mesaj, trace_id=None, **kw):
        self._log("WARN", mesaj, trace_id=trace_id, **kw)

    def error(self, mesaj, trace_id=None, **kw):
        self._log("ERROR", mesaj, trace_id=trace_id, **kw)

    def critical(self, mesaj, trace_id=None, **kw):
        self._log("CRITICAL", mesaj, trace_id=trace_id, **kw)

    def son_loglar(self, n: int = 20) -> list:
        """Son n log kaydini dondur."""
        return list(_son_loglar)[-n:]

    def durum_ozeti(self) -> str:
        """Log durumu."""
        toplam = sum(self._sayac.values())
        return (
            f"[Logger] Toplam: {toplam} | "
            f"INFO:{self._sayac.get('INFO',0)} "
            f"WARN:{self._sayac.get('WARN',0)} "
            f"ERR:{self._sayac.get('ERROR',0)}"
        )


# Global instance
logger = BotLogger()
