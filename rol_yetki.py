# rol_yetki.py - S3-2: Rol bazli yetkilendirme
# ============================================================
# 3 rol seviyesi: admin, user, readonly
#   admin:    Tum komutlar (PC kontrol, guvenlik, egitim, vs.)
#   user:     Sohbet, arama, PDF, kod, sunum, word, plan
#   readonly: Sadece /status, /help, /start ve okuma
#
# Ayar:
#   config.yaml > roller bölümüne kullanıcı ekle
#   ya da .env'e ROL_ADMIN=123456,789012 seklinde yaz
# ============================================================

import os
from typing import Dict, Optional, Set

try:
    from bot_config import CFG

    _rol_cfg = CFG.get("roller", {})
except Exception:
    _rol_cfg = {}

# Roller ve izinler
ROLLER = {
    "admin": {
        "aciklama": "Tam yetki — tum komutlar",
        "komutlar": "*",  # Hepsi
    },
    "user": {
        "aciklama": "Normal kullanici — sohbet ve araclar",
        "komutlar": {
            "start",
            "help",
            "status",
            "chat",
            "ara",
            "pdf",
            "kod",
            "sunum",
            "word",
            "plan",
            "hafiza",
            "hatirlat",
            "gonder",
        },
    },
    "readonly": {
        "aciklama": "Salt okunur — sadece goruntuleyebilir",
        "komutlar": {"start", "help", "status"},
    },
}

# Kullanici-rol eslestirmesi
_kullanici_rolleri: dict[int, str] = {}


def _rolleri_yukle():
    """Config ve env'den rolleri yukle."""
    global _kullanici_rolleri
    _kullanici_rolleri = {}

    # 1. Config'den yukle
    for rol_adi in ("admin", "user", "readonly"):
        kullanicilar = _rol_cfg.get(rol_adi, [])
        if isinstance(kullanicilar, (list, tuple)):
            for uid in kullanicilar:
                try:
                    _kullanici_rolleri[int(uid)] = rol_adi
                except (ValueError, TypeError):
                    pass

    # 2. Env'den yukle (config'in ustune yazar)
    for rol_adi in ("admin", "user", "readonly"):
        env_key = f"ROL_{rol_adi.upper()}"
        env_val = os.getenv(env_key, "").strip()
        if env_val:
            for uid_str in env_val.split(","):
                uid_str = uid_str.strip()
                if uid_str:
                    try:
                        _kullanici_rolleri[int(uid_str)] = rol_adi
                    except ValueError:
                        pass

    if _kullanici_rolleri:
        print(f"[Roller] {len(_kullanici_rolleri)} kullanici rol atandi")


# Baslangicta yukle
_rolleri_yukle()


def rol_al(user_id: int) -> str:
    """Kullanicinin rolunu dondur. Tanimli degilse 'admin' (geriye uyumluluk)."""
    return _kullanici_rolleri.get(user_id, "admin")


def komut_izinli_mi(user_id: int, komut: str) -> bool:
    """Kullanicinin bu komutu calistirma yetkisi var mi?"""
    rol = rol_al(user_id)
    rol_bilgi = ROLLER.get(rol, ROLLER["readonly"])
    izinli_komutlar = rol_bilgi["komutlar"]  # type: ignore[index]

    # Admin her seyi yapabilir
    if izinli_komutlar == "*":
        return True

    # Mesaj handler'lar icin — sohbet izni
    if komut in ("message", "sohbet", "sesli_mesaj"):
        return rol in ("admin", "user")

    return komut in izinli_komutlar


def rol_ata(user_id: int, rol: str) -> bool:
    """Kullaniciya rol ata (calisma zamaninda)."""
    if rol not in ROLLER:
        return False
    _kullanici_rolleri[user_id] = rol
    return True


def rol_kaldir(user_id: int) -> bool:
    """Kullanicinin rolunu kaldir."""
    if user_id in _kullanici_rolleri:
        del _kullanici_rolleri[user_id]
        return True
    return False


def durum_ozeti() -> str:
    """Rol durumu ozeti."""
    if not _kullanici_rolleri:
        return "[Roller] Rol sistemi aktif (tum yetkili kullanicilar admin)"

    satirlar = ["[Roller]"]
    for rol_adi in ("admin", "user", "readonly"):
        kullanicilar = [uid for uid, r in _kullanici_rolleri.items() if r == rol_adi]
        if kullanicilar:
            satirlar.append(f"  {rol_adi}: {len(kullanicilar)} kullanici")
    return "\n".join(satirlar)
