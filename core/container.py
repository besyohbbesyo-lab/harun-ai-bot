# core/container.py — A4-1: Dependency Injection Container
# ============================================================
# Tum servisleri tek bir yerden olusturur ve inject eder.
# globals.py'yi bozmaz — ek katman olarak calisir.
# ============================================================

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class Container:
    """
    Basit Dependency Injection Container.

    Kullanim:
        container = Container()

        # Singleton kayit
        container.singleton("metrics", lambda: BotMetrics())

        # Factory kayit (her cagirda yeni instance)
        container.factory("session", lambda: Session())

        # Coz
        metrics = container.resolve("metrics")
    """

    def __init__(self):
        self._singletonlar: dict[str, Any] = {}
        self._fabrikalar: dict[str, Callable] = {}
        self._instance_lar: dict[str, Any] = {}

    def singleton(self, isim: str, fabrika: Callable) -> Container:
        """Singleton olarak kaydet — ilk cagirda olusturulur, sonra cache'lenir."""
        self._singletonlar[isim] = fabrika
        return self

    def factory(self, isim: str, fabrika: Callable) -> Container:
        """Factory olarak kaydet — her resolve'da yeni instance olusturulur."""
        self._fabrikalar[isim] = fabrika
        return self

    def instance(self, isim: str, nesne: Any) -> Container:
        """Hazir nesneyi direkt kaydet."""
        self._instance_lar[isim] = nesne
        return self

    def resolve(self, isim: str) -> Any:
        """Kayitli servisi doner. Bulunamazsa KeyError firlatir."""
        # Once hazir instance'lara bak
        if isim in self._instance_lar:
            return self._instance_lar[isim]

        # Singleton — cache'e bak, yoksa olustur
        if isim in self._singletonlar:
            if isim not in self._instance_lar:
                try:
                    self._instance_lar[isim] = self._singletonlar[isim]()
                    logger.debug(f"[Container] Singleton olusturuldu: {isim}")
                except Exception as e:
                    logger.error(f"[Container] Singleton hatasi: {isim} — {e}")
                    raise
            return self._instance_lar[isim]

        # Factory — her seferinde yeni
        if isim in self._fabrikalar:
            try:
                return self._fabrikalar[isim]()
            except Exception as e:
                logger.error(f"[Container] Factory hatasi: {isim} — {e}")
                raise

        raise KeyError(f"[Container] Kayitli servis bulunamadi: '{isim}'")

    def resolve_opsiyonel(self, isim: str, varsayilan: Any = None) -> Any:
        """Servisi doner, bulunamazsa varsayilani doner (hata vermez)."""
        try:
            return self.resolve(isim)
        except KeyError:
            return varsayilan

    def kayitli_mi(self, isim: str) -> bool:
        """Servis kayitli mi?"""
        return isim in self._instance_lar or isim in self._singletonlar or isim in self._fabrikalar

    def tum_isimler(self) -> list:
        """Tum kayitli servis isimlerini doner."""
        isimler: set[str] = set()
        isimler.update(self._singletonlar.keys())
        isimler.update(self._fabrikalar.keys())
        isimler.update(self._instance_lar.keys())
        return sorted(isimler)

    def durum_ozeti(self) -> str:
        """Container durumu ozeti."""
        satirlar = ["🏗️ *DI Container Durumu*"]
        for isim in self.tum_isimler():
            if isim in self._instance_lar:
                tip = "✅ instance"
            elif isim in self._singletonlar:
                tip = "⏸️ singleton (lazy)"
            else:
                tip = "🔄 factory"
            satirlar.append(f"  {tip}: {isim}")
        return "\n".join(satirlar)

    def __repr__(self):
        return (
            f"Container("
            f"singleton={len(self._singletonlar)}, "
            f"factory={len(self._fabrikalar)}, "
            f"instance={len(self._instance_lar)})"
        )


# ── Bot servislerini kaydet ──────────────────────────────────


def bot_container_olustur() -> Container:
    """
    Bot icin hazir DI container olusturur.
    globals.py'deki nesneleri wrap eder.
    """
    c = Container()

    # Metrics singleton
    c.singleton("metrics", lambda: _yukle("monitoring.metrics", "BotMetrics"))

    # Token budget singleton
    c.singleton("token_budget", lambda: _yukle("token_budget", "TokenBudget"))

    # Plugin manager singleton
    c.singleton("plugin_manager", lambda: _yukle("plugin_manager", "PluginManager"))

    # Hybrid RAG factory
    c.factory("hybrid_search", lambda: _yukle_fonk("hybrid_rag", "hybrid_search"))

    return c


def _yukle(modul: str, sinif: str) -> Any:
    """Modulu yukle ve sinifi olustur."""
    import importlib

    m = importlib.import_module(modul)
    return getattr(m, sinif)()


def _yukle_fonk(modul: str, fonk: str) -> Any:
    """Modulu yukle ve fonksiyonu doner."""
    import importlib

    m = importlib.import_module(modul)
    return getattr(m, fonk)


# Global container
container = bot_container_olustur()
