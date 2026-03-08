# services/model_service.py — Model seçimi ve LLM çağrı servisi
# Sprint 1: model_manager + api_rotator üzerine temiz servis katmanı
# ============================================================
# Kullanim:
#   from services.model_service import model_service
#
#   secim = model_service.model_sec(prompt, gorev_turu)
#   durum = model_service.durum()
# ============================================================

from core.globals import CFG, model_mgr, rotator
from core.resilience import cb_durum_raporu
from core.schemas import ToolResult


class ModelService:
    """
    model_manager.py + api_rotator.py + CircuitBreaker
    üzerine temiz servis katmanı.
    """

    # ── Model Seçimi ────────────────────────────────────────

    def model_sec(self, prompt: str, gorev_turu: str = "genel") -> str:
        """
        Prompt'a göre 'lokal' veya 'cloud' döner.
        CircuitBreaker durumu da dikkate alınır.
        """
        try:
            from core.resilience import cb_gemini, cb_groq

            # Tüm cloud CB'ler OPEN ise lokale zorla
            if cb_groq.state == cb_groq.OPEN and cb_gemini.state == cb_gemini.OPEN:
                print("[ModelService] Tüm cloud CB OPEN → lokal zorlandı")
                return "lokal"

            return model_mgr.model_sec(prompt, gorev_turu)
        except Exception:
            return "cloud"

    def aktif_provider(self) -> dict:
        """Aktif provider bilgisini döner."""
        try:
            from core.utils import _safe_active_provider

            p = _safe_active_provider(rotator)
            if p:
                return {
                    "name": p.get("name") or p.get("isim", "?"),
                    "model": p.get("model", "?"),
                }
            return {"name": "yok", "model": "yok"}
        except Exception:
            return {"name": "hata", "model": "hata"}

    # ── Durum Raporu ────────────────────────────────────────

    def durum(self) -> dict:
        """
        Model sistemi tam durum raporu.
        /status ve dashboard için kullanılır.
        """
        cb = cb_durum_raporu()

        provider_listesi = []
        try:
            for p in rotator.providers:
                pname = p.get("name") or p.get("isim", "?")
                provider_listesi.append(
                    {
                        "name": pname,
                        "model": p.get("model", "?"),
                        "aktif": not rotator.cooldown_var_mi(pname)
                        if hasattr(rotator, "cooldown_var_mi")
                        else "?",
                    }
                )
        except Exception:
            pass

        return {
            "circuit_breakers": cb,
            "providers": provider_listesi,
            "aktif_provider": self.aktif_provider(),
            "lokal_model": CFG.get("ollama", {}).get("default_model", "?"),
        }

    def durum_metni(self) -> str:
        """Telegram /status için okunabilir model durum metni."""
        d = self.durum()
        ap = d["aktif_provider"]
        satirlar = [
            "🤖 *Model Sistemi*",
            f"Aktif: `{ap['name']}` — `{ap['model']}`",
            f"Lokal: `{d['lokal_model']}`",
            "",
        ]

        satirlar.append("*CircuitBreaker Durumu:*")
        for name, cb in d["circuit_breakers"].items():
            ikon = (
                "✅" if cb["state"] == "CLOSED" else ("⚠️" if cb["state"] == "HALF_OPEN" else "❌")
            )
            satirlar.append(f"  {ikon} {name}: `{cb['state']}` ({cb['failures']} hata)")

        return "\n".join(satirlar)

    # ── Başarı / Hata Kaydı ─────────────────────────────────

    def basari_kaydet(self, provider_adi: str, latency_ms: float = 0) -> None:
        try:
            rotator.basari_kaydet(provider_adi, latency_ms=latency_ms)
        except Exception:
            try:
                rotator.basari_kaydet(provider_adi)
            except Exception:
                pass

    def hata_kaydet(self, provider_adi: str, hata: str, cooldown_s: int = 60) -> None:
        try:
            rotator.hata_kaydet(provider_adi, hata, cooldown_s=cooldown_s)
        except Exception:
            pass


# ── Global singleton ─────────────────────────────────────────
model_service = ModelService()
