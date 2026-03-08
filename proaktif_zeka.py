# proaktif_zeka.py - Aşama 5: Proaktif Zeka
# Günlük sabah özeti, haftalık zayıf alan raporu, fine-tuning açıklaması

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
PROAKTIF_AYAR = BASE_DIR / "proaktif_ayar.json"
REWARD_DOSYASI = BASE_DIR / "reward_history.json"
EGITIM_DOSYASI = BASE_DIR / "egitim_verisi.jsonl"
MODEL_PERFORMANS_DOSYASI = BASE_DIR / "model_performans.json"

# ─────────────────────────────────────────────────────────────
# AYAR YÖNETİMİ
# ─────────────────────────────────────────────────────────────


def ayar_yukle() -> dict:
    try:
        if PROAKTIF_AYAR.exists():
            with open(PROAKTIF_AYAR, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
    return {
        "sabah_ozeti_saat": "08:00",
        "haftalik_rapor_gun": "Pazartesi",
        "son_sabah_ozeti": "",
        "son_haftalik_rapor": "",
        "chat_id": None,
    }


def ayar_kaydet(ayar: dict):
    try:
        with open(PROAKTIF_AYAR, "w", encoding="utf-8") as f:
            json.dump(ayar, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Proaktif ayar kayit hatasi: {e}")


def chat_id_kaydet(chat_id: int):
    """İlk mesajda chat_id'yi kaydet"""
    ayar = ayar_yukle()
    if not ayar.get("chat_id"):
        ayar["chat_id"] = chat_id
        ayar_kaydet(ayar)


# ─────────────────────────────────────────────────────────────
# VERİ OKUMA YARDIMCILARI
# ─────────────────────────────────────────────────────────────


def reward_gecmisi_oku() -> list:
    try:
        if not REWARD_DOSYASI.exists():
            return []
        with open(REWARD_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return []


def egitim_verisi_oku() -> list:
    try:
        kayitlar = []
        if not EGITIM_DOSYASI.exists():
            return []
        with open(EGITIM_DOSYASI, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        kayitlar.append(json.loads(line))
                    except Exception:
                        continue  # Bozuk JSON satiri atla, sonraki satira gec
        return kayitlar
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return []


def model_performans_oku() -> dict:
    try:
        if not MODEL_PERFORMANS_DOSYASI.exists():
            return {}
        with open(MODEL_PERFORMANS_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return {}


# ─────────────────────────────────────────────────────────────
# SABAH ÖZETİ
# ─────────────────────────────────────────────────────────────


def sabah_ozeti_olustur() -> str:
    """
    Günlük sabah özeti metni oluştur.
    Dün ne kadar kullanıldı, başarı oranı ne, eğitim verisi nerede.
    """
    simdi = datetime.now()
    gun_adi = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"][
        simdi.weekday()
    ]
    tarih = simdi.strftime("%d.%m.%Y")

    # Reward geçmişinden dünkü verileri al
    history = reward_gecmisi_oku()
    dun = (simdi - timedelta(days=1)).date()

    dunkü_kayitlar = []
    for r in history:
        try:
            zaman = datetime.fromisoformat(r["zaman"].split(".")[0])
            if zaman.date() == dun:
                dunkü_kayitlar.append(r)
        except Exception as e:
            print("[ProaktifZeka] Hata:", e)

    # Dün istatistikleri
    if dunkü_kayitlar:
        basari = sum(1 for r in dunkü_kayitlar if r.get("basari"))
        toplam_dun = len(dunkü_kayitlar)
        ort_reward = sum(r.get("smoothed", 0.5) for r in dunkü_kayitlar) / toplam_dun
        basari_yuzde = int(basari / toplam_dun * 100)
        dun_ozet = (
            f"Dün {toplam_dun} görev tamamlandı\n"
            f"Başarı oranı: %{basari_yuzde}\n"
            f"Ortalama performans: {ort_reward:.2f}"
        )
    else:
        dun_ozet = "Dün kullanım verisi bulunamadı"

    # Eğitim verisi durumu
    egitim = egitim_verisi_oku()
    egitim_toplam = len(egitim)
    kalan = max(0, 200 - egitim_toplam)

    if egitim_toplam >= 200:
        egitim_not = f"Fine-tuning için hazır! ({egitim_toplam} örnek)"
    else:
        egitim_not = f"{egitim_toplam}/200 örnek ({kalan} kaldı)"

    # Model performans özeti
    model_perf = model_performans_oku()
    en_iyi_model = "Veri yok"
    if model_perf:
        en_iyi = max(model_perf.values(), key=lambda x: x.get("basari_orani", 0))
        en_iyi_model = f"{en_iyi['model']} ({en_iyi['gorev_turu']})"

    mesaj = (
        f"🌅 Günaydın! {gun_adi}, {tarih}\n\n"
        f"📊 Dün:\n{dun_ozet}\n\n"
        f"🎓 Eğitim verisi: {egitim_not}\n\n"
        f"🏆 En iyi model: {en_iyi_model}\n\n"
        f"Bugün nasıl yardımcı olabilirim?"
    )
    return mesaj


# ─────────────────────────────────────────────────────────────
# HAFTALIK RAPOR
# ─────────────────────────────────────────────────────────────


def haftalik_rapor_olustur() -> str:
    """
    Haftalık zayıf alan raporu.
    Hangi görev türlerinde başarı düşük, hangi modeller iyi/kötü.
    """
    simdi = datetime.now()
    bir_hafta_once = simdi - timedelta(days=7)

    # Son 7 günlük reward verisi
    history = reward_gecmisi_oku()
    haftalik = []
    for r in history:
        try:
            zaman = datetime.fromisoformat(r["zaman"].split(".")[0])
            if zaman >= bir_hafta_once:
                haftalik.append(r)
        except Exception as e:
            print("[ProaktifZeka] Hata:", e)

    if not haftalik:
        return "📋 Haftalık Rapor\n\nBu hafta henüz yeterli veri yok."

    toplam = len(haftalik)
    basari = sum(1 for r in haftalik if r.get("basari"))
    basari_yuzde = int(basari / toplam * 100)
    ort_reward = sum(r.get("smoothed", 0.5) for r in haftalik) / toplam

    # Model performans analizi
    model_perf = model_performans_oku()
    zayif_alanlar = []
    guclu_alanlar = []

    for anahtar, p in model_perf.items():
        if p.get("toplam", 0) >= 3:
            oran = p.get("basari_orani", 0)
            bilgi = f"{p['model']} → {p['gorev_turu']} (%{int(oran*100)})"
            if oran < 0.5:
                zayif_alanlar.append((oran, bilgi))
            elif oran >= 0.8:
                guclu_alanlar.append((oran, bilgi))

    zayif_alanlar.sort(key=lambda x: x[0])
    guclu_alanlar.sort(key=lambda x: x[0], reverse=True)

    # Eğitim verisi analizi
    egitim = egitim_verisi_oku()
    bu_hafta_egitim = 0
    tur_dagilim = {}
    for e in egitim:
        try:
            zaman = datetime.fromisoformat(e["zaman"].split(".")[0])
            if zaman >= bir_hafta_once:
                bu_hafta_egitim += 1
                tur = e.get("gorev_turu", "genel")
                tur_dagilim[tur] = tur_dagilim.get(tur, 0) + 1
        except Exception as e:
            print("[ProaktifZeka] Hata:", e)

    # Rapor metni
    rapor = "📋 Haftalık Performans Raporu\n"
    rapor += f"{(simdi - timedelta(days=7)).strftime('%d.%m')} - {simdi.strftime('%d.%m.%Y')}\n\n"

    rapor += "📊 Genel:\n"
    rapor += f"Toplam görev: {toplam}\n"
    rapor += f"Başarı oranı: %{basari_yuzde}\n"
    rapor += f"Ortalama performans: {ort_reward:.2f}\n\n"

    if zayif_alanlar:
        rapor += "⚠️ Zayıf Alanlar:\n"
        for _, bilgi in zayif_alanlar[:3]:
            rapor += f"• {bilgi}\n"
        rapor += "\n"

    if guclu_alanlar:
        rapor += "✅ Güçlü Alanlar:\n"
        for _, bilgi in guclu_alanlar[:3]:
            rapor += f"• {bilgi}\n"
        rapor += "\n"

    rapor += f"🎓 Bu hafta {bu_hafta_egitim} yeni eğitim örneği eklendi\n"

    if tur_dagilim:
        en_cok_tur = max(tur_dagilim.items(), key=lambda x: x[1])
        rapor += f"En çok çalışılan alan: {en_cok_tur[0]} ({en_cok_tur[1]} örnek)\n"

    # ASAMA 8: Hata raporu ekle
    hata_bolumu = haftalik_hata_raporu_olustur()
    if hata_bolumu:
        rapor += f"\n[!] Hata Analizi:\n{hata_bolumu}"

    return rapor


# ─────────────────────────────────────────────────────────────
# FİNE-TUNİNG ÖNERİSİ AÇIKLAMASI
# ─────────────────────────────────────────────────────────────


def finetuning_oneri_acikla() -> str:
    """
    200 örnek dolunca neden fine-tuning önerdiğini açıkla.
    Hangi görev türleri için, ne kadar iyileşme bekleniyor.
    """
    egitim = egitim_verisi_oku()
    toplam = len(egitim)

    if toplam < 200:
        return f"Henüz yeterli veri yok ({toplam}/200)."

    # Görev türü dağılımı
    tur_dagilim = {}
    kalite_toplam = 0
    for e in egitim:
        tur = e.get("gorev_turu", "genel")
        tur_dagilim[tur] = tur_dagilim.get(tur, 0) + 1
        kalite_toplam += e.get("kalite_skoru", 0.5)

    ort_kalite = kalite_toplam / toplam
    en_cok_turler = sorted(tur_dagilim.items(), key=lambda x: x[1], reverse=True)[:3]

    # Model performans durumu
    model_perf = model_performans_oku()
    lokal_basari = 0
    lokal_toplam = 0
    for p in model_perf.values():
        if p.get("model") == "Lokal":
            lokal_basari += p.get("basari_orani", 0) * p.get("toplam", 0)
            lokal_toplam += p.get("toplam", 0)

    lokal_ort = lokal_basari / max(1, lokal_toplam)

    aciklama = (
        f"🎓 Fine-Tuning Önerisi — Neden Şimdi?\n\n"
        f"✅ {toplam} örnek birikmış (eşik: 200)\n"
        f"✅ Ortalama kalite skoru: {ort_kalite:.2f}/1.0\n\n"
        f"📚 En çok eğitim verisi olan alanlar:\n"
    )

    for tur, sayi in en_cok_turler:
        aciklama += f"• {tur}: {sayi} örnek\n"

    aciklama += (
        f"\n🤖 Mevcut lokal model başarı oranı: %{int(lokal_ort*100)}\n"
        f"Fine-tuning sonrası beklenen iyileşme: +%15-25\n\n"
        f"Bu verilerle Llama 3.2 3B modeli özellikle sana göre "
        f"optimize edilecek. Sık kullandığın görev türlerinde "
        f"çok daha iyi cevaplar verecek.\n\n"
        f"Başlatmak ister misin? (evet / hayır)"
    )

    return aciklama


def haftalik_hata_raporu_olustur() -> str:
    """
    ASAMA 8: Son 7 gunde en cok hata yapilan konulari raporla.
    egitim.hata_istatistigi() ile hata_verisi.jsonl okunur.
    """
    hata_dosyasi = BASE_DIR / "hata_verisi.jsonl"
    simdi = datetime.now()
    bir_hafta_once = simdi - timedelta(days=7)

    tur_sayaci = {}
    toplam_hata = 0
    try:
        if not hata_dosyasi.exists():
            return ""
        with open(hata_dosyasi, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        kayit = json.loads(line)
                        zaman = datetime.fromisoformat(kayit["zaman"].split(".")[0])
                        if zaman >= bir_hafta_once:
                            tur = kayit.get("gorev_turu", "genel")
                            tur_sayaci[tur] = tur_sayaci.get(tur, 0) + 1
                            toplam_hata += 1
                    except Exception:
                        continue  # Bozuk/eksik JSON satiri atla
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return ""

    if toplam_hata == 0:
        return ""

    sirali = sorted(tur_sayaci.items(), key=lambda x: x[1], reverse=True)

    rapor = f"Bu hafta {toplam_hata} basarisiz yanit tespit edildi.\n"
    rapor += "En cok hata yapilan konular:\n"
    for tur, sayi in sirali[:5]:
        rapor += f"  {tur}: {sayi} hata\n"

    return rapor


# ─────────────────────────────────────────────────────────────
# SCHEDULER FONKSİYONLARI
# ─────────────────────────────────────────────────────────────


async def sabah_ozeti_gonder(bot, chat_id: int):
    """Sabah özeti gönder (scheduler tarafından çağrılır)"""
    try:
        ayar = ayar_yukle()
        bugun = datetime.now().strftime("%Y-%m-%d")

        # Bugün zaten gönderildiyse tekrar gönderme
        if ayar.get("son_sabah_ozeti") == bugun:
            return

        mesaj = sabah_ozeti_olustur()
        await bot.send_message(chat_id=chat_id, text=mesaj)

        ayar["son_sabah_ozeti"] = bugun
        ayar_kaydet(ayar)
        print(f"[ProaktifZeka] Sabah özeti gönderildi ({bugun})")
    except Exception as e:
        print(f"[ProaktifZeka] Sabah özeti hatası: {e}")


async def haftalik_rapor_gonder(bot, chat_id: int):
    """Haftalık rapor gönder (scheduler tarafından çağrılır)"""
    try:
        ayar = ayar_yukle()
        bu_hafta = datetime.now().strftime("%Y-W%W")

        # Bu hafta zaten gönderildiyse tekrar gönderme
        if ayar.get("son_haftalik_rapor") == bu_hafta:
            return

        rapor = haftalik_rapor_olustur()
        await bot.send_message(chat_id=chat_id, text=rapor)

        ayar["son_haftalik_rapor"] = bu_hafta
        ayar_kaydet(ayar)
        print(f"[ProaktifZeka] Haftalık rapor gönderildi ({bu_hafta})")
    except Exception as e:
        print(f"[ProaktifZeka] Haftalık rapor hatası: {e}")


# ─────────────────────────────────────────────────────────────
# ASAMA 19: GERÇEK PROAKTİFLİK
# ─────────────────────────────────────────────────────────────

import re

import psutil

KULLANICI_LOG_DOSYASI = BASE_DIR / "kullanici_soru_log.jsonl"
PROAKTIF_ONERI_DOSYASI = BASE_DIR / "proaktif_oneri_log.json"

# Günde max kaç proaktif öneri gönderilsin
MAX_GUNLUK_ONERI = 3


# ── Yardımcı: Bugün kaç öneri gönderildi ─────────────────────
def _bugun_oneri_sayisi() -> int:
    try:
        if not PROAKTIF_ONERI_DOSYASI.exists():
            return 0
        with open(PROAKTIF_ONERI_DOSYASI, encoding="utf-8") as f:
            data = json.load(f)
        bugun = datetime.now().strftime("%Y-%m-%d")
        return sum(1 for o in data if o.get("tarih", "")[:10] == bugun)
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return 0


def _oneri_logla(tip: str, mesaj: str):
    try:
        data = []
        if PROAKTIF_ONERI_DOSYASI.exists():
            with open(PROAKTIF_ONERI_DOSYASI, encoding="utf-8") as f:
                data = json.load(f)
        data.append({"tarih": str(datetime.now()), "tip": tip, "mesaj": mesaj[:100]})
        if len(data) > 200:
            data = data[-200:]
        with open(PROAKTIF_ONERI_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)


# ── 1. Soru Kalıbı Kaydı ─────────────────────────────────────


def kullanici_soru_kaydet(soru: str, saat: int = None):
    """
    Her kullanıcı sorusunu saat bilgisiyle kaydet.
    Daha sonra kalıp analizi için kullanılır.
    """
    try:
        if saat is None:
            saat = datetime.now().hour
        # Soruda geçen anahtar kelimeleri çıkar (ilk 5 kelime yeterli)
        kelimeler = re.sub(r"[^\w\s]", " ", soru.lower()).split()[:5]
        kayit = {
            "zaman": str(datetime.now()),
            "saat": saat,
            "kelimeler": kelimeler,
            "uzunluk": len(soru),
        }
        with open(KULLANICI_LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[ProaktifZeka] Soru kayit hatasi: {e}")


def sik_soru_saati_bul() -> int | None:
    """
    Kullanıcının en sık soru sorduğu saati bul.
    En az 5 kayıt varsa çalışır, yoksa None döner.
    """
    try:
        if not KULLANICI_LOG_DOSYASI.exists():
            return None
        saat_sayac = {}
        toplam = 0
        with open(KULLANICI_LOG_DOSYASI, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        kayit = json.loads(line)
                        s = kayit.get("saat", -1)
                        if 0 <= s <= 23:
                            saat_sayac[s] = saat_sayac.get(s, 0) + 1
                            toplam += 1
                    except Exception:
                        continue  # Bozuk JSON satiri atla
        if toplam < 5:
            return None
        return max(saat_sayac, key=saat_sayac.get)
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return None


def sik_konu_bul(son_n: int = 50) -> str | None:
    """
    Son N soruda en sık geçen kelimeyi bul.
    Stopword'leri filtrele.
    """
    STOPWORDS = {
        "ne",
        "nasıl",
        "neden",
        "nerede",
        "kim",
        "hangi",
        "kaç",
        "bir",
        "bu",
        "şu",
        "o",
        "ve",
        "ile",
        "için",
        "de",
        "da",
        "mi",
        "mu",
        "mı",
        "bana",
        "benim",
        "sen",
        "sana",
        "bize",
        "the",
        "a",
        "an",
        "is",
        "are",
        "what",
        "how",
        "why",
    }
    try:
        if not KULLANICI_LOG_DOSYASI.exists():
            return None
        kelime_sayac = {}
        kayitlar = []
        with open(KULLANICI_LOG_DOSYASI, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        kayitlar.append(json.loads(line))
                    except Exception:
                        continue  # Bozuk JSON satiri atla
        # Son N kayıt
        for kayit in kayitlar[-son_n:]:
            for kelime in kayit.get("kelimeler", []):
                if kelime not in STOPWORDS and len(kelime) > 3:
                    kelime_sayac[kelime] = kelime_sayac.get(kelime, 0) + 1
        if not kelime_sayac:
            return None
        en_sik = max(kelime_sayac, key=kelime_sayac.get)
        # En az 3 kez geçmiyorsa önemsiz say
        if kelime_sayac[en_sik] < 3:
            return None
        return en_sik
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return None


# ── 2. Tekrar Eden Hata Tespiti ──────────────────────────────


def tekrar_eden_hata_bul(esik: int = 3) -> str | None:
    """
    Son 7 günde aynı görev türünde 'esik' veya daha fazla
    hata yapılmışsa o görev türünü döner. Yoksa None.
    """
    hata_dosyasi = BASE_DIR / "hata_verisi.jsonl"
    try:
        if not hata_dosyasi.exists():
            return None
        bir_hafta_once = datetime.now() - timedelta(days=7)
        tur_sayac = {}
        with open(hata_dosyasi, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        kayit = json.loads(line)
                        zaman = datetime.fromisoformat(kayit["zaman"].split(".")[0])
                        if zaman >= bir_hafta_once:
                            tur = kayit.get("gorev_turu", "genel")
                            tur_sayac[tur] = tur_sayac.get(tur, 0) + 1
                    except Exception:
                        continue  # Bozuk JSON satiri atla
        if not tur_sayac:
            return None
        en_fazla = max(tur_sayac, key=tur_sayac.get)
        if tur_sayac[en_fazla] >= esik:
            return f"{en_fazla} ({tur_sayac[en_fazla]} hata)"
        return None
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return None


# ── 3. Sistem Kaynağı Kontrolü ───────────────────────────────


def sistem_kaynak_kontrol() -> str | None:
    """
    CPU > %80 veya RAM > %85 ise uyarı mesajı döner.
    Aksi halde None.
    """
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        if cpu > 80:
            return f"CPU kullanımı yüksek (%{cpu:.0f}). Ağır işlemler yavaşlayabilir."
        if ram > 85:
            return f"RAM dolmak üzere (%{ram:.0f}). Sistemi yeniden başlatmayı düşün."
        return None
    except Exception as e:
        print("[ProaktifZeka] Hata:", e)
        return None


# ── 4. Ana Öneri Üretici ─────────────────────────────────────


def proaktif_oneri_uret() -> str | None:
    """
    ASAMA 19: Bağlama göre proaktif öneri üret.
    Günde max MAX_GUNLUK_ONERI öneri gönderilir.

    Öncelik sırası:
      1. Sistem kaynağı uyarısı (kritik)
      2. Tekrar eden hata — "Bu konuyu pratik yapalım mı?"
      3. Sık konu — "Bunu yine sormak ister misin?"
      4. Sık saat — "Şu saatlerde çok soruyorsun"

    Doner: str (öneri mesajı) | None (öneri yok)
    """
    if _bugun_oneri_sayisi() >= MAX_GUNLUK_ONERI:
        return None

    # 1. Sistem kaynağı (her zaman öncelikli)
    kaynak = sistem_kaynak_kontrol()
    if kaynak:
        mesaj = f"[!] Sistem Uyarısı\n{kaynak}"
        _oneri_logla("sistem_kaynak", mesaj)
        return mesaj

    # 2. Tekrar eden hata
    hata_turu = tekrar_eden_hata_bul(esik=3)
    if hata_turu:
        mesaj = (
            f"[!] Dikkat: '{hata_turu}' konusunda bu hafta birkaç kez hata yapıldı.\n"
            f"Bu konuyu birlikte pratik yapalım mı? (evet / hayır)"
        )
        _oneri_logla("tekrar_eden_hata", mesaj)
        return mesaj

    # 3. Sık konu
    konu = sik_konu_bul(son_n=30)
    if konu:
        mesaj = (
            f"Son zamanlarda '{konu}' ile ilgili çok soru soruyorsun.\n"
            f"Bu konuda daha derin bir özet hazırlayayım mı? (evet / hayır)"
        )
        _oneri_logla("sik_konu", mesaj)
        return mesaj

    # 4. Sık saat
    saat = sik_soru_saati_bul()
    if saat is not None:
        simdi_saat = datetime.now().hour
        # Tam o saatteyse hatırlat
        if simdi_saat == saat:
            mesaj = (
                f"Genellikle bu saatlerde ({saat}:00) sorular soruyorsun.\n"
                f"Bugün aklında bir şey var mı?"
            )
            _oneri_logla("sik_saat", mesaj)
            return mesaj

    return None


# ── 5. Scheduler için async gönderici ────────────────────────


async def proaktif_oneri_gonder(bot, chat_id: int):
    """
    ASAMA 19: Proaktif öneriyi üret ve gönder.
    Sadece anlamlı bir öneri varsa mesaj atar.
    """
    try:
        oneri = proaktif_oneri_uret()
        if oneri:
            await bot.send_message(chat_id=chat_id, text=oneri)
            print(f"[ProaktifZeka] Öneri gönderildi: {oneri[:60]}")
        else:
            print("[ProaktifZeka] Öneri yok, mesaj atlandi.")
    except Exception as e:
        print(f"[ProaktifZeka] Öneri gönderme hatasi: {e}")
