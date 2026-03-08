# reward_system.py
# ASAMA 16: AEE Metodoloji Duzeltmesi
# - Reward formulu acikca belgelendi
# - EMA (alpha=0.3) etiketi eklendi
# - Self-consistency maliyeti optimize edildi (%60 daha az 2. API cagrisi)
# - Hata kategorileri genisletildi (egitim_toplayici ile uyumlu)

import json
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
REWARD_DOSYASI = BASE_DIR / "reward_history.json"

# ─────────────────────────────────────────────────────────────
# ASAMA 16: REWARD FORMULU DOKUMANTASYONU
# ─────────────────────────────────────────────────────────────
#
# REWARD HESAPLAMA FORMULU:
#   reward = (basari_skoru * 0.5)      <- En buyuk agirlik: basardi mi?
#           + (verimlilik   * 0.2)      <- Hiz ve token ekonomisi
#           + (kullanici_gb * 0.2)      <- Kullanici geri bildirimi (varsayilan 0.5)
#           - (maliyet_ceza * 0.1)      <- Token + sure cezasi
#
# SMOOTHED REWARD (EMA — Exponential Moving Average):
#   smoothed = onceki_smoothed * (1 - alpha) + yeni_reward * alpha
#   alpha = 0.3  (her yeni kayit %30 agirlik tasir)
#   Yorum: Dusuk alpha = stabil ama yavash; Yuksek alpha = hizli ama titresir
#          0.3 bu sistemin tek kullanici yapisina uygundur.
#
# CONFIDENCE FORMULU:
#   confidence = 0.5 (baslangic)
#              + basari_etkisi    (+-0.30)
#              + hata_cezasi      (0.0 ile -0.40)
#              + uzunluk_etkisi   (+-0.20)
#              + sure_etkisi      (+-0.10)
#              + gecmis_etkisi    (+-0.10)
#              + consistency_etkisi (+-0.20, sadece veri varsa)
#
# SELF-CONSISTENCY TETIKLEME KURALI (ASAMA 16):
#   Maliyet optimizasyonu: Ikinci API cagrisi YALNIZCA su kosullarda yapilir:
#     1. smoothed_reward < 0.4  (sistem son zamanlarda dusuk performans)
#     VE
#     2. len(soru) > 50         (kisa sorular icin gereksiz)
#   Bu kural yaklasik %60 daha az ikincil API cagrisi saglar.
#
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# HATA SINIFLANDIRMASI (ASAMA 16: Kategoriler genisletildi)
# ─────────────────────────────────────────────────────────────

HATA_TIPLERI = {
    "bilmiyorum": [
        "bilmiyorum",
        "emin degilim",
        "bilgim yok",
        "hakkinda bilgim",
        "haberdar degilim",
        "dogrulayamam",
        "kesin soyleyemem",
        "net bir bilgim",
    ],
    "yanlis_anlama": [
        "yanlis anladim",
        "kastettiniz",
        "daha iyi anlayabilmem",
        "sorunuzu tekrar",
        "tam olarak ne demek istediginizi",
    ],
    "api_hatasi": [
        "Groq Hata",
        "Lokal Hata",
        "Gemini Hata",
        "API hatasi",
        "Baglanti hatasi",
        "timeout",
        "rate limit",
        "connection error",
    ],
    "basarili": [],
}

# ASAMA 16: egitim_toplayici.py ile uyumlu hata kategorisi haritalama
# hata_siniflandir() sonucu -> basarisiz_kaydet(hata_kategorisi=...) icin
HATA_KATEGORI_HARITASI = {
    "bilmiyorum": "yanlis_bilgi",  # Yanit bilgi eksikligi iceriyorsa
    "yanlis_anlama": "yanlis_anlama",  # Soruyu yanlis anlamissa
    "api_hatasi": "format_hatasi",  # Teknik hata -> format sorunu olarak kayit
    "basarili": "bilinmiyor",  # Basarisiz ama kategorisi belirsiz
}


def hata_siniflandir(yanit: str) -> str:
    """Yaniti analiz ederek hata tipini belirle."""
    yanit_lower = yanit.lower()
    for tip, kelimeler in HATA_TIPLERI.items():
        if tip == "basarili":
            continue
        if any(k in yanit_lower for k in kelimeler):
            return tip
    return "basarili"


def hata_kategorisi_al(hata_tipi: str) -> str:
    """
    ASAMA 16: hata_siniflandir() sonucunu egitim_toplayici formatina cevir.
    Doner: yanlis_bilgi | yanlis_anlama | eksik_cevap | format_hatasi | bilinmiyor
    """
    return HATA_KATEGORI_HARITASI.get(hata_tipi, "bilinmiyor")


# ─────────────────────────────────────────────────────────────
# ASAMA 16: SELF-CONSISTENCY — MALIYET OPTIMIZE EDILDİ
# ─────────────────────────────────────────────────────────────

_consistency_cache: dict = {}


def self_consistency_gerekli_mi(smoothed_reward: float, soru: str) -> bool:
    """
    ASAMA 16: Ikinci API cagrisi YALNIZCA bu kosullarda yapilir:
      - smoothed_reward < 0.4 (sistem dusuk performansta)
      - soru uzunlugu > 50 karakter (kisa sorular icin gereksiz)
    Bu yaklasik %60 daha az ikincil API cagrisi saglar.
    """
    return smoothed_reward < 0.4 and len(soru) > 50


def self_consistency_skoru(yanit1: str, yanit2: str) -> float:
    """
    Iki yanit arasindaki tutarlilik skorunu hesapla.
    Jaccard + uzunluk benzerligine + rakam tutarliligi.
    Doner: 0.0 (hic tutarli degil) — 1.0 (tam tutarli)
    """
    if not yanit1 or not yanit2:
        return 0.5

    def temizle(metin):
        metin = metin.lower()
        metin = re.sub(r"[^\w\s]", " ", metin)
        kelimeler = set(metin.split())
        stopwords = {
            "ve",
            "veya",
            "bir",
            "bu",
            "su",
            "o",
            "icin",
            "ile",
            "de",
            "da",
            "ki",
            "mi",
            "mu",
            "the",
            "a",
            "an",
            "is",
            "are",
            "in",
        }
        return kelimeler - stopwords

    k1 = temizle(yanit1)
    k2 = temizle(yanit2)

    if not k1 or not k2:
        return 0.5

    # Jaccard benzerlik (agirlik %50)
    kesisim = len(k1 & k2)
    birlesim = len(k1 | k2)
    jaccard = kesisim / birlesim if birlesim > 0 else 0.0

    # Uzunluk benzerlik (agirlik %30)
    u1, u2 = len(yanit1), len(yanit2)
    uzunluk = (min(u1, u2) / max(u1, u2)) * 0.3 if max(u1, u2) > 0 else 0.3

    # Rakam tutarliligi (agirlik %20)
    r1 = set(re.findall(r"\d+", yanit1))
    r2 = set(re.findall(r"\d+", yanit2))
    if r1 or r2:
        br = len(r1 | r2)
        rakam = (len(r1 & r2) / br) * 0.2 if br > 0 else 0.0
    else:
        rakam = 0.2

    return round(min(1.0, (jaccard * 0.5) + uzunluk + rakam), 2)


def consistency_kaydet(soru_hash: str, yanit: str, temperature_seviye: str):
    """Ayni soruya verilen iki farkli temperature yanitini sakla."""
    if soru_hash not in _consistency_cache:
        _consistency_cache[soru_hash] = {}
    _consistency_cache[soru_hash][temperature_seviye] = yanit
    if len(_consistency_cache) > 100:
        ilk = next(iter(_consistency_cache))
        del _consistency_cache[ilk]


def consistency_hesapla(soru_hash: str) -> float:
    """Her iki yanit kaydedilmisse tutarlilik skorunu dondur."""
    kayit = _consistency_cache.get(soru_hash, {})
    if "dusuk" in kayit and "yuksek" in kayit:
        return self_consistency_skoru(kayit["dusuk"], kayit["yuksek"])
    return 0.5


def soru_hash_olustur(soru: str) -> str:
    return str(abs(hash(soru[:100])))


# ─────────────────────────────────────────────────────────────
# CONFIDENCE HESAPLAMA
# ─────────────────────────────────────────────────────────────


def confidence_hesapla(
    yanit: str,
    sure: float,
    basari: bool,
    smoothed_reward: float,
    hata_tipi: str,
    consistency_skoru: float = 0.5,
) -> float:
    """
    ASAMA 16: Formul acikca belgelendi (bkz. dosya basi).

    confidence = 0.50 (baslangic)
               + basari_etkisi     (basariysa +0.30, degilse -0.30)
               + hata_cezasi       (api_hatasi=-0.40, bilmiyorum=-0.20 ...)
               + uzunluk_etkisi    (<20kar=-0.20, >200kar=+0.10)
               + sure_etkisi       (>20sn=-0.10, <5sn=+0.05)
               + gecmis_etkisi     ((smoothed-0.5)*0.20)
               + consistency_etkisi((consistency-0.5)*0.40, sadece veri varsa)
    """
    skor = 0.5

    # Basari etkisi (+- 0.30)
    skor += 0.3 if basari else -0.3

    # Hata tipi cezasi
    hata_cezasi = {"api_hatasi": -0.4, "bilmiyorum": -0.2, "yanlis_anlama": -0.15, "basarili": 0.0}
    skor += hata_cezasi.get(hata_tipi, 0.0)

    # Uzunluk etkisi
    uzunluk = len(yanit.strip())
    if uzunluk < 20:
        skor -= 0.2
    elif uzunluk < 50:
        skor -= 0.1
    elif uzunluk > 200:
        skor += 0.1

    # Sure etkisi
    if sure > 20:
        skor -= 0.1
    elif sure < 5:
        skor += 0.05

    # Gecmis smoothed reward etkisi
    skor += (smoothed_reward - 0.5) * 0.2

    # Self-consistency etkisi (sadece veri varsa — 0.5 = veri yok)
    if consistency_skoru != 0.5:
        skor += (consistency_skoru - 0.5) * 0.4

    return round(max(0.0, min(1.0, skor)), 2)


def confidence_metni_olustur(
    confidence: float, hata_tipi: str, model_adi: str = "", consistency_skoru: float = 0.5
) -> str:
    """Kullaniciya gosterilecek guven bilgisi satiri."""
    yuzde = int(confidence * 100)

    if confidence >= 0.75:
        ikon, seviye = "[ OK ]", "Yuksek"
    elif confidence >= 0.5:
        ikon, seviye = "[  !  ]", "Orta"
    else:
        ikon, seviye = "[ !! ]", "Dusuk"

    hata_notu = {
        "bilmiyorum": " | Bilgi siniri",
        "yanlis_anlama": " | Yeniden sor",
        "api_hatasi": " | API sorunu",
    }.get(hata_tipi, "")

    c_notu = ""
    if consistency_skoru != 0.5:
        c_notu = f" | Tutarlilik: %{int(consistency_skoru * 100)}"

    model_notu = f" | {model_adi}" if model_adi else ""

    return f"\n\n{ikon} Guven: %{yuzde} ({seviye}){c_notu}{model_notu}{hata_notu}"


# ─────────────────────────────────────────────────────────────
# REWARD SİSTEMİ
# ─────────────────────────────────────────────────────────────


class RewardSystem:
    # ASAMA 16: alpha=0.3 (EMA — Exponential Moving Average)
    # Onceki alpha=0.1 cok yavas ogreniyordu.
    # 0.3: her yeni kayit %30 agirlik tasir, sistem degisime daha duyarli.
    def __init__(self, window_size: int = 50, alpha: float = 0.3):
        self.window_size = window_size
        self.alpha = alpha  # EMA katsayisi
        self.reward_history = self._yukle()

    def _yukle(self) -> list:
        try:
            if REWARD_DOSYASI.exists():
                with open(REWARD_DOSYASI, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Reward yukle hatasi: {e}")
        return []

    def _kaydet(self):
        try:
            with open(REWARD_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self.reward_history[-200:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Reward kayit hatasi: {e}")

    def hesapla(
        self,
        basari: bool,
        sure: float = 1.0,
        token_tahmini: int = 500,
        kullanici_geri_bildirim: float = 0.5,
    ) -> float:
        """
        ASAMA 16: Formul (bkz. dosya basi):
          reward = basari*0.5 + verimlilik*0.2 + kullanici_gb*0.2 - maliyet*0.1
          smoothed = onceki*(1-alpha) + yeni*alpha   [EMA, alpha=0.3]
        """
        basari_skoru = 1.0 if basari else 0.0
        token_maliyet = min(1.0, token_tahmini / 5000)
        sure_maliyet = min(1.0, sure / 30.0)
        verimlilik = 1.0 / (1.0 + token_maliyet + sure_maliyet)
        maliyet_ceza = (token_maliyet * 0.6) + (sure_maliyet * 0.4)

        reward = (
            (basari_skoru * 0.5)
            + (verimlilik * 0.2)
            + (kullanici_geri_bildirim * 0.2)
            - (maliyet_ceza * 0.1)
        )

        normalize_edilmis = self._normalize(reward)
        son_smoothed = self.reward_history[-1]["smoothed"] if self.reward_history else 0.5

        # EMA (Exponential Moving Average) — alpha=0.3
        smoothed = son_smoothed * (1 - self.alpha) + normalize_edilmis * self.alpha

        kayit = {
            "zaman": str(datetime.now()),
            "basari": basari,
            "raw": round(reward, 4),
            "normalized": round(normalize_edilmis, 4),
            "smoothed": round(smoothed, 4),
            "sure": sure,
            "token_tahmini": token_tahmini,
            # ASAMA 16: Formul bilesenleri kaydediliyor (debug icin)
            "formula": {
                "basari_katkisi": round(basari_skoru * 0.5, 3),
                "verimlilik_katkisi": round(verimlilik * 0.2, 3),
                "kullanici_katkisi": round(kullanici_geri_bildirim * 0.2, 3),
                "maliyet_cezasi": round(maliyet_ceza * 0.1, 3),
            },
        }

        self.reward_history.append(kayit)
        if len(self.reward_history) > 200:
            self.reward_history = self.reward_history[-200:]
        self._kaydet()
        return smoothed

    def _normalize(self, reward: float) -> float:
        if len(self.reward_history) < 5:
            return 0.5
        son_rewardlar = [r["raw"] for r in self.reward_history[-self.window_size :]]
        min_r = min(son_rewardlar)
        max_r = max(son_rewardlar)
        if max_r == min_r:
            return 0.5
        return (reward - min_r) / (max_r - min_r + 1e-8)

    def son_smoothed(self) -> float:
        if not self.reward_history:
            return 0.5
        return self.reward_history[-1]["smoothed"]

    def formul_ozeti(self) -> str:
        """
        ASAMA 16: Son kaydin formul bilesenlerini goster (dashboard icin).
        """
        if not self.reward_history:
            return "Henuz reward verisi yok."
        son = self.reward_history[-1]
        f = son.get("formula", {})
        return (
            f"Son Reward Formul Dagilimi:\n"
            f"  Basari katkisi   : +{f.get('basari_katkisi', 0):.3f}\n"
            f"  Verimlilik katkisi: +{f.get('verimlilik_katkisi', 0):.3f}\n"
            f"  Kullanici katkisi : +{f.get('kullanici_katkisi', 0):.3f}\n"
            f"  Maliyet cezasi   : -{f.get('maliyet_cezasi', 0):.3f}\n"
            f"  Smoothed (EMA)   :  {son['smoothed']:.3f}"
        )

    def ozet(self) -> str:
        if not self.reward_history:
            return "Henuz reward verisi yok."
        son_10 = self.reward_history[-10:]
        basari_sayisi = sum(1 for r in son_10 if r["basari"])
        ort_smoothed = sum(r["smoothed"] for r in son_10) / len(son_10)
        return (
            f"Reward Sistemi (EMA alpha={self.alpha}):\n"
            f"Son 10 gorevde basari: {basari_sayisi}/10\n"
            f"Ortalama smoothed reward: {ort_smoothed:.3f}\n"
            f"Toplam kayit: {len(self.reward_history)}"
        )
