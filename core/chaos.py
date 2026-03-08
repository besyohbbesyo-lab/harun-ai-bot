# core/chaos.py — S7-2: Chaos Engineering
# Rastgele hata enjeksiyonu ile sistem dayanikliligini test eder
# SADECE staging/test ortaminda aktif, production'da devre disi
# ============================================================

from __future__ import annotations

import asyncio
import functools
import os
import random
import time
from collections.abc import Callable

from core.config import log_yaz

# ── Chaos sadece staging/test ortaminda aktif ─────────────────
BOT_ENV = os.getenv("BOT_ENV", "production")
CHAOS_AKTIF = BOT_ENV in ("staging", "test", "chaos")

# ── Varsayilan olasiliklar ────────────────────────────────────
HATA_OLASILIGI = 0.05  # %5 — exception firlatir
GECIKME_OLASILIGI = 0.10  # %10 — yapay gecikme ekler
GECIKME_MAKS = 3.0  # Maksimum gecikme (sn)


class ChaosHatasi(Exception):
    """Chaos engineering tarafindan enjekte edilen hata."""

    pass


# ── Chaos Motoru ──────────────────────────────────────────────


class ChaosMotoru:
    """
    Kontrollü hata ve gecikme enjeksiyonu.

    Kullanim:
        motor = ChaosMotoru(hata_olasiligi=0.1)
        motor.hata_enjekte_et("groq_api")   # %10 ihtimalle exception
        await motor.gecikme_enjekte_et()    # %10 ihtimalle 0-3s gecikme
    """

    def __init__(
        self,
        hata_olasiligi: float = HATA_OLASILIGI,
        gecikme_olasiligi: float = GECIKME_OLASILIGI,
        gecikme_maks: float = GECIKME_MAKS,
        aktif: bool | None = None,
    ):
        self.hata_olasiligi = hata_olasiligi
        self.gecikme_olasiligi = gecikme_olasiligi
        self.gecikme_maks = gecikme_maks
        self.aktif = aktif if aktif is not None else CHAOS_AKTIF

        self._istatistik = {
            "hata_enjekte": 0,
            "gecikme_enjekte": 0,
            "kontrol_sayisi": 0,
        }

    def hata_enjekte_et(self, kaynak: str = "bilinmiyor") -> None:
        """
        Olasiliga gore ChaosHatasi firlatir.
        Production'da hic calismaz.
        """
        if not self.aktif:
            return

        self._istatistik["kontrol_sayisi"] += 1

        if random.random() < self.hata_olasiligi:
            self._istatistik["hata_enjekte"] += 1
            log_yaz(f"[Chaos] Hata enjekte edildi → {kaynak}", "WARNING")
            raise ChaosHatasi(f"Chaos: {kaynak} rastgele hatasi")

    async def gecikme_enjekte_et(self, kaynak: str = "bilinmiyor") -> None:
        """
        Olasiliga gore yapay gecikme ekler.
        Production'da hic calismaz.
        """
        if not self.aktif:
            return

        self._istatistik["kontrol_sayisi"] += 1

        if random.random() < self.gecikme_olasiligi:
            sure = random.uniform(0.1, self.gecikme_maks)
            self._istatistik["gecikme_enjekte"] += 1
            log_yaz(f"[Chaos] Gecikme enjekte edildi → {kaynak}: {sure:.2f}s", "WARNING")
            await asyncio.sleep(sure)

    def gecikme_enjekte_et_sync(self, kaynak: str = "bilinmiyor") -> None:
        """Sync versiyon — time.sleep kullanir."""
        if not self.aktif:
            return

        self._istatistik["kontrol_sayisi"] += 1

        if random.random() < self.gecikme_olasiligi:
            sure = random.uniform(0.1, self.gecikme_maks)
            self._istatistik["gecikme_enjekte"] += 1
            log_yaz(f"[Chaos] Gecikme enjekte edildi (sync) → {kaynak}: {sure:.2f}s", "WARNING")
            time.sleep(sure)

    def istatistik(self) -> dict:
        ist = dict(self._istatistik)
        ist["aktif"] = self.aktif
        ist["hata_olasiligi"] = self.hata_olasiligi
        return ist

    def sifirla(self):
        """Istatistikleri sifirla."""
        for k in self._istatistik:
            self._istatistik[k] = 0


# ── Decorator ─────────────────────────────────────────────────


def chaos(
    hata_olasiligi: float = HATA_OLASILIGI,
    gecikme_olasiligi: float = GECIKME_OLASILIGI,
    aktif: bool | None = None,
):
    """
    Fonksiyonlara chaos enjekte eden decorator.

    Kullanim:
        @chaos(hata_olasiligi=0.1)
        async def groq_api_cagri(...): ...
    """
    motor = ChaosMotoru(
        hata_olasiligi=hata_olasiligi,
        gecikme_olasiligi=gecikme_olasiligi,
        aktif=aktif,
    )

    def decorator(func: Callable) -> Callable:
        isim = f"{func.__module__}.{func.__qualname__}"

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                motor.hata_enjekte_et(isim)
                await motor.gecikme_enjekte_et(isim)
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                motor.hata_enjekte_et(isim)
                motor.gecikme_enjekte_et_sync(isim)
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


# ── Global singleton (staging icin) ──────────────────────────
_motor: ChaosMotoru | None = None


def get_chaos_motor() -> ChaosMotoru:
    global _motor
    if _motor is None:
        _motor = ChaosMotoru()
    return _motor
