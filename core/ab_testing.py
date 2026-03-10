# core/ab_testing.py — S7-5: A/B Testing
# Farkli model/prompt versiyonlarini karsilastirma sistemi
# ============================================================

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.config import log_yaz

_AB_PERSISTENCE_YOLU: Path | None = None
_AB_OTOMATIK_KAYDET = False


# ── Varyant Tanimi ────────────────────────────────────────────


@dataclass
class Varyant:
    """A/B test varyanti."""

    ad: str
    agirlik: float = 0.5  # 0.0 - 1.0 arasi dagitim agirligi
    konfig: dict = field(default_factory=dict)  # model, temp, prompt vb
    aktif: bool = True


@dataclass
class VaryantSonuc:
    """Bir varyant denemesinin sonucu."""

    varyant_adi: str
    kullanici_id: str
    basarili: bool
    sure_ms: float
    metadata: dict = field(default_factory=dict)
    zaman: float = field(default_factory=time.time)


# ── A/B Test Motoru ───────────────────────────────────────────


def ab_persistence_ayarla(dosya_yolu: str | Path, otomatik_kaydet: bool = True):
    """A/B test persistence ayarlarini yapilandir."""
    global _AB_PERSISTENCE_YOLU, _AB_OTOMATIK_KAYDET
    _AB_PERSISTENCE_YOLU = Path(dosya_yolu)
    _AB_OTOMATIK_KAYDET = otomatik_kaydet


def _otomatik_kaydet_yap():
    """Persistence aktifse global testleri diske yaz."""
    if not _AB_OTOMATIK_KAYDET or _AB_PERSISTENCE_YOLU is None:
        return
    try:
        tum_testleri_kaydet(_AB_PERSISTENCE_YOLU)
    except Exception as e:
        log_yaz(f"[AB] Otomatik kayit hatasi: {e}", "ERROR")


def tum_testleri_yuklemeyi_dene(dosya_yolu: str | Path | None = None) -> bool:
    """Kayitli A/B test verisini varsa yukle."""
    yol = Path(dosya_yolu) if dosya_yolu is not None else _AB_PERSISTENCE_YOLU
    if yol is None or not yol.exists():
        return False
    try:
        tum_testleri_yukle(yol)
        log_yaz(f"[AB] Tum testler yuklendi <- {yol}", "INFO")
        return True
    except Exception as e:
        log_yaz(f"[AB] Yukleme hatasi: {e}", "ERROR")
        return False


class ABTestMotoru:
    """
    Kullanici bazli deterministik A/B test sistemi.

    - Ayni kullanici her zaman ayni varyanti alir (hash bazli)
    - Agirlikli dagitim destekler (%70 A / %30 B)
    - Sonuclari toplar ve istatistik uretir
    """

    def __init__(self, test_adi: str):
        self.test_adi = test_adi
        self._varyantlar: list[Varyant] = []
        self._sonuclar: list[VaryantSonuc] = []
        self._kullanici_atama: dict[str, str] = {}  # uid → varyant_adi

    def varyant_ekle(self, varyant: Varyant):
        self._varyantlar.append(varyant)
        _otomatik_kaydet_yap()
        log_yaz(
            f"[AB] '{self.test_adi}' → varyant eklendi: "
            f"{varyant.ad} (agirlik={varyant.agirlik})",
            "INFO",
        )

    def varyant_sec(self, kullanici_id: str | int) -> Varyant:
        """
        Kullanici icin deterministik varyant sec.

        Ayni kullanici_id her zaman ayni varyanti alir.
        Hash bazli — random degil, tutarli.
        """
        uid = str(kullanici_id)

        # Onceden atanmissa ayniyi don
        if uid in self._kullanici_atama:
            atanan = self._kullanici_atama[uid]
            for v in self._varyantlar:
                if v.ad == atanan and v.aktif:
                    return v

        aktif = [v for v in self._varyantlar if v.aktif]
        if not aktif:
            raise ValueError(f"'{self.test_adi}' testinde aktif varyant yok")

        # Hash bazli deterministik secim
        hash_deger = int(hashlib.md5(f"{self.test_adi}:{uid}".encode()).hexdigest(), 16)
        norm = (hash_deger % 10000) / 10000.0  # 0.0 - 1.0

        # Agirlikli secim
        toplam_agirlik = sum(v.agirlik for v in aktif)
        esik = 0.0
        for v in aktif:
            esik += v.agirlik / toplam_agirlik
            if norm < esik:
                self._kullanici_atama[uid] = v.ad
                _otomatik_kaydet_yap()
                return v

        # Fallback: son varyant
        secilen = aktif[-1]
        self._kullanici_atama[uid] = secilen.ad
        _otomatik_kaydet_yap()
        return secilen

    def sonuc_kaydet(self, sonuc: VaryantSonuc):
        """Test sonucunu kaydet."""
        self._sonuclar.append(sonuc)
        _otomatik_kaydet_yap()

    def istatistik(self) -> dict:
        """
        Varyant bazli istatistik uret.
        """
        ist: dict[str, Any] = {
            "test_adi": self.test_adi,
            "toplam_sonuc": len(self._sonuclar),
            "varyantlar": {},
        }

        for varyant in self._varyantlar:
            vad = varyant.ad
            v_sonuclar = [s for s in self._sonuclar if s.varyant_adi == vad]
            if not v_sonuclar:
                ist["varyantlar"][vad] = {
                    "toplam": 0,
                    "basarili": 0,
                    "basari_orani": 0.0,
                    "ort_sure_ms": 0.0,
                }
                continue

            basarili = sum(1 for s in v_sonuclar if s.basarili)
            ist["varyantlar"][vad] = {
                "toplam": len(v_sonuclar),
                "basarili": basarili,
                "basari_orani": basarili / len(v_sonuclar),
                "ort_sure_ms": sum(s.sure_ms for s in v_sonuclar) / len(v_sonuclar),
            }

        return ist

    def kazanan(self) -> Varyant | None:
        """
        En yuksek basari oranli varyanti doner.
        Yeterli veri yoksa None.
        """
        MIN_ORNEK = 10
        ist = self.istatistik()
        en_iyi: tuple[float, Varyant | None] = (0.0, None)

        for varyant in self._varyantlar:
            v_ist = ist["varyantlar"].get(varyant.ad, {})
            if v_ist.get("toplam", 0) < MIN_ORNEK:
                continue
            oran = v_ist.get("basari_orani", 0.0)
            if oran > en_iyi[0]:
                en_iyi = (oran, varyant)

        return en_iyi[1]

    def varyant_devre_disi_birak(self, varyant_adi: str):
        """Varyanti devre disi birak (kazanan belirlendikten sonra)."""
        for v in self._varyantlar:
            if v.ad == varyant_adi:
                v.aktif = False
                _otomatik_kaydet_yap()
                log_yaz(f"[AB] Varyant devre disi: {varyant_adi}", "INFO")

    def to_dict(self) -> dict[str, Any]:
        """Motor durumunu JSON-uyumlu dict'e donustur."""
        return {
            "test_adi": self.test_adi,
            "varyantlar": [asdict(v) for v in self._varyantlar],
            "sonuclar": [asdict(s) for s in self._sonuclar],
            "kullanici_atama": dict(self._kullanici_atama),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ABTestMotoru:
        """Dict'ten motoru yeniden olustur."""
        if not isinstance(data, dict):
            raise ValueError("AB test verisi dict olmali")
        test_adi = data.get("test_adi")
        if not test_adi:
            raise ValueError("AB test verisinde 'test_adi' zorunlu")

        motor = cls(str(test_adi))
        motor._varyantlar = [Varyant(**item) for item in data.get("varyantlar", [])]
        motor._sonuclar = [VaryantSonuc(**item) for item in data.get("sonuclar", [])]
        motor._kullanici_atama = {
            str(uid): str(varyant_adi)
            for uid, varyant_adi in data.get("kullanici_atama", {}).items()
        }
        return motor

    def kaydet(self, dosya_yolu: str | Path):
        """Motoru diske JSON olarak kaydet."""
        yol = Path(dosya_yolu)
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log_yaz(f"[AB] Test kaydedildi: {self.test_adi} -> {yol}", "INFO")

    @classmethod
    def yukle(cls, dosya_yolu: str | Path) -> ABTestMotoru:
        """Diskten JSON okuyup motoru geri yukle."""
        yol = Path(dosya_yolu)
        veri = json.loads(yol.read_text(encoding="utf-8"))
        return cls.from_dict(veri)


# ── Global Test Kayitcisi ─────────────────────────────────────
_testler: dict[str, ABTestMotoru] = {}


def ab_test_al_veya_olustur(test_adi: str) -> ABTestMotoru:
    """Global test motorunu al veya olustur."""
    if test_adi not in _testler:
        _testler[test_adi] = ABTestMotoru(test_adi)
        _otomatik_kaydet_yap()
    return _testler[test_adi]


# Geriye donuk uyumluluk: testler ve eski importlar bu ismi kullaniyor.
def test_al_veya_olustur(test_adi: str) -> ABTestMotoru:
    return ab_test_al_veya_olustur(test_adi)


# Pytest bu yardimci fonksiyonu test olarak toplamasin.
setattr(test_al_veya_olustur, "__test__", False)


def kullaniciyi_varyanta_zorla(test_adi: str, kullanici_id: str | int, varyant_adi: str) -> None:
    """Belirli bir kullaniciyi secilen varyanta zorla."""
    motor = ab_test_al_veya_olustur(test_adi)
    uid = str(kullanici_id)

    hedef = None
    for varyant in motor._varyantlar:
        if varyant.ad == varyant_adi:
            hedef = varyant
            break

    if hedef is None:
        raise ValueError(f"'{test_adi}' testinde '{varyant_adi}' varyanti yok")
    if not hedef.aktif:
        raise ValueError(f"'{test_adi}' testinde '{varyant_adi}' varyanti aktif degil")

    motor._kullanici_atama[uid] = varyant_adi
    _otomatik_kaydet_yap()
    log_yaz(f"[AB] Kullanici zorlandi: test={test_adi} uid={uid} varyant={varyant_adi}", "INFO")


def tum_testler_istatistik() -> dict:
    """Tum aktif testlerin istatistiklerini doner."""
    return {ad: motor.istatistik() for ad, motor in _testler.items()}


def tum_testleri_kaydet(dosya_yolu: str | Path):
    """Tum global A/B test motorlarini tek JSON dosyasina kaydet."""
    yol = Path(dosya_yolu)
    yol.parent.mkdir(parents=True, exist_ok=True)
    veri = {ad: motor.to_dict() for ad, motor in _testler.items()}
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    log_yaz(f"[AB] Tum testler kaydedildi -> {yol}", "INFO")


def tum_testleri_yukle(dosya_yolu: str | Path):
    """Kaydedilmis global A/B test motorlarini geri yukle."""
    yol = Path(dosya_yolu)
    veri = json.loads(yol.read_text(encoding="utf-8"))
    if not isinstance(veri, dict):
        raise ValueError("Global AB test verisi dict olmali")

    _testler.clear()
    for ad, motor_veri in veri.items():
        motor = ABTestMotoru.from_dict(motor_veri)
        _testler[str(ad)] = motor


def testleri_sifirla():
    """Testler veya yeniden baslatma senaryolari icin global kayitciyi temizle."""
    _testler.clear()
