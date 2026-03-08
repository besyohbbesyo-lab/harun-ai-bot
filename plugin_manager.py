# plugin_manager.py — A3-4: Dinamik Plugin Yöneticisi
# ============================================================
# Pluginleri dinamik olarak yukler, kaydeder ve yonetir.
# Mevcut pluginler: code, memory, pdf, ses, vision, egitim,
#                   document, planner, search, pyautogui, pc_control
# ============================================================

import importlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Kayitli plugin modulleri
PLUGIN_KAYIT = {
    "code": "code_plugin",
    "memory": "memory_plugin",
    "pdf": "pdf_plugin",
    "ses": "ses_plugin",
    "vision": "vision_plugin",
    "egitim": "egitim_plugin",
    "document": "document_plugin",
    "planner": "planner_plugin",
    "search": "search_plugin",
    "pyautogui": "pyautogui_plugin",
    "pc": "pc_control_plugin",
}


class PluginManager:
    """
    Pluginleri dinamik olarak yukler ve yonetir.

    Kullanim:
        pm = PluginManager()
        pm.yukle("code")
        plugin = pm.al("code")
    """

    def __init__(self):
        self._yuklenmis: dict[str, Any] = {}
        self._hatali: dict[str, str] = {}

    def yukle(self, isim: str) -> bool:
        """Bir plugini yukle. Basarili ise True doner."""
        if isim in self._yuklenmis:
            return True

        modul_adi = PLUGIN_KAYIT.get(isim)
        if not modul_adi:
            logger.warning(f"[PluginManager] Bilinmeyen plugin: {isim}")
            return False

        try:
            modul = importlib.import_module(modul_adi)
            self._yuklenmis[isim] = modul
            logger.info(f"[PluginManager] Plugin yuklendi: {isim} ({modul_adi})")
            return True
        except ImportError as e:
            self._hatali[isim] = str(e)
            logger.warning(f"[PluginManager] Plugin yuklenemedi: {isim} — {e}")
            return False
        except Exception as e:
            self._hatali[isim] = str(e)
            logger.error(f"[PluginManager] Plugin hatasi: {isim} — {e}")
            return False

    def yukle_hepsini(self) -> dict[str, bool]:
        """Tum kayitli pluginleri yukle. {isim: basarili} doner."""
        sonuclar = {}
        for isim in PLUGIN_KAYIT:
            sonuclar[isim] = self.yukle(isim)
        return sonuclar

    def al(self, isim: str) -> Optional[Any]:
        """Yuklenmis plugin modulunu doner. Yuklu degilse None."""
        if isim not in self._yuklenmis:
            self.yukle(isim)
        return self._yuklenmis.get(isim)

    def kaldir(self, isim: str) -> bool:
        """Plugini bellekten kaldir."""
        if isim in self._yuklenmis:
            del self._yuklenmis[isim]
            logger.info(f"[PluginManager] Plugin kaldirildi: {isim}")
            return True
        return False

    def yeniden_yukle(self, isim: str) -> bool:
        """Plugini bellekten silip tekrar yukle."""
        self.kaldir(isim)
        if isim in self._hatali:
            del self._hatali[isim]
        return self.yukle(isim)

    def aktif_pluginler(self) -> list[str]:
        """Yuklenmis plugin isimlerini doner."""
        return list(self._yuklenmis.keys())

    def hatali_pluginler(self) -> dict[str, str]:
        """Yuklenemeyen pluginleri ve hata mesajlarini doner."""
        return dict(self._hatali)

    def durum_ozeti(self) -> str:
        """Plugin durumu ozeti (Telegram /status icin)."""
        satirlar = ["🔌 *Plugin Durumu*"]
        for isim in PLUGIN_KAYIT:
            if isim in self._yuklenmis:
                satirlar.append(f"  ✅ {isim}")
            elif isim in self._hatali:
                satirlar.append(f"  ❌ {isim}: {self._hatali[isim][:40]}")
            else:
                satirlar.append(f"  ⏸️ {isim} (yuklenmedi)")
        return "\n".join(satirlar)

    def __repr__(self):
        return (
            f"PluginManager("
            f"aktif={len(self._yuklenmis)}, "
            f"hatali={len(self._hatali)}, "
            f"toplam={len(PLUGIN_KAYIT)})"
        )


# Global singleton
plugin_manager = PluginManager()
