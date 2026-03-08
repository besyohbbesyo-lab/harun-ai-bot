# core/rate_limiter_v2.py — S7-4: Rate Limiter v2
# Sliding window + kullanici bazli kota
# Sprint 1'deki basit rate limiter'in gelismis versiyonu
# ============================================================

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from core.config import log_yaz

# ── Kota Tanimlari ────────────────────────────────────────────


@dataclass
class Kota:
    """Kullanici kotasi tanimi."""

    istek_sayisi: int  # Pencere icinde izin verilen max istek
    pencere_sn: float  # Pencere suresi (saniye)
    ad: str = "varsayilan"


# Hazir kotalar
KOTA_VARSAYILAN = Kota(istek_sayisi=10, pencere_sn=60, ad="varsayilan")
KOTA_PREMIUM = Kota(istek_sayisi=50, pencere_sn=60, ad="premium")
KOTA_ADMIN = Kota(istek_sayisi=200, pencere_sn=60, ad="admin")
KOTA_BURST = Kota(istek_sayisi=5, pencere_sn=10, ad="burst")  # 10sn burst


@dataclass
class PencereDurumu:
    """Kullanici icin sliding window durumu."""

    istekler: deque = field(default_factory=deque)  # istek zaman damgalari
    engellendi: int = 0  # engellenen istek sayisi
    toplam: int = 0  # toplam istek sayisi


# ── Sliding Window Rate Limiter ───────────────────────────────


class SlidingWindowLimiter:
    """
    Sliding window algoritmasiyla rate limiting.

    Sprint 1'deki TokenBucket'tan farki:
    - Kesin pencere: son N saniyedeki istekleri sayar
    - Kullanici bazli farkli kotalar
    - Async destekli
    - Detayli istatistik

    Kullanim:
        limiter = SlidingWindowLimiter()
        izin, bilgi = limiter.kontrol_et(kullanici_id, kota=KOTA_PREMIUM)
        if not izin:
            await mesaj.reply(f"Limit: {bilgi['bekleme_sn']:.0f}s bekle")
    """

    def __init__(self):
        self._pencereler: dict[str, PencereDurumu] = defaultdict(PencereDurumu)
        self._ozel_kotalar: dict[str, Kota] = {}  # kullanici → ozel kota
        self._lock = asyncio.Lock()

    def _temizle(self, durum: PencereDurumu, simdi: float, pencere_sn: float):
        """Pencere disindaki eski istekleri temizle."""
        sinir = simdi - pencere_sn
        while durum.istekler and durum.istekler[0] < sinir:
            durum.istekler.popleft()

    def kontrol_et(
        self,
        kullanici_id: str | int,
        kota: Kota | None = None,
    ) -> tuple[bool, dict]:
        """
        Sync rate limit kontrolu.

        Returns:
            (izin_var: bool, bilgi: dict)
            bilgi iceriği: mevcut_istek, kalan, bekleme_sn, kota_adi
        """
        anahtar = str(kullanici_id)
        kota = self._ozel_kotalar.get(anahtar) or kota or KOTA_VARSAYILAN
        simdi = time.time()

        durum = self._pencereler[anahtar]
        self._temizle(durum, simdi, kota.pencere_sn)

        mevcut = len(durum.istekler)
        durum.toplam += 1

        if mevcut >= kota.istek_sayisi:
            durum.engellendi += 1
            en_eski = durum.istekler[0] if durum.istekler else simdi
            bekleme = (en_eski + kota.pencere_sn) - simdi
            log_yaz(
                f"[RateLimiter] {anahtar} engellendi "
                f"({mevcut}/{kota.istek_sayisi}, {bekleme:.1f}s bekle)",
                "WARNING",
            )
            return False, {
                "mevcut_istek": mevcut,
                "kalan": 0,
                "bekleme_sn": max(0.0, bekleme),
                "kota_adi": kota.ad,
                "engellendi": durum.engellendi,
            }

        durum.istekler.append(simdi)
        return True, {
            "mevcut_istek": mevcut + 1,
            "kalan": kota.istek_sayisi - mevcut - 1,
            "bekleme_sn": 0.0,
            "kota_adi": kota.ad,
            "engellendi": durum.engellendi,
        }

    async def kontrol_et_async(
        self,
        kullanici_id: str | int,
        kota: Kota | None = None,
    ) -> tuple[bool, dict]:
        """Async rate limit kontrolu — thread-safe."""
        async with self._lock:
            return self.kontrol_et(kullanici_id, kota)

    def ozel_kota_ata(self, kullanici_id: str | int, kota: Kota):
        """Kullaniciya ozel kota ata (premium, admin vb)."""
        self._ozel_kotalar[str(kullanici_id)] = kota
        log_yaz(f"[RateLimiter] {kullanici_id} → {kota.ad} kotasi", "INFO")

    def sifirla(self, kullanici_id: str | int | None = None):
        """Kullanici veya tum pencereleri sifirla."""
        if kullanici_id:
            self._pencereler.pop(str(kullanici_id), None)
        else:
            self._pencereler.clear()

    def istatistik(self, kullanici_id: str | int | None = None) -> dict:
        """Rate limit istatistiklerini doner."""
        if kullanici_id:
            anahtar = str(kullanici_id)
            durum = self._pencereler.get(anahtar)
            if not durum:
                return {"kullanici": anahtar, "toplam": 0, "engellendi": 0}
            return {
                "kullanici": anahtar,
                "toplam": durum.toplam,
                "engellendi": durum.engellendi,
                "aktif_istek": len(durum.istekler),
            }
        return {
            "toplam_kullanici": len(self._pencereler),
            "toplam_istek": sum(d.toplam for d in self._pencereler.values()),
            "toplam_engellendi": sum(d.engellendi for d in self._pencereler.values()),
        }


# ── Global Singleton ──────────────────────────────────────────
_limiter: SlidingWindowLimiter | None = None


def get_limiter() -> SlidingWindowLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowLimiter()
    return _limiter
