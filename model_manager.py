# model_manager.py - Akıllı Model Seçimi (Performans & Maliyet)
# -------------------------------------------------------------
# Basit → Lokal GLM  (bedava, hızlı)
# Orta  → Groq 8b    (ucuz, hızlı)
# Zor   → Groq 70b   (güçlü, pahalı)
#
# Karar faktörleri:
#   1) Görev türü
#   2) Prompt uzunluğu (token tahmini)
#   3) Karmaşıklık kelimeleri
#   4) Öğrenilmiş tercih (strategy_manager)

import re

# Config'den esik degerlerini oku
try:
    from bot_config import CFG

    _ms_cfg = CFG.get("model_secim", {})
    _LOKAL_MAX = _ms_cfg.get("lokal_max_tokens", 50)
    _CLOUD_MIN = _ms_cfg.get("cloud_min_tokens", 200)
except Exception:
    _LOKAL_MAX = 50
    _CLOUD_MIN = 200


def _token_tahmini(text: str) -> int:
    """Kaba token tahmini: 4 karakter ≈ 1 token."""
    return max(1, len(text) // 4)


class ModelManager:
    # --- Kelime listeleri ---
    BASIT_KELIMELER = [
        "merhaba",
        "nasılsın",
        "iyi",
        "tamam",
        "teşekkür",
        "selam",
        "naber",
        "ne haber",
        "evet",
        "hayır",
        "olur",
        "peki",
        "tarih",
        "saat",
        "bugün",
        "günlerden",
        "kaç",
        "kimsin",
        "ne zaman",
        "kısaca",
    ]

    ORTA_KELIMELER = [
        "anlat",
        "açıkla",
        "ne demek",
        "nedir",
        "özet",
        "liste",
        "fark",
        "karşılaştır",
        "avantaj",
        "dezavantaj",
        "neden",
    ]

    KARMASIK_KELIMELER = [
        "kod",
        "yaz",
        "analiz",
        "rapor",
        "araştır",
        "plan",
        "sunum",
        "word",
        "pdf",
        "hesapla",
        "optimize",
        "mimari",
        "geliştir",
        "nasıl çalışır",
        "detaylı",
        "algoritma",
        "refactor",
        "debug",
        "test",
        "deploy",
        "docker",
        "api",
        "veritabanı",
        "sql",
    ]

    # Görev türü → doğrudan model ataması
    # "lokal" | "cloud_fast" | "cloud_strong"
    TASK_MAP = {
        "kod": "cloud_strong",
        "sunum": "cloud_strong",
        "word": "cloud_strong",
        "arastirma": "cloud_strong",
        "planner": "cloud_strong",
        "pdf": "cloud_fast",
        "sohbet": "lokal",
        "genel": None,  # kural tabanlı karar ver
        "basit": "lokal",
    }

    # Groq model index eşlemesi (api_rotator.GROQ_MODELS ile uyumlu)
    MODEL_IDX = {
        "lokal": None,  # lokal = GLM
        "cloud_fast": 1,  # llama-3.1-8b-instant
        "cloud_strong": 0,  # llama-3.3-70b-versatile
    }

    # Token eşikleri (config.yaml'den okunur)
    LOKAL_MAX_TOKENS = _LOKAL_MAX
    CLOUD_MIN_TOKENS = _CLOUD_MIN

    def __init__(self):
        self._ogrenilmis_tercihler: dict = {}

    def model_sec(self, prompt: str, gorev_turu: str = "genel", strategy_mgr=None) -> str:
        """
        Döner: 'lokal' | 'cloud'
        """
        # 1. Öğrenilmiş tercih
        if strategy_mgr is not None:
            try:
                ogrenilmis = strategy_mgr.en_iyi_model_bul(gorev_turu)
                if ogrenilmis:
                    return "lokal" if ogrenilmis == "Lokal" else "cloud"
            except Exception:
                pass

        tier = self._karar_ver(prompt, gorev_turu)
        return "lokal" if tier == "lokal" else "cloud"

    def model_sec_detayli(self, prompt: str, gorev_turu: str = "genel", strategy_mgr=None) -> dict:
        """
        Detaylı karar: model tier + groq model index + açıklama döner.
        telegram_bot.py'de aktif_provider_al(gorev_turu) çağrısında kullanılır.
        """
        if strategy_mgr is not None:
            try:
                ogrenilmis = strategy_mgr.en_iyi_model_bul(gorev_turu)
                if ogrenilmis:
                    tier = "lokal" if ogrenilmis == "Lokal" else "cloud_fast"
                    return self._dict_donus(tier, "ogrenilmis_tercih")
            except Exception:
                pass

        tier = self._karar_ver(prompt, gorev_turu)
        return self._dict_donus(tier, "kural_tabali")

    def _karar_ver(self, prompt: str, gorev_turu: str) -> str:
        pl = prompt.lower()
        tokens = _token_tahmini(prompt)

        # 1. Görev türü haritası
        task_tier = self.TASK_MAP.get(gorev_turu)
        if task_tier is not None:
            return task_tier

        # 2. Çok kısa prompt → lokal
        if tokens <= self.LOKAL_MAX_TOKENS:
            if any(k in pl for k in self.BASIT_KELIMELER):
                return "lokal"
            if not any(k in pl for k in self.KARMASIK_KELIMELER):
                return "lokal"

        # 3. Karmaşık kelime → cloud_strong
        if any(k in pl for k in self.KARMASIK_KELIMELER):
            return "cloud_strong"

        # 4. Orta kelime → cloud_fast
        if any(k in pl for k in self.ORTA_KELIMELER):
            return "cloud_fast"

        # 5. Token bazlı karar
        if tokens >= self.CLOUD_MIN_TOKENS:
            return "cloud_strong"
        if tokens >= self.LOKAL_MAX_TOKENS:
            return "cloud_fast"

        # 6. Varsayılan
        return "lokal"

    def _dict_donus(self, tier: str, neden: str) -> dict:
        groq_idx = self.MODEL_IDX.get(tier, 1)
        return {
            "tier": tier,
            "lokal": tier == "lokal",
            "cloud": tier != "lokal",
            "groq_idx": groq_idx,  # api_rotator.aktif_provider_al(tercih_model_idx=groq_idx)
            "neden": neden,
        }

    def ozet(self) -> str:
        return (
            "Model Yoneticisi (v2):\n"
            "Basit/kisa  → GLM-4.6V (Lokal, bedava)\n"
            "Orta        → Groq llama-3.1-8b-instant (hizli, ucuz)\n"
            "Karmasik    → Groq llama-3.3-70b-versatile (guclu)\n"
            "Fallback    → gemma2-9b-it\n"
            "Ogrenme     : Gecmis basarilara gore otomatik guncelleniyor"
        )


model_mgr = ModelManager()
