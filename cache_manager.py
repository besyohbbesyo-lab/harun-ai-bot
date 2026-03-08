# cache_manager.py - S3-5: In-memory cache (TTL destekli)
# ============================================================
# Tekrarlayan sorgularda API cagrisi yapma — cache'den dondur.
# LRU + TTL mantigi, max boyut siniri.
# ============================================================

import hashlib
import time
from collections import OrderedDict

try:
    from bot_config import CFG

    _cache_cfg = CFG.get("cache", {})
except Exception:
    _cache_cfg = {}

MAX_BOYUT = int(_cache_cfg.get("max_boyut", 200))
VARSAYILAN_TTL = int(_cache_cfg.get("ttl_saniye", 300))  # 5 dakika


class CacheManager:
    """TTL destekli LRU cache."""

    def __init__(self, max_boyut=None, ttl=None):
        self.max_boyut = max_boyut or MAX_BOYUT
        self.ttl = ttl or VARSAYILAN_TTL
        self._cache = OrderedDict()  # {key: (value, expire_ts)}
        self._hit = 0
        self._miss = 0

    def _key_olustur(self, *args) -> str:
        """Argumanlari hash'e donustur."""
        ham = "|".join(str(a) for a in args)
        return hashlib.md5(ham.encode()).hexdigest()

    def al(self, key: str):
        """Cache'den deger al. Yoksa veya suresi dolmussa None."""
        if key not in self._cache:
            self._miss += 1
            return None

        value, expire_ts = self._cache[key]
        if time.time() > expire_ts:
            del self._cache[key]
            self._miss += 1
            return None

        # LRU: En son erisilen en sona git
        self._cache.move_to_end(key)
        self._hit += 1
        return value

    def koy(self, key: str, value, ttl: int = None):
        """Cache'e deger koy."""
        if ttl is None:
            ttl = self.ttl

        # Boyut siniri — en eski kaydi sil
        while len(self._cache) >= self.max_boyut:
            self._cache.popitem(last=False)

        self._cache[key] = (value, time.time() + ttl)

    def sil(self, key: str):
        """Cache'den sil."""
        self._cache.pop(key, None)

    def temizle(self):
        """Tum cache'i temizle."""
        self._cache.clear()
        self._hit = 0
        self._miss = 0

    def suresi_dolanlari_temizle(self):
        """Suresi dolan kayitlari temizle."""
        now = time.time()
        silinecek = [k for k, (_, exp) in self._cache.items() if now > exp]
        for k in silinecek:
            del self._cache[k]
        return len(silinecek)

    def hit_orani(self) -> float:
        """Cache hit orani (0.0 - 1.0)."""
        toplam = self._hit + self._miss
        return self._hit / toplam if toplam > 0 else 0.0

    def durum_ozeti(self) -> str:
        """Cache durumu."""
        toplam = self._hit + self._miss
        oran = f"{self.hit_orani()*100:.0f}%" if toplam > 0 else "n/a"
        return (
            f"[Cache] Boyut: {len(self._cache)}/{self.max_boyut} | "
            f"Hit: {self._hit} Miss: {self._miss} Oran: {oran}"
        )


# Global instance'lar
yanit_cache = CacheManager(max_boyut=200, ttl=300)  # AI yanit cache (5dk)
arama_cache = CacheManager(max_boyut=100, ttl=600)  # Arama cache (10dk)
