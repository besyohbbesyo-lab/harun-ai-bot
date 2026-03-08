# dashboard.py - Aşama 4: Tool Intelligence + Model Performans Paneli
import datetime
import json
from pathlib import Path

import psutil
from flask import Flask, jsonify, render_template_string

try:
    from memory_plugin import MemorySystem

    memory = MemorySystem()
    HAFIZA_AKTIF = True
except Exception:
    HAFIZA_AKTIF = False

try:
    from strategy_manager import StrategyManager

    strategy_mgr = StrategyManager()
    STRATEJI_AKTIF = True
except Exception:
    STRATEJI_AKTIF = False

try:
    from api_rotator import rotator

    ROTATOR_AKTIF = True
except Exception:
    ROTATOR_AKTIF = False

app = Flask(__name__)
BASE_DIR = Path(__file__).parent.resolve()
LOG_DOSYASI = BASE_DIR / "bot_log.txt"
EGITIM_DOSYASI = BASE_DIR / "egitim_verisi.jsonl"
FINETUNING_LOG = BASE_DIR / "finetuning_log.json"
REWARD_DOSYASI = BASE_DIR / "reward_history.json"


def log_oku(satir_sayisi: int = 50) -> list:
    try:
        if not LOG_DOSYASI.exists():
            return ["Henuz log yok."]
        with open(LOG_DOSYASI, encoding="utf-8") as f:
            satirlar = f.readlines()
        return [s.strip() for s in satirlar[-satir_sayisi:]]
    except Exception:
        return ["Log okunamadi."]


def egitim_bilgi() -> dict:
    try:
        toplam = 0
        if EGITIM_DOSYASI.exists():
            toplam = sum(1 for _ in open(EGITIM_DOSYASI, encoding="utf-8"))
        son_egitim = "Henuz yok"
        if FINETUNING_LOG.exists():
            with open(FINETUNING_LOG, encoding="utf-8") as f:
                log = json.load(f)
            son_egitim = log.get("zaman", "?")[:16]
        return {"toplam": toplam, "son_egitim": son_egitim}
    except Exception:
        return {"toplam": 0, "son_egitim": "?"}


def reward_ozeti() -> dict:
    try:
        if not REWARD_DOSYASI.exists():
            return {"ort": 0.5, "basari": 0, "toplam": 0}
        with open(REWARD_DOSYASI, encoding="utf-8") as f:
            history = json.load(f)
        if not history:
            return {"ort": 0.5, "basari": 0, "toplam": 0}
        son_10 = history[-10:]
        ort = sum(r["smoothed"] for r in son_10) / len(son_10)
        basari = sum(1 for r in son_10 if r["basari"])
        return {"ort": round(ort, 3), "basari": basari, "toplam": len(history)}
    except Exception:
        return {"ort": 0.5, "basari": 0, "toplam": 0}


def api_durumu() -> list:
    try:
        if not ROTATOR_AKTIF:
            return []
        sonuc = []
        for p in rotator.providers:
            sonuc.append(
                {
                    "isim": p["isim"],
                    "kullanim": p["kullanim_sayisi"],
                    "limit": p["gunluk_limit"],
                    "yuzde": round(p["kullanim_sayisi"] / max(1, p["gunluk_limit"]) * 100, 1),
                    "aktif": bool(p.get("api_key")),
                }
            )
        return sonuc
    except Exception:
        return []


def model_performans_verisi() -> list:
    try:
        if not STRATEJI_AKTIF:
            return []
        sonuc = []
        for anahtar, p in strategy_mgr.model_performans.items():
            if p["toplam"] >= 2:
                sonuc.append(
                    {
                        "model": p["model"],
                        "gorev": p["gorev_turu"],
                        "basari": round(p["basari_orani"] * 100, 1),
                        "toplam": p["toplam"],
                        "ort_sure": p["ort_sure"],
                    }
                )
        sonuc.sort(key=lambda x: x["basari"], reverse=True)
        return sonuc
    except Exception:
        return []


def basarisiz_toollar() -> list:
    try:
        if not STRATEJI_AKTIF:
            return []
        return strategy_mgr.basarisiz_toollari_al()
    except Exception:
        return []


def reward_trend_verisi() -> dict:
    """Son 50 reward kaydini grafik icin hazirla"""
    try:
        if not REWARD_DOSYASI.exists():
            return {"etiketler": [], "degerler": [], "basarilar": []}
        with open(REWARD_DOSYASI, encoding="utf-8") as f:
            history = json.load(f)
        if not history:
            return {"etiketler": [], "degerler": [], "basarilar": []}
        son = history[-50:]
        etiketler = [str(i + 1) for i in range(len(son))]
        degerler = [round(r.get("smoothed", 0), 3) for r in son]
        basarilar = [1 if r.get("basari") else 0 for r in son]
        return {"etiketler": etiketler, "degerler": degerler, "basarilar": basarilar}
    except Exception:
        return {"etiketler": [], "degerler": [], "basarilar": []}


def hata_trend_verisi() -> dict:
    """Gorev turune gore hata istatistiklerini grafik icin hazirla"""
    try:
        hata_dosyasi = BASE_DIR / "hata_verisi.jsonl"
        if not hata_dosyasi.exists():
            return {"etiketler": [], "degerler": []}
        hata_sayac = {}
        with open(hata_dosyasi, encoding="utf-8") as f:
            for satir in f:
                satir = satir.strip()
                if not satir:
                    continue
                try:
                    kayit = json.loads(satir)
                    tur = kayit.get("gorev_turu", "genel")
                    hata_sayac[tur] = hata_sayac.get(tur, 0) + 1
                except Exception:
                    pass  # optional import
        sirali = sorted(hata_sayac.items(), key=lambda x: x[1], reverse=True)[:8]
        return {"etiketler": [x[0] for x in sirali], "degerler": [x[1] for x in sirali]}
    except Exception:
        return {"etiketler": [], "degerler": []}


def model_kullanim_verisi() -> dict:
    """Model kullanim dagiliminipasta grafik icin hazirla"""
    try:
        model_dosyasi = BASE_DIR / "model_performans.json"
        if not model_dosyasi.exists():
            return {"etiketler": [], "degerler": []}
        with open(model_dosyasi, encoding="utf-8") as f:
            data = json.load(f)
        model_toplam = {}
        for anahtar, bilgi in data.items():
            model = bilgi.get("model", "Bilinmiyor")
            toplam = bilgi.get("toplam", 0)
            model_toplam[model] = model_toplam.get(model, 0) + toplam
        sirali = sorted(model_toplam.items(), key=lambda x: x[1], reverse=True)
        return {"etiketler": [x[0] for x in sirali], "degerler": [x[1] for x in sirali]}
    except Exception:
        return {"etiketler": [], "degerler": []}


def episodik_hafiza_verisi() -> dict:
    """Episodik hafiza kayitlarini hazirla"""
    try:
        if not HAFIZA_AKTIF:
            return {"kayitlar": [], "toplam": 0, "ani_sayisi": 0, "prosedur_sayisi": 0}
        ani_sayisi = 0
        prosedur_sayisi = 0
        try:
            ani_sayisi = memory.episodik.anlar.count()
        except Exception:
            pass  # optional import
        try:
            prosedur_sayisi = memory.prosedur.prosedurler.count()
        except Exception:
            pass  # optional import
        kayitlar = []
        try:
            sonuclar = memory.episodik.anlar.get(limit=8, include=["metadatas"])
            if sonuclar and sonuclar.get("metadatas"):
                for meta in sonuclar["metadatas"]:
                    kayitlar.append(
                        {
                            "baslik": meta.get("baslik", "?")[:50],
                            "onem": round(float(meta.get("onem", 0)), 2),
                        }
                    )
        except Exception as e:
            print(f"[Dashboard] Hafiza kayitlari okunamadi: {e}")
        return {
            "kayitlar": kayitlar,
            "toplam": ani_sayisi + prosedur_sayisi,
            "ani_sayisi": ani_sayisi,
            "prosedur_sayisi": prosedur_sayisi,
        }
    except Exception:
        return {"kayitlar": [], "toplam": 0, "ani_sayisi": 0, "prosedur_sayisi": 0}


def guvenlik_verisi() -> dict:
    """Guvenlik istatistiklerini hazirla"""
    try:
        guvenlik_log = BASE_DIR / "guvenlik_log.json"
        if not guvenlik_log.exists():
            return {"toplam": 0, "injection": 0, "bypass": 0, "risk": 0, "semantik": 0}
        with open(guvenlik_log, encoding="utf-8") as f:
            data = json.load(f)
        olaylar = data if isinstance(data, list) else data.get("olaylar", [])
        injection = sum(1 for o in olaylar if o.get("tip") == "injection")
        bypass = sum(1 for o in olaylar if o.get("tip") == "bypass")
        risk = sum(1 for o in olaylar if o.get("tip") == "risk_skoru")
        semantik = sum(1 for o in olaylar if "semantik" in str(o.get("tespit", "")))
        return {
            "toplam": len(olaylar),
            "injection": injection,
            "bypass": bypass,
            "risk": risk,
            "semantik": semantik,
        }
    except Exception:
        return {"toplam": 0, "injection": 0, "bypass": 0, "risk": 0, "semantik": 0}


# ─────────────────────────────────────────────────────────────
# ASAMA 18: YENİ VERİ FONKSİYONLARI
# ─────────────────────────────────────────────────────────────


def latency_verisi() -> dict:
    """Motor bazli ortalama yanit suresi (son 50 kayit)"""
    try:
        if not REWARD_DOSYASI.exists():
            return {"modeller": [], "sureler": [], "bugun": 0, "hafta": 0}
        with open(REWARD_DOSYASI, encoding="utf-8") as f:
            history = json.load(f)
        if not history:
            return {"modeller": [], "sureler": [], "bugun": 0, "hafta": 0}

        # Model performans dosyasindan motor bazli sure hesapla
        model_dosyasi = BASE_DIR / "model_performans.json"
        motor_sure = {}
        if model_dosyasi.exists():
            with open(model_dosyasi, encoding="utf-8") as f:
                perf = json.load(f)
            for _, bilgi in perf.items():
                motor = bilgi.get("model", "Bilinmiyor")
                sure = bilgi.get("ort_sure", 0)
                if motor not in motor_sure:
                    motor_sure[motor] = []
                motor_sure[motor].append(sure)

        modeller = list(motor_sure.keys())
        sureler = [round(sum(v) / len(v), 2) if v else 0 for v in motor_sure.values()]

        # Bugun ve haftalik ortalama sure
        son_50 = history[-50:]
        bugun_s = [r.get("sure", 0) for r in son_50[-10:]]
        hafta_s = [r.get("sure", 0) for r in son_50]
        bugun_ort = round(sum(bugun_s) / len(bugun_s), 2) if bugun_s else 0
        hafta_ort = round(sum(hafta_s) / len(hafta_s), 2) if hafta_s else 0

        return {"modeller": modeller, "sureler": sureler, "bugun": bugun_ort, "hafta": hafta_ort}
    except Exception:
        return {"modeller": [], "sureler": [], "bugun": 0, "hafta": 0}


def egitim_filtre_verisi() -> dict:
    """ASAMA 14 filtresi: Kabul edilen vs reddedilen egitim ornekleri"""
    try:
        toplam_basari = 0
        if EGITIM_DOSYASI.exists():
            toplam_basari = sum(1 for _ in open(EGITIM_DOSYASI, encoding="utf-8"))

        hata_dosyasi = BASE_DIR / "hata_verisi.jsonl"
        toplam_hata = 0
        if hata_dosyasi.exists():
            toplam_hata = sum(1 for _ in open(hata_dosyasi, encoding="utf-8"))

        # Hata kategori dagilimi (ASAMA 16)
        kategori_sayac = {}
        if hata_dosyasi.exists():
            with open(hata_dosyasi, encoding="utf-8") as f:
                for satir in f:
                    satir = satir.strip()
                    if satir:
                        try:
                            k = json.loads(satir).get("hata_kategorisi", "bilinmiyor")
                            kategori_sayac[k] = kategori_sayac.get(k, 0) + 1
                        except Exception:
                            continue  # Bozuk JSON satiri atla, sonraki satira gec

        return {"kabul": toplam_basari, "ret_hata": toplam_hata, "kategoriler": kategori_sayac}
    except Exception:
        return {"kabul": 0, "ret_hata": 0, "kategoriler": {}}


def aee_detay_verisi() -> dict:
    """ASAMA 16: AEE formul bilesenlerini ve Thompson Sampling durumunu hazirla"""
    try:
        if not REWARD_DOSYASI.exists():
            return {"formula_son": {}, "smoothed_trend": [], "alpha": 0.3}
        with open(REWARD_DOSYASI, encoding="utf-8") as f:
            history = json.load(f)
        if not history:
            return {"formula_son": {}, "smoothed_trend": [], "alpha": 0.3}

        son = history[-1]
        formula_son = son.get("formula", {})
        smoothed_trend = [round(r.get("smoothed", 0.5), 3) for r in history[-20:]]

        # Thompson Sampling: strateji dosyasindan al
        strateji_sayac = {}
        if STRATEJI_AKTIF:
            try:
                for anahtar, p in strategy_mgr.model_performans.items():
                    m = p.get("model", "?")
                    strateji_sayac[m] = {
                        "deneme": p.get("toplam", 0),
                        "basari": round(p.get("basari_orani", 0) * 100, 1),
                    }
            except Exception as e:
                print(f"[Dashboard] Strateji verisi okunamadi: {e}")

        return {
            "formula_son": formula_son,
            "smoothed_trend": smoothed_trend,
            "alpha": 0.3,
            "strateji": strateji_sayac,
        }
    except Exception:
        return {"formula_son": {}, "smoothed_trend": [], "alpha": 0.3}


def hafiza_hit_verisi() -> dict:
    """Hafiza hit rate: sorularin yuzde kaci hafizadan yararlanarak yanitlandi"""
    try:
        if not REWARD_DOSYASI.exists():
            return {"hit_rate": 0, "toplam": 0}
        with open(REWARD_DOSYASI, encoding="utf-8") as f:
            history = json.load(f)
        toplam = len(history)
        # Reward > 0.6 olan kayitlar hafiza destekli kabul edilir (yaklaşık)
        hit = sum(1 for r in history if r.get("normalized", 0) > 0.6)
        hit_rate = round(hit / toplam * 100, 1) if toplam > 0 else 0
        return {"hit_rate": hit_rate, "toplam": toplam, "hit": hit}
    except Exception:
        return {"hit_rate": 0, "toplam": 0, "hit": 0}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Harun AI - Kontrol Paneli</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0a0a; color: #e0e0e0; font-family: 'Courier New', monospace; }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 20px 30px; border-bottom: 2px solid #00ff88;
            display: flex; justify-content: space-between; align-items: center;
        }
        .header h1 { color: #00ff88; font-size: 22px; }
        .header .zaman { color: #888; font-size: 13px; }
        .status-dot {
            width: 12px; height: 12px; border-radius: 50%;
            background: #00ff88; display: inline-block;
            animation: pulse 2s infinite; margin-right: 8px;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .container { padding: 20px 30px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; margin-bottom: 20px; }
        .kart {
            background: #111; border: 1px solid #222;
            border-radius: 10px; padding: 18px; transition: border-color 0.3s;
        }
        .kart:hover { border-color: #00ff88; }
        .kart h3 { color: #00ff88; margin-bottom: 12px; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
        .kart .deger { font-size: 30px; font-weight: bold; color: #fff; }
        .kart .alt { font-size: 11px; color: #666; margin-top: 5px; }
        .bar { height: 7px; background: #222; border-radius: 4px; overflow: hidden; margin-top: 8px; }
        .bar-dolu { height: 100%; border-radius: 4px; transition: width 0.5s; }
        .bar-cpu { background: linear-gradient(90deg, #00ff88, #00cc66); }
        .bar-ram { background: linear-gradient(90deg, #0088ff, #0055cc); }
        .bar-disk { background: linear-gradient(90deg, #ff8800, #cc6600); }
        .bar-egitim { background: linear-gradient(90deg, #aa00ff, #7700cc); }
        .bar-api { background: linear-gradient(90deg, #00ffcc, #00aa88); }
        .bar-reward { background: linear-gradient(90deg, #ffdd00, #ccaa00); }
        .bolum { background: #111; border: 1px solid #222; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
        .bolum h3 { color: #00ff88; margin-bottom: 16px; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }
        .grafik-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .grafik-kart { background: #111; border: 1px solid #222; border-radius: 10px; padding: 20px; }
        .grafik-kart h3 { color: #00ff88; margin-bottom: 14px; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
        .grafik-kart canvas { max-height: 220px; }
        .api-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
        .api-kart { background: #0a0a0a; border: 1px solid #333; border-radius: 8px; padding: 14px; }
        .api-kart .api-isim { font-size: 16px; font-weight: bold; color: #fff; margin-bottom: 6px; }
        .api-kart .api-durum { font-size: 11px; margin-bottom: 8px; }
        .aktif-tag { color: #00ff88; }
        .pasif-tag { color: #ff4444; }
        .tablo { width: 100%; border-collapse: collapse; }
        .tablo th { color: #00ff88; font-size: 11px; text-align: left; padding: 8px 12px; border-bottom: 1px solid #333; }
        .tablo td { padding: 8px 12px; font-size: 12px; border-bottom: 1px solid #1a1a1a; }
        .tablo tr:hover td { background: #161616; }
        .basari-yuksek { color: #00ff88; font-weight: bold; }
        .basari-orta { color: #ffdd00; }
        .basari-dusuk { color: #ff4444; }
        .mini-bar { height: 5px; background: #222; border-radius: 3px; overflow: hidden; width: 80px; }
        .mini-bar-ic { height: 100%; border-radius: 3px; }
        .uyari { background: #1a0a0a; border: 1px solid #ff4444; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; font-size: 12px; }
        .uyari .uyari-baslik { color: #ff4444; font-weight: bold; margin-bottom: 4px; }
        .hafiza-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
        .hafiza-kart { background: #111; border: 1px solid #222; border-radius: 10px; padding: 14px; text-align: center; }
        .hafiza-kart .sayi { font-size: 32px; font-weight: bold; color: #00ff88; }
        .hafiza-kart .etiket { font-size: 11px; color: #666; margin-top: 4px; }
        .episodik-liste { list-style: none; }
        .episodik-liste li { padding: 7px 10px; border-bottom: 1px solid #1a1a1a; font-size: 12px; display: flex; justify-content: space-between; }
        .episodik-liste li:hover { background: #161616; }
        .onem-badge { background: #1a2a1a; color: #00ff88; border-radius: 4px; padding: 1px 7px; font-size: 11px; }
        .log-icerik { height: 220px; overflow-y: auto; font-size: 11px; line-height: 1.8; }
        .log-satir { padding: 2px 0; border-bottom: 1px solid #0f0f0f; }
        .log-satir:hover { background: #111; }
        .yenile-btn {
            position: fixed; bottom: 24px; right: 24px;
            background: #00ff88; color: #000; border: none;
            border-radius: 50px; padding: 10px 22px;
            font-weight: bold; cursor: pointer; font-family: 'Courier New', monospace; font-size: 13px;
        }
        .yenile-btn:hover { background: #00cc66; }
        .bos-not { color: #555; font-size: 12px; font-style: italic; }
        .guncellendi { font-size: 11px; color: #555; margin-top: 6px; }
        #canli-zaman { color: #00ff88; }
    </style>
</head>
<body>
<div class="header">
    <div><span class="status-dot"></span><h1 style="display:inline">HARUN AI KONTROL PANELİ</h1></div>
    <div class="zaman">
        <span id="canli-zaman">{{ zaman }}</span>
        <div class="guncellendi">Veriler 15sn'de bir güncellenir</div>
    </div>
</div>
<div class="container">

    <!-- Sistem Metrikleri -->
    <div class="grid" id="sistem-grid">
        <div class="kart">
            <h3>CPU</h3>
            <div class="deger" id="cpu-deger">{{ cpu }}%</div>
            <div class="bar"><div class="bar-dolu bar-cpu" id="cpu-bar" style="width:{{ cpu }}%"></div></div>
            <div class="alt">{{ cpu_cekirdek }} çekirdek</div>
        </div>
        <div class="kart">
            <h3>RAM</h3>
            <div class="deger" id="ram-deger">{{ ram_yuzde }}%</div>
            <div class="bar"><div class="bar-dolu bar-ram" id="ram-bar" style="width:{{ ram_yuzde }}%"></div></div>
            <div class="alt" id="ram-alt">{{ ram_kullanilan }} / {{ ram_toplam }} GB</div>
        </div>
        <div class="kart">
            <h3>Disk</h3>
            <div class="deger">{{ disk_yuzde }}%</div>
            <div class="bar"><div class="bar-dolu bar-disk" style="width:{{ disk_yuzde }}%"></div></div>
            <div class="alt">{{ disk_kullanilan }} / {{ disk_toplam }} GB</div>
        </div>
        <div class="kart">
            <h3>Eğitim Verisi</h3>
            <div class="deger" id="egitim-deger">{{ egitim_toplam }}</div>
            <div class="bar"><div class="bar-dolu bar-egitim" id="egitim-bar" style="width:{{ [egitim_toplam * 0.2, 100] | min }}%"></div></div>
            <div class="alt">Hedef: 500 | Son: {{ son_egitim }}</div>
        </div>
        <div class="kart">
            <h3>Reward (Son 10)</h3>
            <div class="deger" id="reward-deger">{{ reward.basari }}/10</div>
            <div class="bar"><div class="bar-dolu bar-reward" id="reward-bar" style="width:{{ reward.ort * 100 }}%"></div></div>
            <div class="alt" id="reward-alt">Ort: {{ reward.ort }} | Toplam: {{ reward.toplam }}</div>
        </div>
    </div>

    <!-- Hafıza (genişletilmiş — episodik + prosedürel dahil) -->
    <div class="hafiza-grid">
        <div class="hafiza-kart">
            <div class="sayi" id="hf-gorev">{{ gorev_sayisi }}</div>
            <div class="etiket">Kayıtlı Görev</div>
        </div>
        <div class="hafiza-kart">
            <div class="sayi" id="hf-bilgi">{{ bilgi_sayisi }}</div>
            <div class="etiket">Kayıtlı Bilgi</div>
        </div>
        <div class="hafiza-kart">
            <div class="sayi" id="hf-tercih">{{ tercih_sayisi }}</div>
            <div class="etiket">Kayıtlı Tercih</div>
        </div>
        <div class="hafiza-kart">
            <div class="sayi" id="hf-ani" style="color:#aa88ff">{{ episodik.ani_sayisi }}</div>
            <div class="etiket">Episodik Anı</div>
        </div>
        <div class="hafiza-kart">
            <div class="sayi" id="hf-prosedur" style="color:#88ccff">{{ episodik.prosedur_sayisi }}</div>
            <div class="etiket">Prosedür</div>
        </div>
    </div>

    <!-- GRAFİKLER -->
    <div class="grafik-grid">

        <!-- Reward Trendi -->
        <div class="grafik-kart">
            <h3>Reward Trendi (Son 50 İşlem)</h3>
            <canvas id="rewardChart"></canvas>
        </div>

        <!-- Model Kullanım Dağılımı -->
        <div class="grafik-kart">
            <h3>Model Kullanım Dağılımı</h3>
            <canvas id="modelChart"></canvas>
        </div>

        <!-- Hata Oranı (Görev Türüne Göre) -->
        <div class="grafik-kart">
            <h3>Hata Dağılımı (Görev Türü)</h3>
            <canvas id="hataChart"></canvas>
        </div>

        <!-- Güvenlik Olayları -->
        <div class="grafik-kart">
            <h3>Güvenlik Olayları</h3>
            <canvas id="guvenlikChart"></canvas>
        </div>

    </div>

    <!-- Episodik Hafıza Listesi -->
    {% if episodik.kayitlar %}
    <div class="bolum">
        <h3>Son Episodik Anılar</h3>
        <ul class="episodik-liste">
            {% for ani in episodik.kayitlar %}
            <li>
                <span>{{ ani.baslik }}</span>
                <span class="onem-badge">önem: {{ ani.onem }}</span>
            </li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}

    <!-- API Durumu -->
    <div class="bolum">
        <h3>API Rotasyon Durumu</h3>
        <div class="api-grid">
            {% for api in api_durumu %}
            <div class="api-kart">
                <div class="api-isim">{{ api.isim }}</div>
                <div class="api-durum">
                    {% if api.aktif %}<span class="aktif-tag">Aktif</span>{% else %}<span class="pasif-tag">Key Eksik</span>{% endif %}
                </div>
                <div class="bar"><div class="bar-dolu bar-api" style="width:{{ api.yuzde }}%"></div></div>
                <div class="alt">{{ api.kullanim }} / {{ api.limit }} istek (%{{ api.yuzde }})</div>
            </div>
            {% endfor %}
            {% if not api_durumu %}
            <div class="bos-not">API verisi yuklenemedi.</div>
            {% endif %}
        </div>
    </div>

    <!-- Model Performans Tablosu -->
    <div class="bolum">
        <h3>Model Performansları</h3>
        {% if model_performans %}
        <table class="tablo">
            <tr>
                <th>Model</th><th>Görev Türü</th><th>Başarı</th>
                <th>Grafik</th><th>Kullanım</th><th>Ort. Süre</th>
            </tr>
            {% for p in model_performans %}
            <tr>
                <td>{{ p.model }}</td>
                <td>{{ p.gorev }}</td>
                <td class="{% if p.basari >= 75 %}basari-yuksek{% elif p.basari >= 50 %}basari-orta{% else %}basari-dusuk{% endif %}">
                    %{{ p.basari }}
                </td>
                <td>
                    <div class="mini-bar">
                        <div class="mini-bar-ic" style="width:{{ p.basari }}%; background: {% if p.basari >= 75 %}#00ff88{% elif p.basari >= 50 %}#ffdd00{% else %}#ff4444{% endif %}"></div>
                    </div>
                </td>
                <td>{{ p.toplam }} görev</td>
                <td>{{ p.ort_sure }}s</td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <div class="bos-not">Henuz yeterli veri yok.</div>
        {% endif %}
    </div>

    <!-- Başarısız Tool'lar -->
    {% if basarisiz_toollar %}
    <div class="bolum">
        <h3>Dusuk Performansli Kombinasyonlar</h3>
        {% for t in basarisiz_toollar %}
        <div class="uyari">
            <div class="uyari-baslik">{{ t.model }} → {{ t.gorev_turu }}</div>
            <div>Basari: %{{ (t.basari_orani * 100) | int }} | {{ t.toplam }} gorev | Ort. {{ t.ort_sure }}s</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <!-- ASAMA 18: Derinlestirilmis Metrikler -->
    <div class="bolum">
        <h3>&#9889; Asama 18 — Derinlestirilmis Izleme</h3>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px;">
            <div class="kart" style="text-align:center;">
                <div class="kart-baslik">LATENCY (BUGUN)</div>
                <div class="kart-deger" id="latency-bugun">-</div>
                <div class="kart-alt">Ort. yanit suresi</div>
            </div>
            <div class="kart" style="text-align:center;">
                <div class="kart-baslik">LATENCY (HAFTA)</div>
                <div class="kart-deger" id="latency-hafta">-</div>
                <div class="kart-alt">7 gunluk ortalama</div>
            </div>
            <div class="kart" style="text-align:center;">
                <div class="kart-baslik">HAFIZA HIT RATE</div>
                <div class="kart-deger" id="hafiza-hit">-</div>
                <div class="kart-alt">Hafizadan yararlanma</div>
            </div>
            <div class="kart" style="text-align:center;">
                <div class="kart-baslik">FILTRE (ASAMA 14)</div>
                <div class="kart-deger" style="font-size:1em;">
                    <span style="color:#00ff88" id="filtre-kabul">-</span>
                    <span style="color:#888"> / </span>
                    <span style="color:#ff4444" id="filtre-ret">-</span>
                </div>
                <div class="kart-alt">Kabul / Reddedilen</div>
            </div>
        </div>

        <!-- AEE Formul + Motor Latency grafikleri -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
            <div class="kart">
                <div class="kart-baslik">MOTOR LATENCY KARSILASTIRMASI</div>
                <div style="height:180px;"><canvas id="latencyCanvas"></canvas></div>
            </div>
            <div class="kart">
                <div class="kart-baslik">HATA KATEGORİ DAGILIMI (ASAMA 16)</div>
                <div style="height:180px;"><canvas id="hataKategoriCanvas"></canvas></div>
            </div>
        </div>

        <!-- AEE Formul Ozeti -->
        <div class="kart">
            <div class="kart-baslik">AEE REWARD FORMUL SON KAYIT (ASAMA 16)</div>
            <div id="aee-formul" style="font-family:Courier New;font-size:0.85em;color:#aaa;padding:6px 0;">
                Veri bekleniyor...
            </div>
            <div style="font-size:0.75em;color:#555;margin-top:4px;">
                Formul: basari*0.50 + verimlilik*0.20 + kullanici*0.20 - maliyet*0.10 | EMA alpha=0.3
            </div>
        </div>
    </div>

    <!-- Log -->
    <div class="bolum">
        <h3>Son Loglar</h3>
        <div class="log-icerik" id="log-alan">
            {% for satir in loglar %}
            <div class="log-satir">{{ satir }}</div>
            {% endfor %}
        </div>
    </div>

</div>
<button class="yenile-btn" onclick="veriYenile()">Canli Guncelle</button>

<script>
// ─── Grafik Renk Paleti ───
const RENKLER = ['#00ff88','#0088ff','#ff8800','#aa00ff','#ff4444','#ffdd00','#00ffcc','#ff88aa'];

// ─── Grafik Nesneleri ───
let rewardChart, modelChart, hataChart, guvenlikChart;

// ─── Chart.js Global Ayarlar ───
Chart.defaults.color = '#888';
Chart.defaults.borderColor = '#222';
Chart.defaults.font.family = 'Courier New, monospace';

// ─── Reward Trend Grafiği ───
function rewardGrafik(data) {
    const ctx = document.getElementById('rewardChart').getContext('2d');
    if (rewardChart) rewardChart.destroy();
    rewardChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.etiketler,
            datasets: [{
                label: 'Smoothed Reward',
                data: data.degerler,
                borderColor: '#00ff88',
                backgroundColor: 'rgba(0,255,136,0.07)',
                borderWidth: 2,
                pointRadius: 2,
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: { min: 0, max: 1, grid: { color: '#1a1a1a' },
                     ticks: { callback: v => (v*100).toFixed(0)+'%' } },
                x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } }
            }
        }
    });
}

// ─── Model Kullanım Pasta Grafiği ───
function modelGrafik(data) {
    const ctx = document.getElementById('modelChart').getContext('2d');
    if (modelChart) modelChart.destroy();
    if (!data.etiketler.length) {
        ctx.fillStyle = '#555';
        ctx.font = '12px Courier New';
        ctx.fillText('Henuz veri yok', 80, 110);
        return;
    }
    modelChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.etiketler,
            datasets: [{
                data: data.degerler,
                backgroundColor: RENKLER.slice(0, data.etiketler.length),
                borderColor: '#0a0a0a',
                borderWidth: 3
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 16, font: { size: 11 } } }
            }
        }
    });
}

// ─── Hata Dağılımı Bar Grafiği ───
function hataGrafik(data) {
    const ctx = document.getElementById('hataChart').getContext('2d');
    if (hataChart) hataChart.destroy();
    if (!data.etiketler.length) {
        ctx.fillStyle = '#555';
        ctx.font = '12px Courier New';
        ctx.fillText('Hata verisi yok', 80, 110);
        return;
    }
    hataChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.etiketler,
            datasets: [{
                label: 'Hata Sayisi',
                data: data.degerler,
                backgroundColor: 'rgba(255,68,68,0.7)',
                borderColor: '#ff4444',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: '#1a1a1a' }, ticks: { stepSize: 1 } },
                x: { grid: { display: false } }
            }
        }
    });
}

// ─── Güvenlik Olayları Bar Grafiği ───
function guvenlikGrafik(data) {
    const ctx = document.getElementById('guvenlikChart').getContext('2d');
    if (guvenlikChart) guvenlikChart.destroy();
    guvenlikChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Toplam Olay', 'Injection', 'Bypass'],
            datasets: [{
                label: 'Guvenlik',
                data: [data.toplam, data.injection, data.bypass],
                backgroundColor: ['rgba(255,136,0,0.7)', 'rgba(255,68,68,0.7)', 'rgba(170,0,255,0.7)'],
                borderColor: ['#ff8800', '#ff4444', '#aa00ff'],
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: '#1a1a1a' }, ticks: { stepSize: 1 } },
                x: { grid: { display: false } }
            }
        }
    });
}

// ─── Canlı Saat ───
function saatGuncelle() {
    const simdi = new Date();
    const str = simdi.toLocaleDateString('tr-TR') + ' ' +
                simdi.toLocaleTimeString('tr-TR');
    document.getElementById('canli-zaman').textContent = str;
}
setInterval(saatGuncelle, 1000);

// ─── ASAMA 18: Yeni Grafik Degiskenleri ───
let latencyChart = null;
let hataKategoriChart = null;

function latencyGrafik(data) {
    if (!data.modeller || data.modeller.length === 0) return;
    const ctx = document.getElementById('latencyCanvas');
    if (!ctx) return;
    if (latencyChart) { latencyChart.destroy(); }
    latencyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.modeller,
            datasets: [{
                label: 'Ort. Sure (sn)',
                data: data.sureler,
                backgroundColor: ['#00ff88','#0088ff','#ff8800'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color:'#888', font:{family:'Courier New'} }, grid: { color:'#222' } },
                y: { ticks: { color:'#888', font:{family:'Courier New'} }, grid: { color:'#222' }, beginAtZero: true }
            }
        }
    });
}

function hataKategoriGrafik(filtre) {
    if (!filtre.kategoriler) return;
    const ctx = document.getElementById('hataKategoriCanvas');
    if (!ctx) return;
    const kat = filtre.kategoriler;
    const labels = Object.keys(kat);
    const vals   = Object.values(kat);
    if (labels.length === 0) return;
    if (hataKategoriChart) { hataKategoriChart.destroy(); }
    hataKategoriChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: vals,
                backgroundColor: ['#ff4444','#ff8800','#ffdd00','#aa00ff','#0088ff'],
                borderColor: '#111', borderWidth: 2
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position:'bottom', labels: { color:'#888', font:{family:'Courier New', size:11} } }
            }
        }
    });
}

// ─── AJAX Veri Yenileme ───
async function veriYenile() {
    try {
        // Sistem metrikleri
        const sistemRes = await fetch('/api/sistem');
        const sistem = await sistemRes.json();
        document.getElementById('cpu-deger').textContent = sistem.cpu + '%';
        document.getElementById('cpu-bar').style.width = sistem.cpu + '%';
        document.getElementById('ram-deger').textContent = sistem.ram_yuzde + '%';
        document.getElementById('ram-bar').style.width = sistem.ram_yuzde + '%';
        document.getElementById('ram-alt').textContent = sistem.ram_kullanilan + ' / ' + sistem.ram_toplam + ' GB';
        document.getElementById('egitim-deger').textContent = sistem.egitim_toplam;
        document.getElementById('egitim-bar').style.width = Math.min(sistem.egitim_toplam * 0.2, 100) + '%';
        document.getElementById('reward-deger').textContent = sistem.reward_basari + '/10';
        document.getElementById('reward-bar').style.width = (sistem.reward_ort * 100) + '%';
        document.getElementById('reward-alt').textContent = 'Ort: ' + sistem.reward_ort + ' | Toplam: ' + sistem.reward_toplam;
        document.getElementById('hf-gorev').textContent = sistem.gorev_sayisi;
        document.getElementById('hf-bilgi').textContent = sistem.bilgi_sayisi;
        document.getElementById('hf-tercih').textContent = sistem.tercih_sayisi;
        document.getElementById('hf-ani').textContent = sistem.ani_sayisi;
        document.getElementById('hf-prosedur').textContent = sistem.prosedur_sayisi;

        // Grafikler
        const grafRes = await fetch('/api/grafik');
        const graf = await grafRes.json();
        rewardGrafik(graf.reward);
        modelGrafik(graf.model);
        hataGrafik(graf.hata);
        guvenlikGrafik(graf.guvenlik);

        // Loglar
        const logRes = await fetch('/api/log');
        const logData = await logRes.json();
        const logAlan = document.getElementById('log-alan');
        logAlan.innerHTML = logData.loglar.map(s => '<div class="log-satir">' + s + '</div>').join('');
        logAlan.scrollTop = logAlan.scrollHeight;

        // ASAMA 18: Derinlestirilmis metrikler
        try {
            const detayRes = await fetch('/api/detay');
            const detay = await detayRes.json();

            // Latency metrikleri
            const bugunEl = document.getElementById('latency-bugun');
            const haftaEl = document.getElementById('latency-hafta');
            if (bugunEl) bugunEl.textContent = detay.latency.bugun + 's';
            if (haftaEl) haftaEl.textContent = detay.latency.hafta + 's';

            // Egitim filtresi (ASAMA 14)
            const kabulEl = document.getElementById('filtre-kabul');
            const retEl   = document.getElementById('filtre-ret');
            if (kabulEl) kabulEl.textContent = detay.filtre.kabul;
            if (retEl)   retEl.textContent   = detay.filtre.ret_hata;

            // Hafiza hit rate
            const hitEl = document.getElementById('hafiza-hit');
            if (hitEl) hitEl.textContent = detay.hafiza_hit.hit_rate + '%';

            // AEE formul ozeti
            const aeeEl = document.getElementById('aee-formul');
            if (aeeEl && detay.aee.formula_son) {
                const f = detay.aee.formula_son;
                aeeEl.innerHTML =
                    '<span style="color:#00ff88">+' + (f.basari_katkisi||0).toFixed(3) + ' basari</span> ' +
                    '<span style="color:#0088ff">+' + (f.verimlilik_katkisi||0).toFixed(3) + ' verimlilik</span> ' +
                    '<span style="color:#ffdd00">+' + (f.kullanici_katkisi||0).toFixed(3) + ' kullanici</span> ' +
                    '<span style="color:#ff4444">-' + (f.maliyet_cezasi||0).toFixed(3) + ' maliyet</span>';
            }

            // Guvenlik katman sayilari (ASAMA 15)
            const guv = detay.aee; // guvenlik verisi grafik uzerinden geliyor
            latencyGrafik(detay.latency);
            hataKategoriGrafik(detay.filtre);
        } catch(ex) {
            console.log('Detay guncelleme hatasi:', ex);
        }

    } catch(e) {
        console.log('Guncelleme hatasi:', e);
    }
}

// ─── Sayfa Yüklenince Grafikleri Çiz ───
window.onload = function() {
    veriYenile();  // Ilk yukleme
    setInterval(veriYenile, 15000);  // 15sn guncelleme
};
</script>
</body>
</html>
"""


@app.route("/")
def panel():
    cpu = psutil.cpu_percent(interval=1)
    cpu_cekirdek = psutil.cpu_count()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:/")

    gorev_sayisi = bilgi_sayisi = tercih_sayisi = 0
    if HAFIZA_AKTIF:
        try:
            gorev_sayisi = memory.gorevler.count()
            bilgi_sayisi = memory.bilgiler.count()
            tercih_sayisi = memory.tercihler.count()
        except Exception as e:
            print("[Dashboard] Hafiza sayac hatasi:", e)

    eg = egitim_bilgi()
    reward = reward_ozeti()
    episodik = episodik_hafiza_verisi()

    return render_template_string(
        HTML_TEMPLATE,
        zaman=datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        cpu=cpu,
        cpu_cekirdek=cpu_cekirdek,
        ram_yuzde=ram.percent,
        ram_kullanilan=round(ram.used / (1024**3), 1),
        ram_toplam=round(ram.total / (1024**3), 1),
        disk_yuzde=disk.percent,
        disk_kullanilan=round(disk.used / (1024**3), 1),
        disk_toplam=round(disk.total / (1024**3), 1),
        gorev_sayisi=gorev_sayisi,
        bilgi_sayisi=bilgi_sayisi,
        tercih_sayisi=tercih_sayisi,
        egitim_toplam=eg["toplam"],
        son_egitim=eg["son_egitim"],
        reward=reward,
        episodik=episodik,
        api_durumu=api_durumu(),
        model_performans=model_performans_verisi(),
        basarisiz_toollar=basarisiz_toollar(),
        loglar=log_oku(50),
    )


@app.route("/api/sistem")
def api_sistem():
    """AJAX: Sistem metriklerini JSON olarak döner"""
    ram = psutil.virtual_memory()
    reward = reward_ozeti()
    episodik = episodik_hafiza_verisi()
    gorev_sayisi = bilgi_sayisi = tercih_sayisi = 0
    if HAFIZA_AKTIF:
        try:
            gorev_sayisi = memory.gorevler.count()
            bilgi_sayisi = memory.bilgiler.count()
            tercih_sayisi = memory.tercihler.count()
        except Exception as e:
            print("[Dashboard] API hafiza sayac hatasi:", e)
    eg = egitim_bilgi()
    return jsonify(
        {
            "cpu": psutil.cpu_percent(interval=0.5),
            "ram_yuzde": ram.percent,
            "ram_kullanilan": round(ram.used / (1024**3), 1),
            "ram_toplam": round(ram.total / (1024**3), 1),
            "egitim_toplam": eg["toplam"],
            "reward_basari": reward["basari"],
            "reward_ort": reward["ort"],
            "reward_toplam": reward["toplam"],
            "gorev_sayisi": gorev_sayisi,
            "bilgi_sayisi": bilgi_sayisi,
            "tercih_sayisi": tercih_sayisi,
            "ani_sayisi": episodik["ani_sayisi"],
            "prosedur_sayisi": episodik["prosedur_sayisi"],
        }
    )


@app.route("/api/grafik")
def api_grafik():
    """AJAX: Tum grafik verilerini JSON olarak döner"""
    return jsonify(
        {
            "reward": reward_trend_verisi(),
            "model": model_kullanim_verisi(),
            "hata": hata_trend_verisi(),
            "guvenlik": guvenlik_verisi(),
        }
    )


@app.route("/api/detay")
def api_detay():
    """ASAMA 18: Derinlestirilmis metrikler"""
    return jsonify(
        {
            "latency": latency_verisi(),
            "filtre": egitim_filtre_verisi(),
            "aee": aee_detay_verisi(),
            "hafiza_hit": hafiza_hit_verisi(),
        }
    )


@app.route("/api/log")
def api_log():
    """AJAX: Son loglari JSON olarak döner"""
    return jsonify({"loglar": log_oku(50)})


if __name__ == "__main__":
    print("Kontrol paneli baslatiliyor...")
    print("Tarayicida ac: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
