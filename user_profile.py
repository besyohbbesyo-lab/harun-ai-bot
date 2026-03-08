# user_profile.py - Kullanici Profil ve Tercih Sistemi
# Aşama 2: Kullanıcı tercihleri kalıcı olarak user_profile.json'da tutulur

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
PROFIL_DOSYASI = BASE_DIR / "user_profile.json"

VARSAYILAN_PROFIL = {
    "cevap_uzunlugu": "orta",  # kisa / orta / uzun
    "ton": "samimi",  # samimi / resmi
    "dil": "tr",
    "sesli_cevap": False,
    "hafiza_destegi": True,
    "olusturma_tarihi": "",
    "son_guncelleme": "",
    "toplam_mesaj": 0,
}


def profil_yukle(user_id: int) -> dict:
    """Kullanicinin profilini yukle, yoksa varsayilan olustur"""
    try:
        if PROFIL_DOSYASI.exists():
            with open(PROFIL_DOSYASI, encoding="utf-8") as f:
                data = json.load(f)
            profil = data.get(str(user_id))
            if profil:
                # Eksik alanlari varsayilanlarla tamamla
                for k, v in VARSAYILAN_PROFIL.items():
                    if k not in profil:
                        profil[k] = v
                return profil
    except Exception as e:
        print(f"Profil yukle hatasi: {e}")

    # Yeni profil olustur
    yeni = VARSAYILAN_PROFIL.copy()
    yeni["olusturma_tarihi"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return yeni


def profil_kaydet(user_id: int, profil: dict):
    """Kullanici profilini kaydet"""
    try:
        data = {}
        if PROFIL_DOSYASI.exists():
            with open(PROFIL_DOSYASI, encoding="utf-8") as f:
                data = json.load(f)
        profil["son_guncelleme"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        data[str(user_id)] = profil
        with open(PROFIL_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Profil kaydet hatasi: {e}")
        return False


def tercih_guncelle(user_id: int, anahtar: str, deger) -> dict:
    """Tek bir tercih alanini guncelle ve geri domdur"""
    profil = profil_yukle(user_id)
    profil[anahtar] = deger
    profil_kaydet(user_id, profil)
    return profil


def mesaj_sayaci_artir(user_id: int):
    """Toplam mesaj sayacini 1 artir"""
    try:
        profil = profil_yukle(user_id)
        profil["toplam_mesaj"] = profil.get("toplam_mesaj", 0) + 1
        profil_kaydet(user_id, profil)
    except Exception:
        pass


def sistem_prompt_olustur(user_id: int) -> str:
    """
    Kullanicinin tercihlerine gore sistem promptu olustur.
    Bu prompt ask_ai'ya eklenecek.
    """
    profil = profil_yukle(user_id)

    uzunluk_talimat = {
        "kisa": "Cevaplarini mumkun oldugunca kisa ve oz tut, 2-3 cumle yeterli.",
        "orta": "Cevaplarini dengeli tut, ne cok kisa ne cok uzun.",
        "uzun": "Cevaplarini detayli ve kapsamli yaz, gerekirse ornekler ekle.",
    }.get(profil.get("cevap_uzunlugu", "orta"), "")

    ton_talimat = {
        "samimi": "Samimi, arkadas gibi bir dil kullan.",
        "resmi": "Resmi ve profesyonel bir dil kullan.",
    }.get(profil.get("ton", "samimi"), "")

    return f"{uzunluk_talimat} {ton_talimat}".strip()


def profil_ozeti(user_id: int) -> str:
    """Profil ozetini insan okunabilir formatta domdur"""
    profil = profil_yukle(user_id)
    return (
        f"Profil Ayarlarin:\n"
        f"Cevap uzunlugu: {profil.get('cevap_uzunlugu', 'orta')}\n"
        f"Ton: {profil.get('ton', 'samimi')}\n"
        f"Hafiza destegi: {'Acik' if profil.get('hafiza_destegi', True) else 'Kapali'}\n"
        f"Toplam mesaj: {profil.get('toplam_mesaj', 0)}\n"
        f"Son guncelleme: {profil.get('son_guncelleme', 'Henuz yok')}"
    )
