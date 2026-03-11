# core/schemas.py — Standart veri şemaları
# Master Plan S1-5: Claude-8 (ToolResult + trace_id) + AI-4 (ProviderConfig)
# ============================================================
# Kullanim:
#   from core.schemas import ToolResult, ProviderConfig, yeni_trace_id
#
#   # Basarili sonuc:
#   return ToolResult(ok=True, data={"yanit": text}).dict()
#
#   # Hatali sonuc:
#   return ToolResult(ok=False, error="API timeout").dict()
# ============================================================

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, List, Optional

# ── Trace ID yardımcısı ───────────────────────────────────────


def yeni_trace_id() -> str:
    """8 karakterlik benzersiz trace ID uret."""
    return str(uuid.uuid4())[:8]


# ── ToolResult ────────────────────────────────────────────────


@dataclass
class ToolResult:
    """
    Tum plugin ve servis cagrilarinin standart donus formati.

    ok       : Islem basarili mi?
    data     : Basarili sonuc (herhangi bir tip)
    error    : Hata mesaji (ok=False ise dolu olur)
    trace_id : Islem takip ID'si (loglarda eslesme icin)

    Kullanim ornekleri:
        ToolResult(ok=True, data="Merhaba!")
        ToolResult(ok=False, error="Groq timeout")
        ToolResult(ok=True, data={"dosya": "rapor.pdf"}, trace_id="a1b2c3d4")
    """

    ok: bool
    data: Any = None
    error: str | None = None
    trace_id: str = field(default_factory=yeni_trace_id)

    def dict(self) -> dict:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "trace_id": self.trace_id,
        }

    def __repr__(self):
        if self.ok:
            return f"<ToolResult OK trace={self.trace_id}>"
        return f"<ToolResult ERR={self.error!r} trace={self.trace_id}>"

    @classmethod
    def basari(cls, data: Any = None) -> ToolResult:
        """Kisa yol: basarili sonuc olustur."""
        return cls(ok=True, data=data)

    @classmethod
    def hata(cls, mesaj: str) -> ToolResult:
        """Kisa yol: hatali sonuc olustur."""
        return cls(ok=False, error=mesaj)


# ── ProviderConfig ────────────────────────────────────────────


@dataclass
class ProviderConfig:
    """
    LLM provider yapılandırması.
    api_rotator.py ile uyumlu standart format.

    name/isim KeyError sorununu cözer — ikisi de kabul edilir.
    """

    name: str
    model: str
    api_key: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 30.0

    def dict(self) -> dict:
        return {
            "name": self.name,
            "isim": self.name,  # Eski kod uyumu
            "model": self.model,
            "api_key": self.api_key,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProviderConfig:  # type: ignore[valid-type]
        """
        api_rotator'dan gelen sozlugu ProviderConfig'e donustur.
        'name' veya 'isim' anahtarini otomatik alir.
        """
        name = d.get("name") or d.get("isim") or "bilinmiyor"  # type: ignore[attr-defined]
        return cls(
            name=name,
            model=d.get("model", ""),  # type: ignore[attr-defined]
            api_key=d.get("api_key", ""),  # type: ignore[attr-defined]
            max_tokens=int(d.get("max_tokens", 4096)),  # type: ignore[attr-defined]
            temperature=float(d.get("temperature", 0.7)),  # type: ignore[attr-defined]
            timeout=float(d.get("timeout", 30.0)),  # type: ignore[attr-defined]
        )


# ── OperationLog (idempotent komutlar) ───────────────────────

import json
import time
from pathlib import Path


class OperationLog:
    """
    Master Plan S1-6: Idempotent komutlar.
    Ayni islemi iki kez calistirmayi onler (cift mesaj, cift dosya olusturma).

    Kullanim:
        op_log = OperationLog()
        op_id  = f"mkdir_{user_id}_{klasor_adi}"
        sonuc  = op_log.execute_once(op_id, klasor_olustur, klasor_adi)
    """

    def __init__(self, db_path: str = "operations.json"):
        self.db_path = Path(db_path)
        self._yukle()

    def _yukle(self):
        if self.db_path.exists():
            try:
                self._db = json.loads(self.db_path.read_text(encoding="utf-8"))
            except Exception:
                self._db = {}
        else:
            self._db = {}

    def _kaydet(self):
        self.db_path.write_text(
            json.dumps(self._db, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def is_done(self, operation_id: str) -> bool:
        return operation_id in self._db

    def execute_once(self, op_id: str, fn: Any, *args, **kwargs) -> Any:
        """
        op_id ile isaretlenmis islemi yalnizca bir kez calistir.
        Daha once yapilmissa onceki sonucu dondur.
        """
        if self.is_done(op_id):
            print(f"[OpLog] Zaten yapildi: {op_id}")
            return {
                "status": "already_done",
                "op_id": op_id,
                "result": self._db[op_id].get("result"),
            }

        result = fn(*args, **kwargs)
        self._db[op_id] = {
            "timestamp": time.time(),
            "result": str(result)[:500],
        }
        self._kaydet()
        return result

    def temizle(self, max_yas_gun: int = 7):
        """max_yas_gun'dan eski kayitlari sil."""
        simdi = time.time()
        esik = simdi - (max_yas_gun * 86400)
        eskiler = [k for k, v in self._db.items() if v.get("timestamp", 0) < esik]
        for k in eskiler:
            del self._db[k]
        if eskiler:
            self._kaydet()
            print(f"[OpLog] {len(eskiler)} eski kayit silindi")


# ── Global instance'lar ──────────────────────────────────────
op_log = OperationLog()
