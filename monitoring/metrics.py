# monitoring/metrics.py — Bot metrik takibi
# Master Plan S3-3: Prometheus + dahili sayaçlar
# ============================================================
# Kullanim:
#   from monitoring.metrics import metrics
#
#   metrics.mesaj_sayac()
#   metrics.yanit_sure_kaydet(1.23)
#   metrics.hata_sayac("Groq")
#   print(metrics.ozet())
# ============================================================

import threading
import time
from collections import defaultdict, deque
from datetime import datetime

# Prometheus — sadece açıkça istenirse yükle, import sırasında değil
_PROM = False
_msg_counter = None
_error_counter = None
_latency_hist = None
_active_users = None
_token_gauge = None


def _prom_yukle():
    """Prometheus'u lazy load et — başlangıçta yükleme."""
    global _PROM, _msg_counter, _error_counter, _latency_hist, _active_users, _token_gauge
    if _PROM:
        return True
    try:
        from prometheus_client import Counter, Gauge, Histogram

        _msg_counter = Counter("harun_messages_total", "Toplam mesaj", ["gorev_turu"])
        _error_counter = Counter("harun_errors_total", "Toplam hata", ["provider"])
        _latency_hist = Histogram(
            "harun_response_latency_seconds",
            "Yanıt süresi",
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )
        _active_users = Gauge("harun_active_users", "Aktif kullanıcı")
        _token_gauge = Gauge("harun_daily_tokens_used", "Token kullanım")
        _PROM = True
        return True
    except Exception:
        return False


# ── BotMetrics sınıfı ────────────────────────────────────────


class BotMetrics:
    """
    Bot performans ve hata metriklerini toplar.
    Prometheus varsa oraya da gönderir, yoksa dahili tutar.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Dahili sayaçlar
        self._mesaj_sayisi = 0
        self._hata_sayisi = defaultdict(int)  # {provider: count}
        self._gorev_sayisi = defaultdict(int)  # {gorev_turu: count}
        self._yanit_sureleri = deque(maxlen=1000)  # son 1000 yanıt
        self._token_kullanim = 0
        self._basari_sayisi = 0
        self._basarisiz_sayisi = 0

        # Aktif kullanıcı takibi (son 5dk)
        self._aktif_kullanicilar = {}  # {user_id: timestamp}
        self._baslangic = datetime.now()

    # ── Sayaçlar ────────────────────────────────────────────

    def mesaj_sayac(self, gorev_turu: str = "genel", user_id: int = None):
        """Gelen mesajı say."""
        with self._lock:
            self._mesaj_sayisi += 1
            self._gorev_sayisi[gorev_turu] += 1
            if user_id:
                self._aktif_kullanicilar[user_id] = time.time()

        if _PROM:
            try:
                _msg_counter.labels(gorev_turu=gorev_turu).inc()
            except Exception:
                pass

    def hata_sayac(self, provider: str = "genel"):
        """Hata sayısını artır."""
        with self._lock:
            self._hata_sayisi[provider] += 1
            self._basarisiz_sayisi += 1

        if _PROM:
            try:
                _error_counter.labels(provider=provider).inc()
            except Exception:
                pass

    def basari_kaydet(self):
        """Başarılı yanıt sayısını artır."""
        with self._lock:
            self._basari_sayisi += 1

    def yanit_sure_kaydet(self, sure_sn: float, gorev_turu: str = "genel"):
        """Yanıt süresini kaydet (saniye cinsinden)."""
        with self._lock:
            self._yanit_sureleri.append(
                {"sure": sure_sn, "gorev": gorev_turu, "zaman": time.time()}
            )

        if _PROM:
            try:
                _latency_hist.observe(sure_sn)
            except Exception:
                pass

    def token_kaydet(self, miktar: int):
        """Kullanılan token miktarını güncelle."""
        with self._lock:
            self._token_kullanim += miktar

        if _PROM:
            try:
                _token_gauge.set(self._token_kullanim)
            except Exception:
                pass

    # ── Hesaplamalar ────────────────────────────────────────

    def aktif_kullanici_sayisi(self, pencere_sn: int = 300) -> int:
        """Son `pencere_sn` saniyede aktif kullanıcı sayısı."""
        esik = time.time() - pencere_sn
        with self._lock:
            aktif = sum(1 for t in self._aktif_kullanicilar.values() if t > esik)

        if _PROM:
            try:
                _active_users.set(aktif)
            except Exception:
                pass

        return aktif

    def ortalama_yanit_suresi(self) -> float:
        """Son 1000 yanıtın ortalama süresi (saniye)."""
        with self._lock:
            if not self._yanit_sureleri:
                return 0.0
            return sum(r["sure"] for r in self._yanit_sureleri) / len(self._yanit_sureleri)

    def basari_orani(self) -> float:
        """Başarı oranı 0.0-1.0 arasında."""
        with self._lock:
            toplam = self._basari_sayisi + self._basarisiz_sayisi
            if toplam == 0:
                return 1.0
            return self._basari_sayisi / toplam

    def uptime_sn(self) -> float:
        """Bot çalışma süresi saniye cinsinden."""
        return (datetime.now() - self._baslangic).total_seconds()

    # ── Raporlama ───────────────────────────────────────────

    def ozet(self) -> dict:
        """Tam metrik özeti dict olarak."""
        with self._lock:
            # Lock icinde metod cagirma — deadlock onlemek icin inline hesapla
            toplam = self._basari_sayisi + self._basarisiz_sayisi
            basari = self._basari_sayisi / toplam if toplam > 0 else 1.0
            ort_sure = (
                sum(r["sure"] for r in self._yanit_sureleri) / len(self._yanit_sureleri)
                if self._yanit_sureleri
                else 0.0
            )
            esik = time.time() - 300
            aktif = sum(1 for t in self._aktif_kullanicilar.values() if t > esik)
            return {
                "mesaj_sayisi": self._mesaj_sayisi,
                "basari_sayisi": self._basari_sayisi,
                "basarisiz_sayisi": self._basarisiz_sayisi,
                "basari_orani": round(basari, 3),
                "ort_yanit_suresi_sn": round(ort_sure, 2),
                "aktif_kullanici": aktif,
                "token_kullanim": self._token_kullanim,
                "gorev_dagilimi": dict(self._gorev_sayisi),
                "hata_dagilimi": dict(self._hata_sayisi),
                "uptime_sn": round(self.uptime_sn(), 0),
                "prometheus": _PROM,
            }

    def ozet_metni(self) -> str:
        """Telegram /status için okunabilir metrik özeti."""
        o = self.ozet()
        saat = int(o["uptime_sn"] // 3600)
        dakika = int((o["uptime_sn"] % 3600) // 60)

        satirlar = [
            "📊 *Bot Metrikleri*",
            f"Toplam mesaj: `{o['mesaj_sayisi']}`",
            f"Başarı oranı: `%{o['basari_orani']*100:.1f}`",
            f"Ort. yanıt: `{o['ort_yanit_suresi_sn']}s`",
            f"Aktif kullanıcı: `{o['aktif_kullanici']}` (son 5dk)",
            f"Token kullanım: `{o['token_kullanim']:,}`",
            f"Uptime: `{saat}s {dakika}dk`",
        ]

        if o["hata_dagilimi"]:
            satirlar.append("\n*Hata Dağılımı:*")
            for prov, cnt in sorted(o["hata_dagilimi"].items(), key=lambda x: x[1], reverse=True)[
                :3
            ]:
                satirlar.append(f"  {prov}: `{cnt}`")

        if _PROM:
            satirlar.append("\n✅ Prometheus aktif")
        else:
            satirlar.append("\nℹ️ Prometheus devre dışı")

        return "\n".join(satirlar)

    def sifirla(self):
        """Tüm sayaçları sıfırla (test için)."""
        with self._lock:
            self._mesaj_sayisi = 0
            self._hata_sayisi = defaultdict(int)
            self._gorev_sayisi = defaultdict(int)
            self._yanit_sureleri = deque(maxlen=1000)
            self._token_kullanim = 0
            self._basari_sayisi = 0
            self._basarisiz_sayisi = 0

    # ── Prometheus sunucusu ─────────────────────────────────

    def prometheus_baslat(self, port: int = 8001):
        """Prometheus metrics endpoint'i başlat."""
        if not _PROM:
            print("[Metrics] prometheus_client yüklü değil, başlatılamadı")
            return False
        try:
            from prometheus_client import start_http_server

            start_http_server(port)
            print(f"[Metrics] Prometheus endpoint: http://localhost:{port}/metrics")
            return True
        except Exception as e:
            print(f"[Metrics] Prometheus başlatma hatası: {e}")
            return False


# ── Global singleton ─────────────────────────────────────────
metrics = BotMetrics()
