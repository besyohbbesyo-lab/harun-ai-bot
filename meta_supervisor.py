# meta_supervisor.py - Aşama 3: Self-Reflection + Confidence + Doğrulama
from datetime import datetime
from enum import Enum


class SystemMode(Enum):
    FAST = "hizli"
    BALANCED = "dengeli"
    DEEP = "derin"
    RESEARCH = "arastirma"


class MetaSupervisor:
    def __init__(self, policy, reward_sys):
        self.policy = policy
        self.reward_sys = reward_sys
        self.current_mode = SystemMode.BALANCED
        self.loop_counter = 0
        self.last_tool_sequence = []
        self.mod_gecmisi = []
        self.MALIYET_ESIGI = 3.0
        self.GUVEN_ESIGI = 0.4
        self.BASARI_ESIGI = 0.8

        # Aşama 3: Self-reflection istatistikleri
        self.dogrulama_sayisi = 0  # Kaç kez ikinci model devreye girdi
        self.dusuk_guven_sayisi = 0  # Kaç kez düşük güven tespit edildi
        self.hata_istatistikleri = {
            "bilmiyorum": 0,
            "yanlis_anlama": 0,
            "api_hatasi": 0,
            "basarili": 0,
        }

    def mod_belirle(self, gorev_turu: str, gorev_metni: str = "") -> dict:
        confidence = self.policy.state["confidence_score"]
        success_rate = self.policy.state["success_rate"]

        if self._dongu_tespit(gorev_turu):
            self._mod_degistir(SystemMode.FAST, "Dongu tespit edildi")
            return self._mod_parametreleri()

        avg_cost = self.policy.state.get("avg_cost", 1.0)
        if avg_cost > self.MALIYET_ESIGI:
            self._mod_degistir(SystemMode.FAST, "Maliyet patlamasi")
            return self._mod_parametreleri()

        if confidence < self.GUVEN_ESIGI:
            self._mod_degistir(SystemMode.DEEP, "Dusuk guven skoru")
            return self._mod_parametreleri()

        arastirma_kelimeleri = ["arastir", "karsilastir", "analiz", "plan", "rapor", "detayli"]
        if any(k in gorev_metni.lower() for k in arastirma_kelimeleri):
            self._mod_degistir(SystemMode.RESEARCH, "Arastirma gorevi")
            return self._mod_parametreleri()

        riskli_turler = ["kod", "planner", "vision"]
        if gorev_turu in riskli_turler and confidence < 0.7:
            self._mod_degistir(SystemMode.DEEP, f"Riskli gorev: {gorev_turu}")
            return self._mod_parametreleri()

        if success_rate > self.BASARI_ESIGI and confidence > 0.7:
            self._mod_degistir(SystemMode.FAST, "Yuksek performans")
            return self._mod_parametreleri()

        self._mod_degistir(SystemMode.BALANCED, "Normal islem")
        return self._mod_parametreleri()

    def _mod_parametreleri(self) -> dict:
        parametreler = {
            SystemMode.FAST: {
                "mod": "hizli",
                "retrieval_depth": 1,
                "reasoning_depth": 1,
                "temperature": 0.7,
                "max_tokens": 1000,
                "hafiza_destegi": False,
            },
            SystemMode.BALANCED: {
                "mod": "dengeli",
                "retrieval_depth": 3,
                "reasoning_depth": 2,
                "temperature": 0.5,
                "max_tokens": 2000,
                "hafiza_destegi": True,
            },
            SystemMode.DEEP: {
                "mod": "derin",
                "retrieval_depth": 5,
                "reasoning_depth": 4,
                "temperature": 0.2,
                "max_tokens": 3000,
                "hafiza_destegi": True,
            },
            SystemMode.RESEARCH: {
                "mod": "arastirma",
                "retrieval_depth": 5,
                "reasoning_depth": 4,
                "temperature": 0.3,
                "max_tokens": 4000,
                "hafiza_destegi": True,
            },
        }
        return parametreler[self.current_mode]

    def _dongu_tespit(self, gorev_turu: str) -> bool:
        self.last_tool_sequence.append(gorev_turu)
        if len(self.last_tool_sequence) > 10:
            self.last_tool_sequence.pop(0)

        if len(self.last_tool_sequence) >= 3:
            son_uc = self.last_tool_sequence[-3:]
            if len(set(son_uc)) == 1:
                self.loop_counter += 1
                return self.loop_counter >= 3
        self.loop_counter = 0
        return False

    def _mod_degistir(self, yeni_mod: SystemMode, sebep: str):
        if self.current_mode != yeni_mod:
            self.mod_gecmisi.append(
                {
                    "zaman": str(datetime.now()),
                    "eski_mod": self.current_mode.value,
                    "yeni_mod": yeni_mod.value,
                    "sebep": sebep,
                }
            )
            if len(self.mod_gecmisi) > 20:
                self.mod_gecmisi.pop(0)
            self.current_mode = yeni_mod

    def guclendir(self, basari: bool):
        if not basari and self.current_mode == SystemMode.FAST:
            self._mod_degistir(SystemMode.BALANCED, "Basarisizlik - mod yukseltildi")

    # ─────────────────────────────────────────────────────────
    # AŞAMA 3: SELF-REFLECTION FONKSİYONLARI
    # ─────────────────────────────────────────────────────────

    def dogrulama_gerekli_mi(self, confidence: float) -> bool:
        """
        Confidence skoru düşükse ikinci modelden doğrulama iste.
        Eşik: 0.4 altı
        """
        if confidence < 0.4:
            self.dusuk_guven_sayisi += 1
            return True
        return False

    def hata_kaydet(self, hata_tipi: str):
        """Hata tipini istatistiklere ekle"""
        if hata_tipi in self.hata_istatistikleri:
            self.hata_istatistikleri[hata_tipi] += 1

    def dogrulama_kaydet(self):
        """İkinci model doğrulaması yapıldığında say"""
        self.dogrulama_sayisi += 1

    def dogrulama_promptu_olustur(self, orijinal_soru: str, ilk_yanit: str) -> str:
        """
        Düşük güvenli yanıt için doğrulama promptu oluştur.
        İkinci model bu promptla kontrol yapacak.
        """
        return (
            f"Aşağıdaki soruya verilen yanıtı değerlendir ve gerekiyorsa düzelt:\n\n"
            f"Soru: {orijinal_soru}\n\n"
            f"İlk yanıt: {ilk_yanit}\n\n"
            f"Bu yanıt doğru ve yeterli mi? Eğer eksik veya yanlış bir şey varsa "
            f"düzeltilmiş yanıtı yaz. Eğer yanıt doğruysa 'ONAYLANDI: ' ile başlayarak "
            f"kısa bir özet yaz."
        )

    def dogrulama_sonucu_isle(self, dogrulama_yaniti: str, ilk_yanit: str) -> str:
        """
        Doğrulama yanıtını işle ve son yanıtı belirle.
        ONAYLANDI → ilk yanıt kullan
        Değişiklik var → doğrulama yanıtını kullan
        """
        if dogrulama_yaniti.strip().upper().startswith("ONAYLANDI"):
            return ilk_yanit
        return dogrulama_yaniti

    def ozet(self) -> str:
        son_degisim = self.mod_gecmisi[-1] if self.mod_gecmisi else None
        toplam_hata = sum(self.hata_istatistikleri.values())
        basarili = self.hata_istatistikleri.get("basarili", 0)
        basari_orani = f"%{int(basarili/toplam_hata*100)}" if toplam_hata > 0 else "Veri yok"

        mesaj = (
            f"Meta-Supervisor:\n"
            f"Aktif mod: {self.current_mode.value}\n"
            f"Toplam mod degisimi: {len(self.mod_gecmisi)}\n"
            f"Dogrulama yapilan: {self.dogrulama_sayisi} kez\n"
            f"Dusuk guven tespiti: {self.dusuk_guven_sayisi} kez\n"
            f"Hata dagilimi - Basarili: {self.hata_istatistikleri['basarili']} | "
            f"Bilmiyorum: {self.hata_istatistikleri['bilmiyorum']} | "
            f"Yanlis anlama: {self.hata_istatistikleri['yanlis_anlama']} | "
            f"API: {self.hata_istatistikleri['api_hatasi']}\n"
            f"Genel basari: {basari_orani}\n"
        )
        if son_degisim:
            mesaj += f"Son mod degisimi: {son_degisim['sebep']}\n"
        return mesaj
