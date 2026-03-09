# core/resilience.py — CircuitBreaker + Retry + Timeout
# Master Plan S1-3: Mistral (CircuitBreaker) + Gemini (exponential backoff) + Claude-8 (timeout)
# ============================================================
# Kullanim:
#   from core.resilience import CircuitBreaker, retry_async, cb_groq, cb_ollama
#
#   # Yeni provider icin:
#   cb = CircuitBreaker(name="Groq", threshold=5, timeout=60)
#   result = await cb.call(ask_groq, prompt)
# ============================================================

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any, Optional

# ── CircuitBreaker ────────────────────────────────────────────


class CircuitBreaker:
    """
    3 durumlu devre kesici:
      CLOSED    → Normal calisma. Hatalar sayilir.
      OPEN      → Servis devre disi. Hemen hata firlat.
      HALF_OPEN → Deneme modu. Tek deneme yapilir.
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, name: str, threshold: int = 5, timeout: float = 60.0):
        """
        name      : Log icin servis adi (ornk. 'Groq', 'Ollama')
        threshold : Kac hata sonra OPEN'a gececegi
        timeout   : OPEN → HALF_OPEN gecisi icin bekleme suresi (saniye)
        """
        self.name = name
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.state = self.CLOSED
        self.opened_at: float | None = None
        self._lock = asyncio.Lock()

    # ── Durum geciş yardımcıları ──────────────────────────────

    def _gecis_kontrol(self):
        """OPEN durumda timeout gectiyse HALF_OPEN'a gec."""
        if self.state == self.OPEN:
            if time.time() - (self.opened_at or 0) >= self.timeout:
                self.state = self.HALF_OPEN
                print(f"[CB:{self.name}] OPEN → HALF_OPEN (deneme modu)")

    def _basari(self):
        """Basarili cagri sonrasi durumu sifirla."""
        if self.state == self.HALF_OPEN:
            print(f"[CB:{self.name}] HALF_OPEN → CLOSED (iyilesti)")
        self.failures = 0
        self.state = self.CLOSED
        self.opened_at = None

    def _hata(self, exc: Exception):
        """Hatali cagri sonrasi sayaci artir, gerekirse OPEN'a gec."""
        self.failures += 1
        if self.state == self.HALF_OPEN or self.failures >= self.threshold:
            self.state = self.OPEN
            self.opened_at = time.time()
            print(
                f"[CB:{self.name}] → OPEN "
                f"(hata:{self.failures}, timeout:{self.timeout}s) — {exc}"
            )
        else:
            print(f"[CB:{self.name}] hata {self.failures}/{self.threshold}: {exc}")

    # ── Ana cagri ────────────────────────────────────────────

    async def call(self, fn: Callable, *args, hard_timeout: float = 30.0, **kwargs) -> Any:
        """
        fn fonksiyonunu CircuitBreaker + hard timeout ile cagir.

        hard_timeout : asyncio.timeout suresi (saniye). 0 = devre disi.
        """
        async with self._lock:
            self._gecis_kontrol()

            if self.state == self.OPEN:
                kalan = self.timeout - (time.time() - (self.opened_at or 0))
                raise CircuitOpenError(
                    f"[CB:{self.name}] Devre ACIK — " f"{kalan:.0f}s sonra tekrar denenecek"
                )

        # Kilidi serbest birak, asil cagrıyı yap
        try:
            if hard_timeout > 0:
                async with asyncio.timeout(hard_timeout):
                    if asyncio.iscoroutinefunction(fn):
                        result = await fn(*args, **kwargs)
                    else:
                        loop = asyncio.get_running_loop()
                        result = await loop.run_in_executor(
                            None, functools.partial(fn, *args, **kwargs)
                        )
            else:
                if asyncio.iscoroutinefunction(fn):
                    result = await fn(*args, **kwargs)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, functools.partial(fn, *args, **kwargs)
                    )

            async with self._lock:
                self._basari()
            return result

        except CircuitOpenError:
            raise
        except Exception as exc:
            async with self._lock:
                self._hata(exc)
            raise

    # ── Durum raporu ─────────────────────────────────────────

    def durum(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "failures": self.failures,
            "threshold": self.threshold,
            "opened_at": self.opened_at,
        }

    def __repr__(self):
        return f"<CircuitBreaker name={self.name} state={self.state} failures={self.failures}>"


class CircuitOpenError(Exception):
    """CircuitBreaker OPEN durumunda firlatilan ozel hata."""

    pass


# ── Retry decorator ──────────────────────────────────────────


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
):
    """
    Exponential backoff ile async retry decorator.

    Kullanim:
        @retry_async(max_attempts=3, base_delay=1.0)
        async def ask_groq(prompt):
            ...
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            deneme = 0
            while deneme < max_attempts:
                try:
                    return await fn(*args, **kwargs)
                except exceptions as e:
                    deneme += 1
                    if deneme >= max_attempts:
                        raise
                    delay = min(base_delay * (2 ** (deneme - 1)), max_delay)
                    print(
                        f"[Retry] {fn.__name__} hata ({deneme}/{max_attempts}): "
                        f"{e} — {delay:.1f}s bekle"
                    )
                    await asyncio.sleep(delay)

        return wrapper

    return decorator


# ── Hazir CircuitBreaker instance'lari ───────────────────────
# chat_service.py ve diger moduller bunlari import eder.

cb_groq = CircuitBreaker(name="Groq", threshold=5, timeout=60)
cb_gemini = CircuitBreaker(name="Gemini", threshold=3, timeout=90)
cb_ollama = CircuitBreaker(name="Ollama", threshold=3, timeout=30)


# ── Durum ozeti ──────────────────────────────────────────────


def cb_durum_raporu() -> dict:
    """Tum CircuitBreaker'larin durumunu tek sozlukte dondur."""
    return {cb.name: cb.durum() for cb in [cb_groq, cb_gemini, cb_ollama]}
