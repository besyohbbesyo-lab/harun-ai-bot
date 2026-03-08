# strategy_manager.py - Aşama 4: Model Bazlı Başarı Takibi
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.resolve()
STRATEJI_DOSYASI = BASE_DIR / "strategy_data.json"
MODEL_PERFORMANS_DOSYASI = BASE_DIR / "model_performans.json"


class StrategyManager:
    def __init__(self):
        self.strategies = self._yukle()
        self.model_performans = self._model_yukle()

    def _yukle(self) -> dict:
        try:
            if STRATEJI_DOSYASI.exists():
                with open(STRATEJI_DOSYASI, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Strateji yukle hatasi: {e}")
        return {}

    def _kaydet(self):
        try:
            with open(STRATEJI_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self.strategies, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Strateji kayit hatasi: {e}")

    # ─────────────────────────────────────────────────────────
    # AŞAMA 4: MODEL PERFORMANS TAKİBİ
    # ─────────────────────────────────────────────────────────

    def _model_yukle(self) -> dict:
        try:
            if MODEL_PERFORMANS_DOSYASI.exists():
                with open(MODEL_PERFORMANS_DOSYASI, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Model performans yukle hatasi: {e}")
        return {}

    def _model_kaydet(self):
        try:
            with open(MODEL_PERFORMANS_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self.model_performans, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Model performans kayit hatasi: {e}")

    def model_sonuc_kaydet(self, model_adi: str, gorev_turu: str, basari: bool, sure: float):
        """
        Hangi modelin hangi görev türünde ne kadar başarılı olduğunu kaydet.
        model_adi: 'Gemini' | 'Groq' | 'Lokal'
        """
        anahtar = f"{model_adi}_{gorev_turu}"
        if anahtar not in self.model_performans:
            self.model_performans[anahtar] = {
                "model": model_adi,
                "gorev_turu": gorev_turu,
                "toplam": 0,
                "basarili": 0,
                "toplam_sure": 0.0,
                "ort_sure": 0.0,
                "basari_orani": 0.0,
                "son_guncelleme": str(datetime.now()),
            }

        p = self.model_performans[anahtar]
        p["toplam"] += 1
        if basari:
            p["basarili"] += 1
        p["toplam_sure"] += sure
        p["ort_sure"] = round(p["toplam_sure"] / p["toplam"], 2)
        p["basari_orani"] = round(p["basarili"] / p["toplam"], 3)
        p["son_guncelleme"] = str(datetime.now())
        self._model_kaydet()

    def en_iyi_model_bul(self, gorev_turu: str) -> Optional[str]:
        """
        Geçmiş veriye göre bu görev türü için en başarılı modeli döndür.
        Yeterli veri yoksa None döner (varsayılan kullanılır).
        """
        adaylar = []
        for anahtar, p in self.model_performans.items():
            if p["gorev_turu"] == gorev_turu and p["toplam"] >= 5:
                # Başarı oranı yüksek, süre düşük olan kazanır
                skor = p["basari_orani"] / max(0.1, p["ort_sure"] / 10.0)
                adaylar.append((p["model"], skor, p["basari_orani"]))

        if not adaylar:
            return None

        adaylar.sort(key=lambda x: x[1], reverse=True)
        en_iyi_model = adaylar[0][0]
        print(f"[ModelManager] {gorev_turu} için öğrenilmiş en iyi model: {en_iyi_model}")
        return en_iyi_model

    def basarisiz_toollari_al(self) -> list:
        """
        Başarı oranı düşük (< %50) olan model+görev kombinasyonlarını listele.
        Dashboard'da gösterilecek.
        """
        basarisizlar = []
        for anahtar, p in self.model_performans.items():
            if p["toplam"] >= 5 and p["basari_orani"] < 0.5:
                basarisizlar.append(
                    {
                        "model": p["model"],
                        "gorev_turu": p["gorev_turu"],
                        "basari_orani": p["basari_orani"],
                        "toplam": p["toplam"],
                        "ort_sure": p["ort_sure"],
                    }
                )
        basarisizlar.sort(key=lambda x: x["basari_orani"])
        return basarisizlar

    def model_performans_ozeti(self) -> str:
        """Dashboard ve /aee komutu için model performans özeti"""
        if not self.model_performans:
            return "Henuz model performans verisi yok. (En az 5 gorev gerekli)"

        satirlar = ["Model Performanslari:"]
        gorev_turlerine_gore = {}

        for anahtar, p in self.model_performans.items():
            tur = p["gorev_turu"]
            if tur not in gorev_turlerine_gore:
                gorev_turlerine_gore[tur] = []
            gorev_turlerine_gore[tur].append(p)

        for tur, modeller in gorev_turlerine_gore.items():
            satirlar.append(f"\n[{tur.upper()}]")
            modeller.sort(key=lambda x: x["basari_orani"], reverse=True)
            for m in modeller:
                bar = "█" * int(m["basari_orani"] * 10) + "░" * (10 - int(m["basari_orani"] * 10))
                satirlar.append(
                    f"  {m['model']}: {bar} %{int(m['basari_orani']*100)} "
                    f"({m['basarili']}/{m['toplam']}, ort {m['ort_sure']}s)"
                )

        return "\n".join(satirlar)

    # ─────────────────────────────────────────────────────────
    # MEVCUT STRATEJİ FONKSİYONLARI
    # ─────────────────────────────────────────────────────────

    def imza_olustur(self, gorev_turu: str, mod: str, araclar: list, retrieval_depth: int) -> str:
        imza_str = f"{gorev_turu}|{mod}|{','.join(araclar)}|{retrieval_depth}"
        return hashlib.md5(imza_str.encode()).hexdigest()[:12]

    def sonuc_kaydet(self, imza: str, gorev_turu: str, basari: bool, sure: float, reward: float):
        if imza not in self.strategies:
            self.strategies[imza] = {
                "gorev_turu": gorev_turu,
                "toplam": 0,
                "basarili": 0,
                "toplam_sure": 0.0,
                "performans_skoru": 0.5,
                "son_guncelleme": str(datetime.now()),
            }

        s = self.strategies[imza]
        s["toplam"] += 1
        if basari:
            s["basarili"] += 1
        s["toplam_sure"] += sure

        basari_orani = s["basarili"] / s["toplam"]
        ort_sure = s["toplam_sure"] / s["toplam"]
        maliyet = max(0.1, ort_sure / 10.0)
        s["performans_skoru"] = basari_orani / maliyet

        if s["toplam"] > 10 and s["performans_skoru"] < 0.3:
            s["aktif"] = False

        s["son_guncelleme"] = str(datetime.now())
        self._kaydet()

    def en_iyi_strateji(self, gorev_turu: str) -> Optional[dict]:
        adaylar = [
            (imza, s)
            for imza, s in self.strategies.items()
            if s.get("gorev_turu") == gorev_turu
            and s.get("aktif", True)
            and s.get("toplam", 0) >= 3
        ]
        if not adaylar:
            return None
        adaylar.sort(key=lambda x: x[1]["performans_skoru"], reverse=True)
        en_iyi_imza, en_iyi = adaylar[0]
        return {
            "imza": en_iyi_imza,
            "basari_orani": en_iyi["basarili"] / en_iyi["toplam"],
            "performans_skoru": en_iyi["performans_skoru"],
            "toplam_kullanim": en_iyi["toplam"],
        }

    def ozet(self) -> str:
        if not self.strategies:
            return "Henuz strateji verisi yok."
        aktif = sum(1 for s in self.strategies.values() if s.get("aktif", True))
        toplam = len(self.strategies)
        en_iyi = max(self.strategies.values(), key=lambda s: s["performans_skoru"], default=None)
        mesaj = f"Strateji Yoneticisi:\n" f"Toplam strateji: {toplam} ({aktif} aktif)\n"
        if en_iyi:
            mesaj += (
                f"En iyi performans: {en_iyi['performans_skoru']:.3f}\n"
                f"({en_iyi['gorev_turu']} - "
                f"{en_iyi['basarili']}/{en_iyi['toplam']} basari)\n\n"
            )
        mesaj += self.model_performans_ozeti()
        return mesaj
