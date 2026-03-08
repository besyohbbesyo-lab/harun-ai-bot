# bot_config.py - Merkezi Konfigurasyon Yukleyici (Asama 2 Gorev 9)
# -------------------------------------------------------------------
# config.yaml dosyasini okur, varsayilan degerlerle birlestirir.
# Tum moduller buradan import eder:
#   from bot_config import CFG
#   CFG["ollama"]["timeout"]  → 120

import os
from pathlib import Path

try:
    import yaml

    _YAML_MEVCUT = True
except ImportError:
    _YAML_MEVCUT = False
    print("[Config] UYARI: PyYAML yuklenmemis. Varsayilan degerler kullanilacak.")
    print("         Kurmak icin: pip install PyYAML")

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_DOSYASI = BASE_DIR / "config.yaml"

# ─────────────────────────────────────────────────────────────
# VARSAYILAN DEGERLER (config.yaml okunamazsa bunlar kullanilir)
# ─────────────────────────────────────────────────────────────
_VARSAYILAN = {
    "groq": {
        "models": [
            {"id": "llama-3.3-70b-versatile", "max_tokens": 2000, "maliyet": 3},
            {"id": "llama-3.1-8b-instant", "max_tokens": 2000, "maliyet": 1},
            {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "max_tokens": 2000, "maliyet": 2},
        ],
        "task_model_pref": {
            "kod": 0,
            "sunum": 0,
            "word": 0,
            "arastirma": 0,
            "planner": 0,
            "pdf": 0,
            "sohbet": 1,
            "genel": 1,
            "basit": 1,
        },
        "default_model": "llama-3.1-8b-instant",
        "default_max_tokens": 2000,
    },
    "ollama": {
        "url": "http://localhost:11434/api/generate",
        "timeout": 120,
        "default_model": "haervwe/GLM-4.6V-Flash-9B",
    },
    "model_secim": {
        "lokal_max_tokens": 50,
        "cloud_min_tokens": 200,
    },
    "guvenlik": {
        "rate_limit_pencere": 60,
        "rate_limit_maksimum": 10,
    },
    "log": {
        "max_boyut_mb": 10,
        "max_yedek": 5,
        "dosya": "bot_log.txt",
    },
    "bot": {
        "baslangic_mesaji": "Harun AI Bot aktif!",
        "proaktif_zeka_aralik_dk": 30,
    },
}


def _derin_birlestir(varsayilan: dict, kullanici: dict) -> dict:
    """Kullanici config'ini varsayilanla derin birlestirir.
    Kullanici degeri varsa onu kullan, yoksa varsayilani koru."""
    sonuc = dict(varsayilan)
    for key, val in kullanici.items():
        if key in sonuc and isinstance(sonuc[key], dict) and isinstance(val, dict):
            sonuc[key] = _derin_birlestir(sonuc[key], val)
        else:
            sonuc[key] = val
    return sonuc


def config_yukle() -> dict:
    """config.yaml'i oku ve varsayilanlarla birlestir."""
    if not _YAML_MEVCUT:
        return dict(_VARSAYILAN)

    if not CONFIG_DOSYASI.exists():
        print(f"[Config] {CONFIG_DOSYASI} bulunamadi. Varsayilan degerler kullaniliyor.")
        return dict(_VARSAYILAN)

    try:
        with open(CONFIG_DOSYASI, encoding="utf-8") as f:
            kullanici_cfg = yaml.safe_load(f) or {}
        cfg = _derin_birlestir(_VARSAYILAN, kullanici_cfg)
        print(f"[Config] config.yaml yuklendi ({len(kullanici_cfg)} bolum)")
        return cfg
    except Exception as e:
        print(f"[Config] UYARI: config.yaml okuma hatasi: {e}")
        print("[Config] Varsayilan degerler kullaniliyor.")
        return dict(_VARSAYILAN)


# ─────────────────────────────────────────────────────────────
# GLOBAL CONFIG NESNESI — Tum moduller bunu import eder
# ─────────────────────────────────────────────────────────────
CFG = config_yukle()
