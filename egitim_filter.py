# egitim_filter.py - ASAMA 26: Eğitim Filtreleme Sistemi
# --------------------------------------------------------
# Amaç: EgitimStore dataset'ini "noise" (test/ping/komut/sistem ciktilari) ile kirletmemek.
# Mantık:
#   - Regex kara liste + whitelist (görev türü / minimal kalite şartları)
#   - Minimum uzunluk / anlamsız içerik / komut / sadece noktalama filtreleri
#   - İsteğe bağlı ENV ayarları ile ince ayar
#
# ENV:
#   EGITIM_FILTER_ENABLED=1/0
#   EGITIM_MIN_PROMPT_LEN=6
#   EGITIM_MIN_ANSWER_LEN=40
#   EGITIM_FILTER_DEBUG=1  (telegram_bot.py içinde print)
#
# Not: Bu modül async değildir; saf fonksiyonlar içerir.

from __future__ import annotations

import os
import re
from typing import Tuple


def _norm(s: str) -> str:
    s = (s or "").strip()
    # çoklu boşluğu sadeleştir
    s = re.sub(r"\s+", " ", s)
    return s


def _only_punct_or_emoji(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return True
    # harf/rakam yoksa (sadece noktalama/emoji/sembol)
    return re.search(r"[A-Za-z0-9ÇĞİÖŞÜçğıöşü]", s) is None


# Eğitim dataseti için "kesin dışla" komut/ping desenleri
_KOMUT_RE = re.compile(r"^\/[a-zA-Z0-9_]+(\s|$)")
_PING_SET = {
    "test",
    "ping",
    "deneme",
    "deneme1",
    "deneme 1",
    "ok",
    "tamam",
    "hmm",
    "hımm",
    "hmmm",
    "a",
    "aa",
    "aaa",
    ".",
    "..",
    "...",
    "!",
    "!!",
    "???",
    "??",
    "🙂",
    "😀",
}

# Prompt içinde geçerse genelde sistem/diagnostic anlamına gelir (slashsız yazılsa bile)
_DIAG_KEYWORDS = [
    "api_test",
    "api test",
    "rotator",
    "cooldown",
    "uptime",
    "status",
    "hafiza durumu",
    "egitim store",
    "egitim_incele",
    "egitim_onayla",
    "egitim_reddet",
    "egitim_export",
    "egitimrapor",
]

# Answer içinde geçerse çoğu zaman "sistem çıktısı / debug" veya "format blokları"
_ANSWER_BLOCKLIST_RE = re.compile(
    r"(\[Guncel Web Bilgisi\]|\[/Guncel Web Bilgisi\]|\[Hafiza\]|\[/Hafiza\])"
    r"|(\bconfidence\b|\bguven\b\s*[:=])"
    r"|(^Harun AI Bot Komutlari:)"
    r"|(\bGroq LLaMA\b.*Aktif)",
    re.IGNORECASE | re.MULTILINE,
)

# Görev türü whitelist (istersen genişlet)
_ALLOWED_GOREV_TURLERI = {"genel", "sohbet", "arastirma", "vision"}


def egitim_filtre_karar(prompt: str, answer: str, gorev_turu: str = "genel") -> tuple[bool, str]:
    """
    Doner: (gecer_mi, neden)
    """
    if os.getenv("EGITIM_FILTER_ENABLED", "1") != "1":
        return True, "filter_disabled"

    p = _norm(prompt)
    a = (answer or "").strip()

    # Görev türü whitelist
    if gorev_turu and gorev_turu not in _ALLOWED_GOREV_TURLERI:
        return False, f"gorev_turu_disli:{gorev_turu}"

    # Komut (slash) ise direkt dışla
    if _KOMUT_RE.match(p):
        return False, "komut_mesaji"

    # Çok kısa / anlamsız
    min_p = int(os.getenv("EGITIM_MIN_PROMPT_LEN", "6"))
    if len(p) < min_p:
        return False, f"prompt_kisa<{min_p}"

    if p.lower() in _PING_SET:
        return False, "ping_test"

    if _only_punct_or_emoji(p):
        return False, "anlamsiz_prompt"

    # Diagnostic kelimeler (slash olmasa bile)
    lp = p.lower()
    if any(k in lp for k in _DIAG_KEYWORDS):
        return False, "diagnostic_prompt"

    # Cevap minimum kalite
    min_a = int(os.getenv("EGITIM_MIN_ANSWER_LEN", "40"))
    if len(a) < min_a:
        return False, f"answer_kisa<{min_a}"

    # Cevapta sistem blokları vs.
    if _ANSWER_BLOCKLIST_RE.search(a):
        return False, "answer_blocklist"

    return True, "ok"


def egitim_filtreden_gecer_mi(prompt: str, answer: str, gorev_turu: str = "genel") -> bool:
    ok, _ = egitim_filtre_karar(prompt, answer, gorev_turu=gorev_turu)
    return ok


def egitim_filtre_ozet(prompt: str, answer: str, gorev_turu: str = "genel") -> str:
    ok, neden = egitim_filtre_karar(prompt, answer, gorev_turu=gorev_turu)
    p = _norm(prompt)
    a = (answer or "").strip()
    return f"ok={ok} neden={neden} prompt='{p[:60]}' answer_len={len(a)}"
