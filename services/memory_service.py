# services/memory_service.py — Hafıza operasyonları servisi
# Sprint 1: memory_plugin.py üzerine temiz bir servis katmanı
# ============================================================
# Kullanim:
#   from services.memory_service import memory_service
#
#   memory_service.kaydet(user_id, prompt, response, reward)
#   memory_service.bul(sorgu, n=3)
#   memory_service.ozet()
# ============================================================

from core.globals import memory
from core.schemas import ToolResult


class MemoryService:
    """
    memory_plugin.py üzerine temiz servis katmanı.
    Handler'lar doğrudan memory_plugin'e erişmek yerine
    bu servisi kullanır.
    """

    # ── Kaydetme ────────────────────────────────────────────

    def kaydet(
        self, prompt: str, response: str, reward: float = 0.5, gorev_turu: str = "genel"
    ) -> ToolResult:
        """Konuşmayı hafızaya kaydet."""
        try:
            memory.gorev_kaydet(
                gorev=prompt[:200], sonuc=response[:500], basari=reward > 0.5, sure=0, reward=reward  # type: ignore[call-arg]
            )
            return ToolResult.basari({"kayit": "ok"})
        except Exception as e:
            return ToolResult.hata(f"Hafıza kayıt hatası: {e}")

    def bilgi_kaydet(self, baslik: str, icerik: str, kategori: str = "genel") -> ToolResult:
        """Kalıcı bilgi olarak kaydet (LTM)."""
        try:
            memory.bilgi_ekle(baslik=baslik, icerik=icerik, kategori=kategori)  # type: ignore[attr-defined]
            return ToolResult.basari({"baslik": baslik})
        except Exception as e:
            return ToolResult.hata(f"Bilgi kayıt hatası: {e}")

    # ── Arama ───────────────────────────────────────────────

    def bul(self, sorgu: str, n: int = 3) -> ToolResult:
        """Hafızadan benzer görevleri bul."""
        try:
            sonuclar = memory.benzer_gorev_bul(sorgu[:100], n=n)
            return ToolResult.basari(sonuclar)
        except Exception as e:
            return ToolResult.hata(f"Hafıza arama hatası: {e}")

    def bilgi_ara(self, sorgu: str, n: int = 3) -> ToolResult:
        """Bilgi tabanında ara."""
        try:
            sonuclar = memory.bilgi_ara(sorgu[:100], n=n)
            return ToolResult.basari(sonuclar)
        except Exception as e:
            return ToolResult.hata(f"Bilgi arama hatası: {e}")

    # ── Bakım ───────────────────────────────────────────────

    def decay_uygula(self) -> ToolResult:
        """Eski hafıza kayıtlarını zayıflat."""
        try:
            memory.decay_uygula()
            return ToolResult.basari({"decay": "ok"})
        except Exception as e:
            return ToolResult.hata(f"Decay hatası: {e}")

    def guclendir(self, sorgu: str, reward: float) -> ToolResult:
        """Başarılı işlem sonrası hafızayı güçlendir."""
        try:
            memory.hafizayi_guclendir(sorgu[:100], reward)
            return ToolResult.basari()
        except Exception as e:
            return ToolResult.hata(f"Güçlendirme hatası: {e}")

    # ── Özet ────────────────────────────────────────────────

    def ozet(self) -> dict:
        """Hafıza durumu özeti — /status komutunda kullanılır."""
        try:
            return {
                "gorevler": memory.gorev_sayisi() if hasattr(memory, "gorev_sayisi") else "?",
                "bilgiler": memory.bilgi_sayisi() if hasattr(memory, "bilgi_sayisi") else "?",
                "episodik": memory.episodik.ani_sayisi() if hasattr(memory, "episodik") else "?",
                "prosedur": memory.prosedur.prosedur_sayisi()
                if hasattr(memory, "prosedur")
                else "?",
            }
        except Exception:
            return {"durum": "bilgi alinamadi"}


# ── Global singleton ─────────────────────────────────────────
memory_service = MemoryService()
