# core/plugin_sandbox.py — S6-6: Plugin Process İzolasyonu
# subprocess + multiprocessing.Queue ile izole calistirma
# Her plugin cagri ayri process'te, ana bot etkilenmez
# ============================================================

from __future__ import annotations

import json
import multiprocessing
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from core.config import log_yaz

# Timeout degerleri
PLUGIN_TIMEOUT = 30.0  # Plugin cagri maksimum suresi (sn)
PROCESS_STARTUP = 2.0  # Process baslatma bekleme suresi (sn)


# ── IPC Worker (izole process'te calisir) ────────────────────


def _plugin_worker(
    plugin_module: str,
    plugin_func: str,
    args: tuple,
    kwargs: dict,
    sonuc_queue: multiprocessing.Queue,
):
    """
    Ayri process'te plugin fonksiyonunu calistirir.
    Sonucu queue'ya koyar: {"ok": True, "sonuc": ...} veya {"ok": False, "hata": ...}
    """
    try:
        # Modulu dinamik yukle
        import importlib

        modul = importlib.import_module(plugin_module)
        fonksiyon = getattr(modul, plugin_func)
        sonuc = fonksiyon(*args, **kwargs)
        sonuc_queue.put({"ok": True, "sonuc": sonuc})
    except Exception as e:
        hata = {
            "ok": False,
            "hata": str(e),
            "traceback": traceback.format_exc()[-500:],
        }
        sonuc_queue.put(hata)


# ── Ana Sandbox Sinifi ────────────────────────────────────────


class PluginSandbox:
    """
    Plugin'leri izole process'lerde calistirir.

    Kullanim:
        sandbox = PluginSandbox()
        sonuc = sandbox.calistir("search_plugin", "ara", args=("python",))
    """

    def __init__(self, timeout: float = PLUGIN_TIMEOUT):
        self.timeout = timeout
        self._istatistik = {
            "toplam": 0,
            "basarili": 0,
            "zaman_asimi": 0,
            "hata": 0,
        }

    def calistir(
        self,
        plugin_module: str,
        plugin_func: str,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> dict:
        """
        Plugin fonksiyonunu izole process'te calistirir.

        Returns:
            {"ok": True, "sonuc": ..., "sure": float}
            {"ok": False, "hata": str, "sure": float}
        """
        if kwargs is None:
            kwargs = {}

        self._istatistik["toplam"] += 1
        baslangic = time.time()

        # IPC Queue
        q: multiprocessing.Queue = multiprocessing.Queue()

        # Izole process olustur
        p = multiprocessing.Process(
            target=_plugin_worker,
            args=(plugin_module, plugin_func, args, kwargs, q),
            daemon=True,
        )

        try:
            p.start()
            p.join(timeout=self.timeout)

            sure = time.time() - baslangic

            if p.is_alive():
                # Timeout — process'i zorla sonlandir
                p.terminate()
                p.join(timeout=1.0)
                if p.is_alive():
                    p.kill()

                self._istatistik["zaman_asimi"] += 1
                log_yaz(
                    f"[Sandbox] {plugin_module}.{plugin_func} " f"{self.timeout}s timeout'a ugradi",
                    "WARNING",
                )
                return {
                    "ok": False,
                    "hata": f"Plugin timeout: {self.timeout}s asimi",
                    "sure": sure,
                }

            # Queue'dan sonucu al
            if not q.empty():
                sonuc = q.get_nowait()
                sonuc["sure"] = sure
                if sonuc.get("ok"):
                    self._istatistik["basarili"] += 1
                else:
                    self._istatistik["hata"] += 1
                    log_yaz(
                        f"[Sandbox] {plugin_module}.{plugin_func} hata: "
                        f"{sonuc.get('hata', '?')}",
                        "WARNING",
                    )
                return sonuc
            else:
                self._istatistik["hata"] += 1
                return {
                    "ok": False,
                    "hata": "Plugin sonuc donmedi (process erken kapandi)",
                    "sure": sure,
                }

        except Exception as e:
            sure = time.time() - baslangic
            self._istatistik["hata"] += 1
            log_yaz(f"[Sandbox] Process hatasi: {e}", "ERROR")
            if p.is_alive():
                p.terminate()
            return {"ok": False, "hata": str(e), "sure": sure}

    def istatistik(self) -> dict:
        """Sandbox kullanim istatistiklerini doner."""
        ist = dict(self._istatistik)
        toplam = ist["toplam"] or 1
        ist["basari_orani"] = int(ist["basarili"] / toplam * 100)
        return ist


# ── Subprocess tabanlı hafif sandbox ────────────────────────


def subprocess_calistir(
    kod: str,
    timeout: float = 10.0,
    env: dict | None = None,
) -> dict:
    """
    Kodu tamamen izole bir Python subprocess'te calistirir.
    code_runner plugin'i icin — kod yurutme sandbox'i.

    Returns:
        {"ok": True/False, "cikti": str, "hata": str, "sure": float}
    """
    baslangic = time.time()
    try:
        sonuc = subprocess.run(
            [sys.executable, "-c", kod],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        sure = time.time() - baslangic
        if sonuc.returncode == 0:
            return {"ok": True, "cikti": sonuc.stdout[:2000], "hata": "", "sure": sure}
        else:
            return {
                "ok": False,
                "cikti": sonuc.stdout[:500],
                "hata": sonuc.stderr[:500],
                "sure": sure,
            }
    except subprocess.TimeoutExpired:
        sure = time.time() - baslangic
        return {"ok": False, "cikti": "", "hata": f"Timeout: {timeout}s", "sure": sure}
    except Exception as e:
        sure = time.time() - baslangic
        return {"ok": False, "cikti": "", "hata": str(e), "sure": sure}


# ── Global singleton ─────────────────────────────────────────
_sandbox: PluginSandbox | None = None


def get_sandbox() -> PluginSandbox:
    """Global PluginSandbox singleton'ini doner."""
    global _sandbox
    if _sandbox is None:
        _sandbox = PluginSandbox()
    return _sandbox
