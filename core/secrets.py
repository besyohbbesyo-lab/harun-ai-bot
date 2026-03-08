# core/secrets.py — S7-3: Secret Management
# Doppler → Vault → .env fallback zinciri
# Hicbir secret kaynak kodda olmaz
# ============================================================

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from core.config import log_yaz

# .env yukle (fallback)
load_dotenv()

# ── Secret Kaynaklari ─────────────────────────────────────────


class SecretKaynagi:
    DOPPLER = "doppler"
    VAULT = "vault"
    ENV = "env"
    NONE = "none"


_kaynak: str = SecretKaynagi.NONE
_cache: dict[str, str] = {}


# ── Doppler Entegrasyonu ──────────────────────────────────────


def _doppler_yukle() -> bool:
    """
    Doppler CLI ile secret'lari yukle.
    Kurulum: https://docs.doppler.com/docs/install-cli
    Kullanim: doppler setup → proje ve config sec
    """
    try:
        import subprocess

        sonuc = subprocess.run(
            ["doppler", "secrets", "download", "--no-file", "--format", "env"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if sonuc.returncode != 0:
            return False

        for satir in sonuc.stdout.splitlines():
            if "=" in satir and not satir.startswith("#"):
                anahtar, _, deger = satir.partition("=")
                _cache[anahtar.strip()] = deger.strip().strip('"')

        log_yaz(f"[Secrets] Doppler: {len(_cache)} secret yuklendi", "INFO")
        return True
    except (FileNotFoundError, Exception):
        return False


def _vault_yukle() -> bool:
    """
    HashiCorp Vault ile secret'lari yukle.
    VAULT_ADDR ve VAULT_TOKEN env'den okunur.
    """
    try:
        import json
        import urllib.request

        vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
        vault_token = os.getenv("VAULT_TOKEN", "")
        vault_path = os.getenv("VAULT_SECRET_PATH", "secret/data/harun_ai")

        if not vault_token:
            return False

        url = f"{vault_addr}/v1/{vault_path}"
        req = urllib.request.Request(url)
        req.add_header("X-Vault-Token", vault_token)

        with urllib.request.urlopen(req, timeout=3) as r:
            veri = json.loads(r.read())
            data = veri.get("data", {}).get("data", {})
            _cache.update(data)

        log_yaz(f"[Secrets] Vault: {len(data)} secret yuklendi", "INFO")
        return True
    except Exception:
        return False


def _env_yukle() -> bool:
    """
    .env dosyasindan fallback olarak yukle.
    Her zaman calısır.
    """
    kritik = [
        "TELEGRAM_TOKEN",
        "GROQ_API_KEY",
        "ALLOWED_USER_IDS",
        "GEMINI_API_KEY",
    ]
    yuklenen = 0
    for k in kritik:
        v = os.getenv(k, "")
        if v:
            _cache[k] = v
            yuklenen += 1

    log_yaz(f"[Secrets] ENV fallback: {yuklenen} secret yuklendi", "INFO")
    return True


# ── Ana Yukleyici ─────────────────────────────────────────────


def secrets_yukle(zorla: bool = False) -> str:
    """
    Secret'lari Doppler → Vault → ENV zinciriyle yukle.

    Returns:
        Kullanilan kaynak adi (doppler/vault/env)
    """
    global _kaynak

    if _cache and not zorla:
        return _kaynak

    # 1. Doppler dene
    if _doppler_yukle():
        _kaynak = SecretKaynagi.DOPPLER
        return _kaynak

    # 2. Vault dene
    if _vault_yukle():
        _kaynak = SecretKaynagi.VAULT
        return _kaynak

    # 3. ENV fallback
    _env_yukle()
    _kaynak = SecretKaynagi.ENV
    return _kaynak


def secret_al(anahtar: str, varsayilan: str = "") -> str:
    """
    Secret degerini doner.

    Oncelik: cache → os.environ → varsayilan

    Kullanim:
        token = secret_al("TELEGRAM_TOKEN")
        api_key = secret_al("GROQ_API_KEY")
    """
    if not _cache:
        secrets_yukle()

    return _cache.get(anahtar) or os.getenv(anahtar, varsayilan)


def secret_var_mi(anahtar: str) -> bool:
    """Secret tanimli ve dolu mu?"""
    return bool(secret_al(anahtar))


def secret_ozeti() -> dict:
    """
    Secret durumunu doner — /status komutundan cagrilabilir.
    Deger gostermez, sadece var/yok bilgisi.
    """
    if not _cache:
        secrets_yukle()

    kritikler = [
        "TELEGRAM_TOKEN",
        "GROQ_API_KEY",
        "ALLOWED_USER_IDS",
        "GEMINI_API_KEY",
        "VAULT_TOKEN",
        "REDIS_URL",
    ]
    return {
        "kaynak": _kaynak,
        "toplam_secret": len(_cache),
        "kritik_secretler": {k: "✅ Mevcut" if secret_var_mi(k) else "❌ Eksik" for k in kritikler},
    }


def _secret_dogrula():
    """
    Baslangicta kritik secretlerin varlıgını kontrol et.
    Eksik varsa uyari logla.
    """
    zorunlu = ["TELEGRAM_TOKEN", "GROQ_API_KEY"]
    eksikler = [k for k in zorunlu if not secret_var_mi(k)]
    if eksikler:
        log_yaz(f"[Secrets] UYARI: Zorunlu secretler eksik: {eksikler}", "ERROR")
    else:
        log_yaz("[Secrets] Tum zorunlu secretler mevcut", "INFO")
    return len(eksikler) == 0


# Modul yuklenince otomatik baslat
secrets_yukle()
_secret_dogrula()
