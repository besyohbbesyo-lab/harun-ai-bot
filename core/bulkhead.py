# core/bulkhead.py — S6-7: HTTP Timeout + Bulkhead Pattern
# asyncio.Semaphore ile max 3 esz zamanli API istegi siniri
# ============================================================

from __future__ import annotations

import asyncio
from functools import wraps

import httpx

from core.config import log_yaz

# ── Bulkhead Konfigurasyonu ───────────────────────────────────
MAX_ESZAMANLI = 3  # Maksimum eş zamanlı API isteği
HTTP_TIMEOUT = 30.0  # Saniye — genel HTTP timeout
CONNECT_TIMEOUT = 10.0  # Saniye — bağlantı timeout
READ_TIMEOUT = 25.0  # Saniye — okuma timeout

# Global semaphore — tüm API çağrıları bu havuzu paylaşır
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Event loop başladıktan sonra semaphore'u lazy-init et."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_ESZAMANLI)
    return _semaphore


def httpx_client() -> httpx.AsyncClient:
    """Standart timeout ayarlı httpx AsyncClient döner."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=CONNECT_TIMEOUT,
            read=READ_TIMEOUT,
            write=10.0,
            pool=5.0,
        ),
        follow_redirects=True,
    )


class BulkheadDolu(Exception):
    """Semaphore doluyken timeout olursa fırlatılır."""

    pass


def _gerekirse_coro_kapat(coro) -> None:
    """Henüz await edilmemiş coroutine objesini sessizce kapat."""
    try:
        if asyncio.iscoroutine(coro):
            coro.close()
    except Exception:
        pass


async def bulkhead_cagri(coro, bekleme_suresi: float = 5.0):
    """
    Coroutine'i bulkhead koruması altında çalıştır.

    - MAX_ESZAMANLI slot doluysa bekleme_suresi kadar bekler
    - Slot boşalmazsa BulkheadDolu fırlatır
    - Slot alınınca coroutine'i HTTP_TIMEOUT ile çalıştırır

    Kullanım:
        sonuc = await bulkhead_cagri(groq_api_cagri(...))
    """
    sem = _get_semaphore()

    try:
        await asyncio.wait_for(sem.acquire(), timeout=bekleme_suresi)
    except TimeoutError:
        _gerekirse_coro_kapat(coro)
        log_yaz(f"[Bulkhead] {MAX_ESZAMANLI} slot doldu, istek reddedildi", "WARNING")
        raise BulkheadDolu(f"Bulkhead dolu: {MAX_ESZAMANLI} eş zamanlı istek limiti aşıldı")

    try:
        log_yaz("[Bulkhead] Slot alındı", "DEBUG")
        return await asyncio.wait_for(coro, timeout=HTTP_TIMEOUT)
    except TimeoutError:
        log_yaz(f"[Bulkhead] İstek {HTTP_TIMEOUT}s timeout'a uğradı", "WARNING")
        raise
    finally:
        sem.release()
        log_yaz("[Bulkhead] Slot serbest bırakıldı", "DEBUG")


def bulkhead(bekleme_suresi: float = 5.0):
    """
    Async fonksiyonlar için bulkhead decorator.

    Kullanım:
        @bulkhead(bekleme_suresi=3.0)
        async def groq_api_cagri(...):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await bulkhead_cagri(
                func(*args, **kwargs),
                bekleme_suresi=bekleme_suresi,
            )

        return wrapper

    return decorator


async def guvenli_http_get(url: str, **kwargs) -> httpx.Response:
    """
    Timeout + bulkhead korumalı HTTP GET isteği.

    Kullanım:
        response = await guvenli_http_get("https://api.example.com/data")
    """

    async def _get():
        async with httpx_client() as client:
            return await client.get(url, **kwargs)

    return await bulkhead_cagri(_get())


async def guvenli_http_post(url: str, **kwargs) -> httpx.Response:
    """
    Timeout + bulkhead korumalı HTTP POST isteği.

    Kullanım:
        response = await guvenli_http_post(url, json={"key": "value"})
    """

    async def _post():
        async with httpx_client() as client:
            return await client.post(url, **kwargs)

    return await bulkhead_cagri(_post())


def bulkhead_durumu() -> dict:
    """
    Mevcut bulkhead durumunu döner — /metrics veya /status için.
    """
    sem = _get_semaphore()
    kullanilan = MAX_ESZAMANLI - sem._value  # type: ignore
    return {
        "max_eszamanli": MAX_ESZAMANLI,
        "kullanilan_slot": kullanilan,
        "bos_slot": sem._value,  # type: ignore
        "http_timeout": HTTP_TIMEOUT,
        "connect_timeout": CONNECT_TIMEOUT,
    }
