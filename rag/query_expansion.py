# rag/query_expansion.py — S6-3: Query Expansion/Rewriting
# Sorguyu 3 varyasyona genisletir → daha fazla alakali chunk
# ============================================================

from __future__ import annotations

import re
from collections.abc import Callable

# ── Kural tabanlı genişletme ──────────────────────────────────

# Türkçe → İngilizce teknik terim eşleştirme
TEKNIK_TERIMLER: dict[str, list[str]] = {
    "hafıza": ["memory", "bellek", "cache"],
    "bellek": ["memory", "hafıza", "cache"],
    "güvenlik": ["security", "guvenlik", "injection"],
    "hata": ["error", "exception", "hata", "bug"],
    "model": ["model", "llm", "ai", "yapay zeka"],
    "arama": ["search", "retrieve", "rag", "arama"],
    "veritabanı": ["database", "db", "chroma", "chromadb"],
    "dosya": ["file", "document", "pdf", "dosya"],
    "api": ["api", "endpoint", "groq", "gemini"],
    "log": ["log", "logging", "kayit", "audit"],
    "test": ["test", "pytest", "unit test"],
    "plugin": ["plugin", "modul", "module"],
    "yedek": ["backup", "yedek", "snapshot"],
    "metrik": ["metric", "prometheus", "grafana"],
    "mesaj": ["message", "telegram", "chat"],
    "kullanıcı": ["user", "kullanici", "uid"],
    "ayar": ["config", "configuration", "settings"],
    "komut": ["command", "cmd", "handler"],
}

# Soru kalıpları → anahtar kelime çıkarımı
SORU_KALIPLARI = [
    (r"nasıl\s+(.+?)(?:\?|$)", "nasil {0} kullanim ornegi"),
    (r"ne\s+(?:dir|nedir)\s+(.+)", "{0} tanimi aciklama"),
    (r"(.+?)\s+nedir", "{0} tanimi aciklama"),
    (r"(.+?)\s+nasıl\s+çalış", "{0} calisma mantigi mimari"),
    (r"(.+?)\s+hata", "{0} hata debug cozum"),
    (r"(.+?)\s+kurulum", "{0} kurulum setup install"),
]


def _teknik_genislet(sorgu: str) -> str:
    """Türkçe teknik terimleri İngilizce karşılıklarıyla zenginleştir."""
    sorgu_lower = sorgu.lower()
    ekler = []
    for terim, karsiliklar in TEKNIK_TERIMLER.items():
        if terim in sorgu_lower:
            ekler.extend(karsiliklar)
    if ekler:
        return sorgu + " " + " ".join(set(ekler))
    return sorgu


def _soru_kalibina_gore_genislet(sorgu: str) -> str:
    """Soru kalıplarını tespit edip odaklanmış arama sorgusuna çevir."""
    for kalip, sablon in SORU_KALIPLARI:
        m = re.search(kalip, sorgu, re.IGNORECASE)
        if m:
            return sablon.format(m.group(1).strip())
    return sorgu


def _kisalt(sorgu: str, maks: int = 10) -> str:
    """Uzun sorgudan anahtar kelimeleri çıkar."""
    kelimeler = sorgu.split()
    if len(kelimeler) <= maks:
        return sorgu
    # Stop words çıkar
    stop = {
        "ve",
        "veya",
        "ile",
        "bir",
        "bu",
        "şu",
        "da",
        "de",
        "mi",
        "mı",
        "mu",
        "mü",
        "için",
        "gibi",
        "kadar",
        "the",
        "and",
        "or",
        "is",
        "are",
        "what",
        "how",
        "why",
    }
    onemli = [k for k in kelimeler if k.lower() not in stop]
    return " ".join(onemli[:maks])


def query_genislet(sorgu: str, ai_fonksiyon: Callable | None = None) -> list[str]:
    """
    Sorguyu 3 varyasyona genişlet.

    Args:
        sorgu: Orijinal kullanıcı sorusu
        ai_fonksiyon: Opsiyonel — (sorgu: str) -> str imzalı AI fonksiyonu.
                      Verilirse 3. varyasyon AI tarafından üretilir.

    Returns:
        [orijinal, varyasyon1, varyasyon2, varyasyon3] — tekrarsız liste
    """
    varyasyonlar = [sorgu]

    # Varyasyon 1: Teknik terim genişletme
    v1 = _teknik_genislet(sorgu)
    if v1 != sorgu:
        varyasyonlar.append(v1)

    # Varyasyon 2: Soru kalıbı → odaklı arama
    v2 = _soru_kalibina_gore_genislet(sorgu)
    if v2 != sorgu and v2 not in varyasyonlar:
        varyasyonlar.append(v2)

    # Varyasyon 3: AI ile yeniden yazma (opsiyonel) veya kısaltma
    if ai_fonksiyon is not None:
        try:
            v3 = ai_fonksiyon(
                f"Bu soruyu RAG arama için farklı kelimelerle tek cümle olarak yeniden yaz "
                f"(sadece soruyu yaz, açıklama yapma): {sorgu}"
            )
            if v3 and v3 not in varyasyonlar:
                varyasyonlar.append(v3.strip())
        except Exception:
            pass
    else:
        v3 = _kisalt(sorgu)
        if v3 != sorgu and v3 not in varyasyonlar:
            varyasyonlar.append(v3)

    return varyasyonlar[:4]  # max 4 varyasyon (orijinal + 3)


def coklu_retrieve(
    sorgu: str, retrieve_fn: Callable, top_k: int = 6, ai_fonksiyon: Callable | None = None
) -> list:
    """
    Query expansion + çoklu retrieve → birleşik ve sıralı sonuçlar.

    Her varyasyon için retrieve çalıştırır, sonuçları birleştirir,
    tekrarları kaynak bazında filtreler.

    Kullanım:
        from rag.query_expansion import coklu_retrieve
        from rag.retrieve import retrieve
        hits = coklu_retrieve("hafıza sistemi nasıl çalışır?", retrieve)
    """
    varyasyonlar = query_genislet(sorgu, ai_fonksiyon)

    goruldu: set = set()
    birlesik: list = []

    for v in varyasyonlar:
        try:
            hits = retrieve_fn(v, top_k=top_k)
        except Exception:
            continue

        for score, row in hits:
            anahtar = (row.get("source", ""), row.get("chunk_index", 0))
            if anahtar not in goruldu:
                goruldu.add(anahtar)
                birlesik.append((score, row))

    # Skora göre sırala, top_k döndür
    birlesik.sort(key=lambda x: x[0], reverse=True)
    return birlesik[:top_k]
