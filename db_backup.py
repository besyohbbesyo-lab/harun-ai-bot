# db_backup.py - S3-3: ChromaDB yedekleme + WAL modu
# ============================================================
# Gece otomatik yedekleme, 30 gun rotasyon
# ============================================================

import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from bot_config import CFG

    _backup_cfg = CFG.get("backup", {})
except Exception:
    _backup_cfg = {}

BASE_DIR = Path(__file__).parent.resolve()
DB_DIR = BASE_DIR / "memory_db"
BACKUP_DIR = BASE_DIR / _backup_cfg.get("dizin", "backups")
MAX_YEDEK_GUN = int(_backup_cfg.get("rotasyon_gun", 30))
YEDEK_SAATI = int(_backup_cfg.get("saat", 3))  # Gece 3'te


def yedek_al(hedef_dizin: Path = None) -> str:
    """ChromaDB veritabaninin yedegini al."""
    if hedef_dizin is None:
        hedef_dizin = BACKUP_DIR

    hedef_dizin.mkdir(parents=True, exist_ok=True)

    tarih = datetime.now().strftime("%Y%m%d_%H%M%S")
    yedek_adi = f"memory_db_backup_{tarih}"
    yedek_yolu = hedef_dizin / yedek_adi

    if not DB_DIR.exists():
        return f"[Backup] memory_db dizini bulunamadi: {DB_DIR}"

    try:
        shutil.copytree(DB_DIR, yedek_yolu)
        boyut_mb = sum(f.stat().st_size for f in yedek_yolu.rglob("*") if f.is_file()) / (
            1024 * 1024
        )
        mesaj = f"[Backup] Yedek alindi: {yedek_adi} ({boyut_mb:.1f} MB)"
        print(mesaj)
        return mesaj
    except Exception as e:
        mesaj = f"[Backup] Yedekleme hatasi: {e}"
        print(mesaj)
        return mesaj


def eski_yedekleri_temizle(hedef_dizin: Path = None, max_gun: int = None):
    """Belirli gunden eski yedekleri sil."""
    if hedef_dizin is None:
        hedef_dizin = BACKUP_DIR
    if max_gun is None:
        max_gun = MAX_YEDEK_GUN

    if not hedef_dizin.exists():
        return

    esik = datetime.now() - timedelta(days=max_gun)
    silinen = 0

    for item in hedef_dizin.iterdir():
        if item.is_dir() and item.name.startswith("memory_db_backup_"):
            try:
                # Tarih parse et
                tarih_str = item.name.replace("memory_db_backup_", "")[:15]
                tarih = datetime.strptime(tarih_str, "%Y%m%d_%H%M%S")
                if tarih < esik:
                    shutil.rmtree(item)
                    silinen += 1
            except (ValueError, OSError):
                continue

    if silinen > 0:
        print(f"[Backup] {silinen} eski yedek temizlendi (>{max_gun} gun)")


def json_dosyalarini_yedekle(hedef_dizin: Path = None):
    """ETM ve token_budget JSON dosyalarini da yedekle."""
    if hedef_dizin is None:
        hedef_dizin = BACKUP_DIR

    hedef_dizin.mkdir(parents=True, exist_ok=True)
    tarih = datetime.now().strftime("%Y%m%d")

    for dosya_adi in ["etm_buffer.json", "token_budget_log.json"]:
        kaynak = BASE_DIR / dosya_adi
        if kaynak.exists():
            hedef = hedef_dizin / f"{dosya_adi}.{tarih}.bak"
            try:
                shutil.copy2(kaynak, hedef)
            except Exception:
                pass


def yedek_listesi(hedef_dizin: Path = None) -> list:
    """Mevcut yedeklerin listesi."""
    if hedef_dizin is None:
        hedef_dizin = BACKUP_DIR
    if not hedef_dizin.exists():
        return []
    yedekler = []
    for item in sorted(hedef_dizin.iterdir(), reverse=True):
        if item.is_dir() and item.name.startswith("memory_db_backup_"):
            boyut = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            yedekler.append(
                {
                    "isim": item.name,
                    "boyut_mb": round(boyut / (1024 * 1024), 1),
                    "tarih": item.name.replace("memory_db_backup_", "")[:15],
                }
            )
    return yedekler


def durum_ozeti() -> str:
    """Yedekleme durumu."""
    yedekler = yedek_listesi()
    if not yedekler:
        return "[Backup] Henuz yedek alinmamis"
    son = yedekler[0]
    return (
        f"[Backup] {len(yedekler)} yedek mevcut\n"
        f"  Son: {son['isim']} ({son['boyut_mb']} MB)\n"
        f"  Rotasyon: {MAX_YEDEK_GUN} gun"
    )


async def periyodik_yedek(context=None):
    """Scheduler'dan cagrilan periyodik yedekleme."""
    saat = datetime.now().hour
    if saat == YEDEK_SAATI:
        yedek_al()
        json_dosyalarini_yedekle()
        eski_yedekleri_temizle()
