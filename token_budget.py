# token_budget.py — Günlük token & maliyet takibi
# Master Plan S2-4: Claude-8 (budget) + Grok (günlük limit) + Mistral (TokenBudget sınıfı)
# ============================================================
# Kullanim:
#   from token_budget import budget
#
#   # Limit asıldı mı?
#   if budget.limit_asildimi(): ...
#
#   # Kullanım kaydet:
#   budget.kullanim_ekle("llama-3.3-70b", prompt_tokens=120, completion_tokens=80)
#
#   # Rapor:
#   print(budget.rapor())
# ============================================================

import json
import os
import time
from datetime import date, datetime
from pathlib import Path

# ── Ayarlar ───────────────────────────────────────────────────

try:
    from bot_config import CFG

    _cfg = CFG.get("token_budget", {})
except Exception:
    _cfg = {}

DAILY_LIMIT = int(os.getenv("DAILY_TOKEN_LIMIT", _cfg.get("daily_limit", 500_000)))
WARN_THRESHOLD = float(_cfg.get("warn_threshold", 0.80))  # %80'de uyarı
LOG_DOSYASI = _cfg.get("log_dosyasi", "token_budget_log.jsonl")


# ── Model maliyet tablosu ($/1M token) ───────────────────────

MODEL_MALIYETLERI = {
    # Groq
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    # Gemini
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    # DeepSeek
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    # Varsayılan (bilinmeyen modeller)
    "default": {"input": 0.50, "output": 0.50},
}


def _maliyet_hesapla(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """USD cinsinden tahmini maliyet hesapla."""
    fiyat = MODEL_MALIYETLERI.get(model, MODEL_MALIYETLERI["default"])
    return (
        prompt_tokens / 1_000_000 * fiyat["input"] + completion_tokens / 1_000_000 * fiyat["output"]
    )


# ── TokenBudget ──────────────────────────────────────────────


class TokenBudget:
    """
    Günlük token kullanımını takip eder.
    - Günlük limit aşılınca Ollama'ya yönlendirir
    - Maliyet hesabı USD cinsinden tutulur
    - Her kullanım JSONL log dosyasına yazılır
    """

    def __init__(self):
        self._gun = str(date.today())
        self._kullanim = 0  # Bugünkü toplam token
        self._maliyet = 0.0  # Bugünkü toplam USD
        self._gecmis = []  # Son 100 kayıt (in-memory)
        self._log_path = Path(LOG_DOSYASI)
        self._yukle()

    # ── Iç yardımcılar ──────────────────────────────────────

    def _gun_kontrol(self):
        """Gün değiştiyse sayaçları sıfırla."""
        bugun = str(date.today())
        if bugun != self._gun:
            print(f"[TokenBudget] Yeni gün: {bugun} — sayaçlar sıfırlandı")
            self._gun = bugun
            self._kullanim = 0
            self._maliyet = 0.0
            self._gecmis = []

    def _yukle(self):
        """Bugüne ait log kayıtlarını yükle (bot yeniden başlatılınca süreklilik)."""
        if not self._log_path.exists():
            return
        try:
            bugun = str(date.today())
            with open(self._log_path, encoding="utf-8") as f:
                for satir in f:
                    try:
                        kayit = json.loads(satir)
                        if kayit.get("gun") == bugun:
                            self._kullanim += kayit.get("toplam_token", 0)
                            self._maliyet += kayit.get("maliyet_usd", 0.0)
                            self._gecmis.append(kayit)
                    except Exception:
                        pass
            if self._kullanim > 0:
                print(
                    f"[TokenBudget] Bugün yüklendi: "
                    f"{self._kullanim:,} token / ${self._maliyet:.4f}"
                )
        except Exception as e:
            print(f"[TokenBudget] Yükleme hatası: {e}")

    def _log_yaz(self, kayit: dict):
        """JSONL dosyasına kayıt ekle."""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[TokenBudget] Log yazma hatası: {e}")

    # ── Public API ──────────────────────────────────────────

    def kullanim_ekle(self, model: str, prompt_tokens: int = 0, completion_tokens: int = 0) -> dict:
        """
        Token kullanımını kaydet.
        Döner: {"toplam_token": int, "maliyet_usd": float, "limit_pct": float}
        """
        self._gun_kontrol()

        toplam = prompt_tokens + completion_tokens
        maliyet = _maliyet_hesapla(model, prompt_tokens, completion_tokens)

        self._kullanim += toplam
        self._maliyet += maliyet

        kayit = {
            "zaman": datetime.now().isoformat(timespec="seconds"),
            "gun": self._gun,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "toplam_token": toplam,
            "maliyet_usd": round(maliyet, 6),
            "gunluk_toplam": self._kullanim,
            "gunluk_maliyet": round(self._maliyet, 6),
        }
        self._gecmis.append(kayit)
        if len(self._gecmis) > 100:
            self._gecmis = self._gecmis[-100:]
        self._log_yaz(kayit)

        pct = self._kullanim / DAILY_LIMIT * 100
        if pct >= WARN_THRESHOLD * 100 and pct < 100:
            print(f"[TokenBudget] ⚠️ Uyarı: Günlük limitin %{pct:.0f}'i kullanıldı!")

        return {
            "toplam_token": toplam,
            "maliyet_usd": round(maliyet, 6),
            "limit_pct": round(pct, 1),
        }

    def limit_asildimi(self) -> bool:
        """Günlük limit aşıldıysa True döner → Ollama'ya yönlendir."""
        self._gun_kontrol()
        return self._kullanim >= DAILY_LIMIT

    def consume(self, tokens: int, model: str = "default") -> bool:
        """
        Alternatif arayüz: tokens miktarı tüketilebilir mi?
        True → tüket ve kaydet | False → limit aşıldı
        """
        self._gun_kontrol()
        if self._kullanim + tokens > DAILY_LIMIT:
            return False
        self.kullanim_ekle(model, prompt_tokens=tokens)
        return True

    def reset(self):
        """Manuel sıfırlama (test veya yönetici komutu için)."""
        self._gun = str(date.today())
        self._kullanim = 0
        self._maliyet = 0.0
        self._gecmis = []
        print("[TokenBudget] Manuel sıfırlandı")

    def rapor(self) -> dict:
        """Güncel kullanım özeti."""
        self._gun_kontrol()
        pct = round(self._kullanim / DAILY_LIMIT * 100, 1)
        return {
            "gun": self._gun,
            "kullanim": self._kullanim,
            "limit": DAILY_LIMIT,
            "kalan": max(0, DAILY_LIMIT - self._kullanim),
            "yuzde": pct,
            "maliyet_usd": round(self._maliyet, 4),
            "durum": "⛔ LIMIT AŞILDI"
            if pct >= 100
            else f"⚠️ UYARI %{pct}"
            if pct >= WARN_THRESHOLD * 100
            else f"✅ Normal %{pct}",
        }

    def rapor_metni(self) -> str:
        """Telegram mesajı için okunabilir rapor."""
        r = self.rapor()
        return (
            f"📊 *Token Bütçesi — {r['gun']}*\n"
            f"Kullanılan: `{r['kullanim']:,}` / `{r['limit']:,}` token\n"
            f"Kalan: `{r['kalan']:,}` token ({r['yuzde']}%)\n"
            f"Tahmini maliyet: `${r['maliyet_usd']:.4f}` USD\n"
            f"Durum: {r['durum']}"
        )

    def son_kayitlar(self, n: int = 10) -> list:
        """Son n kullanım kaydını döner."""
        return self._gecmis[-n:]

    def durum_ozeti(self) -> str:
        """admin.py uyumu için alias — rapor_metni() ile aynı."""
        return self.rapor_metni()


# ── Global singleton ─────────────────────────────────────────
budget = TokenBudget()
