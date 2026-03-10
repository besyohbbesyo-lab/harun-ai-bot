# prompt_evolution.py - AEE Aşama 4: İstatistiksel Prompt Optimizasyonu
import json
import random
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
PROMPT_DOSYASI = BASE_DIR / "prompt_data.json"

# Varsayılan prompt şablonları (A/B test için)
VARSAYILAN_PROMPTLAR = {
    "sohbet": [
        {
            "id": "sohbet_v1",
            "icerik": "Asagidaki soruyu Turkce, kisa ve net yanıtla:\n{soru}",
            "versiyon": "v1",
        },
        {
            "id": "sohbet_v2",
            "icerik": "Sen yardimci bir AI asistanisin. Asagidaki soruyu adim adim dusun ve Turkce yanıtla:\n{soru}",
            "versiyon": "v2",
        },
    ],
    "kod": [
        {
            "id": "kod_v1",
            "icerik": "Asagidaki aciklamaya gore Python kodu yaz:\n{aciklama}\n\nSadece calisacak kodu yaz.",
            "versiyon": "v1",
        },
        {
            "id": "kod_v2",
            "icerik": "Python uzmanı olarak asagidaki gorevi coz:\n{aciklama}\n\nOnce problemi analiz et, sonra temiz ve yorumlu kod yaz.",
            "versiyon": "v2",
        },
    ],
    "arastirma": [
        {
            "id": "arastirma_v1",
            "icerik": "Asagidaki konuyu arastir ve ozetle:\n{konu}\n\nBilgiler: {bilgiler}",
            "versiyon": "v1",
        },
        {
            "id": "arastirma_v2",
            "icerik": "'{konu}' hakkinda kapsamli bir analiz yap.\nKaynaklar: {bilgiler}\n\nYapi: 1) Ozet 2) Ana Noktalar 3) Sonuc",
            "versiyon": "v2",
        },
    ],
    "genel": [
        {"id": "genel_v1", "icerik": "{prompt}", "versiyon": "v1"},
        {
            "id": "genel_v2",
            "icerik": "Asagidaki gorevi dikkatlice ve adim adim tamamla:\n{prompt}",
            "versiyon": "v2",
        },
    ],
}


class PromptEvolution:
    def __init__(self, min_ornek=10):
        self.min_ornek = min_ornek
        self.data = self._yukle()

    def _yukle(self) -> dict:
        try:
            if PROMPT_DOSYASI.exists():
                with open(PROMPT_DOSYASI, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Prompt yukle hatasi: {e}")
        # İlk kurulum
        data = {}
        for tur, promptlar in VARSAYILAN_PROMPTLAR.items():
            for p in promptlar:
                data[p["id"]] = {
                    "tur": tur,
                    "icerik": p["icerik"],
                    "versiyon": p["versiyon"],
                    "basarili": 0,
                    "basarisiz": 0,
                    "toplam": 0,
                    "aktif": True,
                    "sampiyun": False,
                    "olusturulma": str(datetime.now()),
                }
        self._kaydet(data)
        return data

    def _kaydet(self, data=None):
        try:
            with open(PROMPT_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(data or self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Prompt kayit hatasi: {e}")

    def prompt_sec(self, tur: str) -> tuple:
        """Thompson Sampling ile en iyi promptu seç"""
        aktif_promptlar = [
            (pid, p) for pid, p in self.data.items() if p["tur"] == tur and p["aktif"]
        ]

        if not aktif_promptlar:
            aktif_promptlar = [
                (pid, p) for pid, p in self.data.items() if p["tur"] == "genel" and p["aktif"]
            ]

        if not aktif_promptlar:
            return None, "{prompt}"

        # Yeterli veri yoksa rastgele seç
        if any(p["toplam"] < self.min_ornek for _, p in aktif_promptlar):
            secilen_id, secilen = random.choice(aktif_promptlar)
            return secilen_id, secilen["icerik"]

        # Thompson Sampling
        en_iyi_id = None
        en_iyi_skor = -1.0

        for pid, p in aktif_promptlar:
            alpha = p["basarili"] + 1
            beta_val = p["basarisiz"] + 1
            skor = self._beta_ornekle(alpha, beta_val)
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi_id = pid

        return en_iyi_id, self.data[en_iyi_id]["icerik"]

    def _beta_ornekle(self, alpha: float, beta_val: float) -> float:
        """Beta dağılımından örnekle"""
        try:
            x = random.gammavariate(alpha, 1)
            y = random.gammavariate(beta_val, 1)
            return x / (x + y)
        except Exception:
            return alpha / (alpha + beta_val)

    def sonuc_kaydet(self, prompt_id: str, basari: bool):
        """Prompt kullanım sonucunu kaydet"""
        if prompt_id not in self.data:
            return
        p = self.data[prompt_id]
        p["toplam"] += 1
        if basari:
            p["basarili"] += 1
        else:
            p["basarisiz"] += 1

        if p["toplam"] >= self.min_ornek:
            self._degerlendir(prompt_id)

        self._kaydet()

    def _degerlendir(self, prompt_id: str):
        """Promptu şampiyonla karşılaştır"""
        p = self.data[prompt_id]
        tur = p["tur"]
        basari_orani = p["basarili"] / max(1, p["toplam"])

        sampiyun = self._sampiyun_bul(tur)

        if not sampiyun or sampiyun[0] == prompt_id:
            p["sampiyun"] = True
            return

        s_id, s_data = sampiyun
        s_basari = s_data["basarili"] / max(1, s_data["toplam"])

        if basari_orani - s_basari > 0.15 and p["toplam"] >= self.min_ornek:
            self.data[s_id]["sampiyun"] = False
            p["sampiyun"] = True
            print(
                f"Prompt terfi: {prompt_id} yeni sampiyun! ({basari_orani:.2f} vs {s_basari:.2f})"
            )
        elif s_basari - basari_orani > 0.15 and p["toplam"] >= self.min_ornek * 2:
            p["aktif"] = False
            print(f"Prompt devre disi: {prompt_id} ({basari_orani:.2f} vs {s_basari:.2f})")

    def _sampiyun_bul(self, tur: str):
        for pid, p in self.data.items():
            if p["tur"] == tur and p.get("sampiyun") and p["aktif"]:
                return pid, p
        return None

    def prompt_uygula(self, prompt_id: str, tur: str, **kwargs) -> str:
        if not prompt_id or prompt_id not in self.data:
            return kwargs.get("prompt", kwargs.get("soru", ""))
        icerik = self.data[prompt_id]["icerik"]
        try:
            return icerik.format(**kwargs)
        except Exception:
            return kwargs.get("prompt", kwargs.get("soru", icerik))

    def ozet(self) -> str:
        aktif = sum(1 for p in self.data.values() if p["aktif"])
        sampiyunlar = [(pid, p) for pid, p in self.data.items() if p.get("sampiyun")]

        mesaj = f"Prompt Evrimi:\n" f"Toplam prompt: {len(self.data)} ({aktif} aktif)\n"
        if sampiyunlar:
            mesaj += "Mevcut sampiyonlar:\n"
            for pid, p in sampiyunlar:
                oran = p["basarili"] / max(1, p["toplam"])
                mesaj += f"  {p['tur']}: {pid} (%{oran*100:.0f} basari, {p['toplam']} test)\n"
        else:
            mesaj += "Henuz sampiyun belirlenmedi (veri toplaniyor)\n"
        return mesaj
