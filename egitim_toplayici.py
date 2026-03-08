# egitim_toplayici.py - FIXED VERSION
import hashlib
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
EGITIM_DOSYASI = BASE_DIR / "egitim_verisi.jsonl"
HATA_DOSYASI = BASE_DIR / "hata_verisi.jsonl"


class EgitimToplayici:
    def __init__(self):
        self.egitim_dosyasi = EGITIM_DOSYASI
        self.hata_dosyasi = HATA_DOSYASI
        self.base_dir = BASE_DIR

    def _say(self):
        if not self.egitim_dosyasi.exists():
            return 0
        with self.egitim_dosyasi.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def istatistik(self):
        return f"Egitim kayit sayisi: {self._say()}"

    def hata_istatistigi(self):
        sayac = {}
        if not self.hata_dosyasi.exists():
            return {}
        with self.hata_dosyasi.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        kayit = json.loads(line)
                        tur = kayit.get("gorev_turu", "genel")
                        sayac[tur] = sayac.get(tur, 0) + 1
                    except:
                        pass
        return sayac

    def rapor_dict(self, son_n=50):
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "files": {
                "egitim_dosyasi": str(self.egitim_dosyasi),
                "hata_dosyasi": str(self.hata_dosyasi),
            },
            "counts": {
                "egitim_kaydi": self._say(),
                "hata_kaydi": len(self.hata_istatistigi()),
            },
            "summary_text": {
                "egitim": self.istatistik(),
                "redler": self.hata_istatistigi(),
            },
        }

    def rapor_kaydet(self, masaustu=True, son_n=50):
        rapor = self.rapor_dict(son_n)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"egitim_report_{ts}.json"
        out_dir = (Path.home() / "Desktop") if masaustu else self.base_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / fname
        out_path.write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_path


egitim = EgitimToplayici()
