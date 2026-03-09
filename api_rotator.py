# api_rotator.py - Groq multi-model rotator (rate-limit + model fallback)
# -----------------------------------------------------------------------
# Groq'ta birden fazla model destekler. Rate limit yerse:
#   llama-3.3-70b-versatile → llama-3.1-8b-instant → gemma2-9b-it
#
# Key verme sırası:
#   1) Ortam değişkenleri: GROQ_API_KEY veya GROQ_API_KEYS (.env dosyasindan)
#   2) NOT: Hard-coded key kullanimi kaldirilmistir. Tum key'ler .env'de olmalidir.

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# KALDIRILDI: Hard-coded key'ler guvenlik riski olusturuyordu.
# Tum API key'leri .env dosyasina yazin (bkz: .env.example)
# Eski degiskenler geriye uyumluluk icin bos birakildi:
HARD_CODED_GROQ_API_KEY: str = ""
HARD_CODED_GROQ_API_KEYS: str = ""

# Config'den model listesi ve gorev tercihleri yukle
try:
    from bot_config import CFG

    _cfg_models = CFG.get("groq", {}).get("models", [])
    GROQ_MODELS = [(m["id"], m["max_tokens"], m["maliyet"]) for m in _cfg_models]
    TASK_MODEL_PREF: dict[str, int] = CFG.get("groq", {}).get("task_model_pref", {})
except Exception:
    # Config okunamazsa hardcoded varsayilan
    GROQ_MODELS = [
        ("llama-3.3-70b-versatile", 2000, 3),
        ("llama-3.1-8b-instant", 2000, 1),
        ("meta-llama/llama-4-scout-17b-16e-instruct", 2000, 2),
    ]
    TASK_MODEL_PREF: dict[str, int] = {
        "kod": 0,
        "sunum": 0,
        "word": 0,
        "arastirma": 0,
        "planner": 0,
        "pdf": 0,
        "sohbet": 1,
        "genel": 1,
        "basit": 1,
    }


def _split_keys(keys_csv: str) -> list[str]:
    return [k.strip() for k in (keys_csv or "").split(",") if k.strip()]


@dataclass
class _KeyState:
    key: str
    cooldown_until: float = 0.0
    ok_count: int = 0
    err_count: int = 0
    last_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    latency_samples: int = 0
    last_ok_ts: float = 0.0
    last_err_ts: float = 0.0
    last_err_msg: str = ""
    last_used_ts: float = 0.0
    # Hangi modeller bu key'de cooldown'da
    model_cooldown: dict[str, float] = field(default_factory=dict)


class APIRotator:
    """Groq anahtar + model rotasyonu."""

    def __init__(self) -> None:
        env_key = (os.getenv("GROQ_API_KEY") or "").strip()
        env_keys = (os.getenv("GROQ_API_KEYS") or "").strip()

        keys: list[str] = []
        if env_keys:
            keys = _split_keys(env_keys)
        elif env_key:
            keys = [env_key]
        elif HARD_CODED_GROQ_API_KEYS.strip():
            keys = _split_keys(HARD_CODED_GROQ_API_KEYS)
        elif HARD_CODED_GROQ_API_KEY.strip():
            keys = [HARD_CODED_GROQ_API_KEY.strip()]

        if not keys:
            raise RuntimeError(
                "GROQ anahtari bulunamadi.\n"
                ".env dosyasina GROQ_API_KEY=gsk_... satirini ekleyin.\n"
                "Ornek icin .env.example dosyasina bakin."
            )

        self._keys: list[_KeyState] = [_KeyState(key=k) for k in keys]
        self._active_idx: int = 0
        self._last_provider: str = "Groq"
        self._last_model: str = GROQ_MODELS[0][0]

    def aktif_provider_al(
        self, gorev_turu: str = "genel", tercih_model_idx: int | None = None
    ) -> dict | None:
        """
        Uygun key + model döndür.
        - gorev_turu'na göre başlangıç modeli seç
        - Rate limit varsa daha ucuz modele düş
        - Tüm modeller cooldown'daysa None döner
        """
        now = time.time()

        # Başlangıç model indexi
        if tercih_model_idx is not None:
            start_idx = tercih_model_idx
        else:
            start_idx = TASK_MODEL_PREF.get(gorev_turu, 1)

        # Uygun key bul
        adaylar = [st for st in self._keys if st.cooldown_until <= now]
        if not adaylar:
            return None

        def _skor(st: _KeyState):
            avg = st.avg_latency_ms if st.avg_latency_ms > 0 else 10_000.0
            return (st.last_used_ts, avg)

        secilen = min(adaylar, key=_skor)
        self._active_idx = self._keys.index(secilen)
        secilen.last_used_ts = now

        # Model seç: tercihten başla, cooldown'da olanları atla
        for offset in range(len(GROQ_MODELS)):
            model_idx = (start_idx + offset) % len(GROQ_MODELS)
            model_id, max_tokens, maliyet = GROQ_MODELS[model_idx]
            model_cd = secilen.model_cooldown.get(model_id, 0)
            if model_cd <= now:
                self._last_model = model_id
                return {
                    "name": "Groq",
                    "api_key": secilen.key,
                    "model": model_id,
                    "max_tokens": max_tokens,
                    "maliyet": maliyet,
                }

        return None  # Tüm modeller cooldown'da

    def basari_kaydet(self, isim: str = "Groq", latency_ms: float = 0.0) -> None:
        self._last_provider = isim
        try:
            st = self._keys[self._active_idx]
            st.ok_count += 1
            st.last_ok_ts = time.time()
            if latency_ms > 0:
                st.last_latency_ms = float(latency_ms)
                st.latency_samples += 1
                alpha = 0.2
                if st.avg_latency_ms <= 0:
                    st.avg_latency_ms = float(latency_ms)
                else:
                    st.avg_latency_ms = (1 - alpha) * st.avg_latency_ms + alpha * float(latency_ms)
        except Exception:
            pass

    def hata_kaydet(
        self, isim: str, hata: str, cooldown_s: int = 60, model_id: str | None = None
    ) -> None:
        """
        Rate limit hatası:
        - Belirli model_id varsa sadece o modeli cooldown'a al
        - Yoksa key'i tamamen cooldown'a al
        """
        self._last_provider = isim
        try:
            st = self._keys[self._active_idx]
            st.err_count += 1
            st.last_err_ts = time.time()
            st.last_err_msg = (hata or "")[:200]

            is_rate_limit = (
                "429" in (hata or "")
                or "rate" in (hata or "").lower()
                or "limit" in (hata or "").lower()
            )

            if is_rate_limit:
                if model_id:
                    # Sadece bu modeli cooldown'a al, key açık kalsın
                    st.model_cooldown[model_id] = time.time() + max(5, int(cooldown_s))
                    print(f"[APIRotator] {model_id} cooldown {cooldown_s}s")
                else:
                    st.cooldown_until = time.time() + max(5, int(cooldown_s))
        except Exception:
            pass

    def durum_ozeti(self) -> str:
        now = time.time()
        lines = ["[API] Groq multi-model rotator"]
        for i, st in enumerate(self._keys, 1):
            cd = max(0, int(st.cooldown_until - now))
            avg = f"{st.avg_latency_ms:.0f}ms" if st.avg_latency_ms > 0 else "n/a"
            model_cds = []
            for mid, until in st.model_cooldown.items():
                remaining = int(until - now)
                if remaining > 0:
                    model_cds.append(f"{mid}:{remaining}s")
            mcd_str = " | ".join(model_cds) if model_cds else "-"
            lines.append(
                f"- key#{i}: ok={st.ok_count} err={st.err_count} "
                f"key_cd={cd}s avg={avg} model_cd=[{mcd_str}]"
            )
        lines.append(f"Son model: {self._last_model}")
        return "\n".join(lines)

    def api_test_sonuclari(self) -> list:
        now = time.time()
        out = []
        for i, st in enumerate(self._keys, 1):
            out.append(
                {
                    "index": i,
                    "cooldown_s": max(0, int(st.cooldown_until - now)),
                    "ok": st.ok_count,
                    "err": st.err_count,
                    "avg_latency_ms": st.avg_latency_ms,
                    "last_latency_ms": st.last_latency_ms,
                    "last_err_ts": st.last_err_ts,
                    "last_err_msg": st.last_err_msg,
                    "model_cooldowns": {
                        m: max(0, int(u - now)) for m, u in st.model_cooldown.items() if u > now
                    },
                }
            )
        return out


# telegram_bot.py için global instance
rotator = APIRotator()
