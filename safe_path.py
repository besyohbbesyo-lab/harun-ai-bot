# safe_path.py - S3-6: Dosya sistemi jail
# ============================================================
# Path traversal saldirilarina karsi koruma.
# Tum dosya islemleri HARUN_WORKSPACE icinde kalir.
# ============================================================

import os
from pathlib import Path

# Izin verilen calisma alanlari
_BASE_DIR = Path(__file__).parent.resolve()
_MASAUSTU = Path.home() / "Desktop"

HARUN_WORKSPACE = _BASE_DIR  # Ana calisma dizini
IZINLI_DIZINLER = [
    _BASE_DIR,
    _MASAUSTU,
    _BASE_DIR / "memory_db",
    _BASE_DIR / "core",
    _BASE_DIR / "services",
    _BASE_DIR / "handlers",
]


class PathTraversalError(Exception):
    """Guvenlik ihlali: izin verilen dizin disina cikma denemesi."""

    pass


def safe_path(hedef: str, baslangic: Path = None) -> Path:
    """
    Guvenli yol olustur. Path traversal engeller.

    hedef: Kullanicidan gelen dosya yolu (ornek: "../../etc/passwd")
    baslangic: Izin verilen ust dizin (varsayilan: HARUN_WORKSPACE)

    Doner: Guvenli Path nesnesi
    Hata: PathTraversalError eger traversal denemesi varsa
    """
    if baslangic is None:
        baslangic = HARUN_WORKSPACE

    baslangic = baslangic.resolve()

    # Tehlikeli karakter kontrolu
    tehlikeli = ["../", "..\\", "~", "$", "`", "|", ";", "&", "\x00"]
    for t in tehlikeli:
        if t in str(hedef):
            raise PathTraversalError(f"Guvenlik: Tehlikeli karakter tespit edildi: '{t}'")

    # Path olustur ve resolve et
    try:
        tam_yol = (baslangic / hedef).resolve()
    except (ValueError, OSError) as e:
        raise PathTraversalError(f"Gecersiz dosya yolu: {e}")

    # Izin verilen dizinlerde mi kontrol et
    izinli = False
    for dizin in IZINLI_DIZINLER:
        try:
            tam_yol.relative_to(dizin.resolve())
            izinli = True
            break
        except ValueError:
            continue

    if not izinli:
        raise PathTraversalError(
            f"Guvenlik: '{hedef}' izin verilen dizinlerin disinda.\n"
            f"Izinli: {[str(d) for d in IZINLI_DIZINLER]}"
        )

    return tam_yol


def safe_open(hedef: str, mode: str = "r", baslangic: Path = None, **kwargs):
    """
    Guvenli dosya acma. Path traversal engeller.

    Kullanim:
        with safe_open("rapor.txt", "w") as f:
            f.write("merhaba")
    """
    yol = safe_path(hedef, baslangic)

    # Yazma modunda dizin yoksa olustur
    if "w" in mode or "a" in mode:
        yol.parent.mkdir(parents=True, exist_ok=True)

    return open(yol, mode, **kwargs)


def safe_delete(hedef: str, baslangic: Path = None) -> bool:
    """Guvenli dosya silme."""
    yol = safe_path(hedef, baslangic)
    if yol.exists():
        yol.unlink()
        return True
    return False


def dosya_izinli_mi(hedef: str, baslangic: Path = None) -> bool:
    """Path traversal olmadan dosyaya erisim izni var mi?"""
    try:
        safe_path(hedef, baslangic)
        return True
    except PathTraversalError:
        return False
