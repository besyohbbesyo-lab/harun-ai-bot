# core/backoff.py — S5-5: Exponential Backoff
# alpha=2, max=300s, jitter destekli
# ============================================================

from __future__ import annotations

import asyncio
import random
import time
from functools import wraps

from core.config import log_yaz


class BackoffError(Exception):
    """Tum denemeler bittikten sonra firlatilir."""

    pass


def _hesapla(
    deneme: int,
    taban: float = 1.0,
    alpha: float = 2.0,
    maksimum: float = 300.0,
    jitter: bool = True,
) -> float:
    """
    Bekleme suresi = min(taban * alpha^deneme, maksimum)
    jitter=True ise %±20 rastgelelik eklenir.
    """
    sure = min(taban * (alpha**deneme), maksimum)
    if jitter:
        sure *= random.uniform(0.8, 1.2)
    return sure


def retry_sync(
    maks_deneme: int = 5,
    taban: float = 1.0,
    alpha: float = 2.0,
    maksimum: float = 300.0,
    istisnalar: tuple = (Exception,),
):
    """Senkron fonksiyonlar icin retry decorator."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            son_hata = None
            for deneme in range(maks_deneme):
                try:
                    return func(*args, **kwargs)
                except istisnalar as e:
                    son_hata = e
                    if deneme == maks_deneme - 1:
                        break
                    sure = _hesapla(deneme, taban, alpha, maksimum)
                    log_yaz(
                        f"[Backoff] {func.__name__} hata: {e} | "
                        f"deneme {deneme+1}/{maks_deneme} | "
                        f"{sure:.1f}s bekle",
                        "WARNING",
                    )
                    time.sleep(sure)
            log_yaz(f"[Backoff] {func.__name__} {maks_deneme} denemede basarisiz", "ERROR")
            raise BackoffError(f"{func.__name__} basarisiz: {son_hata}") from son_hata

        return wrapper

    return decorator


def retry_async(
    maks_deneme: int = 5,
    taban: float = 1.0,
    alpha: float = 2.0,
    maksimum: float = 300.0,
    istisnalar: tuple = (Exception,),
):
    """Async fonksiyonlar icin retry decorator."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            son_hata = None
            for deneme in range(maks_deneme):
                try:
                    return await func(*args, **kwargs)
                except istisnalar as e:
                    son_hata = e
                    if deneme == maks_deneme - 1:
                        break
                    sure = _hesapla(deneme, taban, alpha, maksimum)
                    log_yaz(
                        f"[Backoff] {func.__name__} hata: {e} | "
                        f"deneme {deneme+1}/{maks_deneme} | "
                        f"{sure:.1f}s bekle",
                        "WARNING",
                    )
                    await asyncio.sleep(sure)
            log_yaz(f"[Backoff] {func.__name__} {maks_deneme} denemede basarisiz", "ERROR")
            raise BackoffError(f"{func.__name__} basarisiz: {son_hata}") from son_hata

        return wrapper

    return decorator


async def guvenli_api_cagri(
    cagri,
    *args,
    maks_deneme: int = 5,
    taban: float = 1.0,
    alpha: float = 2.0,
    maksimum: float = 300.0,
    **kwargs,
):
    """
    Herhangi bir coroutine'i backoff ile calistir.
    Kullanim:
        sonuc = await guvenli_api_cagri(groq_client.chat.completions.create,
                                         model=..., messages=...)
    """
    son_hata = None
    for deneme in range(maks_deneme):
        try:
            return await cagri(*args, **kwargs)
        except Exception as e:
            son_hata = e
            if deneme == maks_deneme - 1:
                break
            sure = _hesapla(deneme, taban, alpha, maksimum)
            log_yaz(
                f"[Backoff] API cagrisi hata: {e} | "
                f"deneme {deneme+1}/{maks_deneme} | "
                f"{sure:.1f}s bekle",
                "WARNING",
            )
            await asyncio.sleep(sure)
    raise BackoffError(f"API cagrisi basarisiz: {son_hata}") from son_hata
