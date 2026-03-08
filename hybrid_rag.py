# hybrid_rag.py - S2-2: BM25 + Dense + RRF Fusion
# ============================================================
# ChromaDB dense arama + BM25 keyword arama + RRF birlestirme
# Ek: cross-encoder benzeri basit re-ranking
# ============================================================

import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────
# BM25 SKORLAMA
# ─────────────────────────────────────────────────────────────

# Turkce stop-words (yaygın, anlam tasimayan kelimeler)
STOP_WORDS = {
    "bir",
    "bu",
    "su",
    "o",
    "ve",
    "ile",
    "de",
    "da",
    "mi",
    "mu",
    "ne",
    "icin",
    "ama",
    "fakat",
    "ki",
    "gibi",
    "daha",
    "en",
    "var",
    "yok",
    "ben",
    "sen",
    "biz",
    "siz",
    "onlar",
    "olan",
    "olarak",
    "her",
    "cok",
    "az",
    "kadar",
    "sonra",
    "once",
    "ise",
    "ya",
    "hem",
    "veya",
    "eger",
    "zaten",
    "sadece",
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "and",
    "or",
    "but",
    "not",
    "with",
}


def _tokenize(text: str) -> list[str]:
    """Basit tokenizer: kucuk harf + alfanumerik parcala."""
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def bm25_skor(
    sorgu: str, belge: str, avg_dl: float = 100.0, k1: float = 1.5, b: float = 0.75
) -> float:
    """Tek bir belge icin BM25 skoru hesapla."""
    sorgu_tokens = _tokenize(sorgu)
    belge_tokens = _tokenize(belge)
    if not sorgu_tokens or not belge_tokens:
        return 0.0

    dl = len(belge_tokens)
    tf_counter = Counter(belge_tokens)
    skor = 0.0

    for token in sorgu_tokens:
        tf = tf_counter.get(token, 0)
        if tf == 0:
            continue
        # Basit IDF (log(2) sabit, tek belge icin)
        idf = math.log(2.0)
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * (dl / max(1, avg_dl)))
        skor += idf * (numerator / denominator)

    return skor


def bm25_batch(sorgu: str, belgeler: list[str]) -> list[float]:
    """Birden fazla belge icin BM25 skorlari hesapla."""
    if not belgeler:
        return []
    avg_dl = sum(len(_tokenize(b)) for b in belgeler) / max(1, len(belgeler))
    return [bm25_skor(sorgu, b, avg_dl=avg_dl) for b in belgeler]


# ─────────────────────────────────────────────────────────────
# RRF (Reciprocal Rank Fusion)
# ─────────────────────────────────────────────────────────────


def rrf_fusion(
    dense_ranking: list[tuple[str, float]],
    bm25_ranking: list[tuple[str, float]],
    k: int = 60,
    dense_agirlik: float = 0.6,
    bm25_agirlik: float = 0.4,
) -> list[tuple[str, float]]:
    """
    Dense ve BM25 siralamalarini RRF ile birlestir.

    dense_ranking: [(doc_id, skor), ...] — yuksek skor = iyi
    bm25_ranking:  [(doc_id, skor), ...] — yuksek skor = iyi
    k: RRF sabiti (varsayilan 60)

    Doner: [(doc_id, rrf_skor), ...] sirali
    """
    skorlar: dict[str, float] = {}

    # Dense RRF
    dense_sorted = sorted(dense_ranking, key=lambda x: x[1], reverse=True)
    for rank, (doc_id, _) in enumerate(dense_sorted, 1):
        skorlar[doc_id] = skorlar.get(doc_id, 0.0) + dense_agirlik / (k + rank)

    # BM25 RRF
    bm25_sorted = sorted(bm25_ranking, key=lambda x: x[1], reverse=True)
    for rank, (doc_id, _) in enumerate(bm25_sorted, 1):
        skorlar[doc_id] = skorlar.get(doc_id, 0.0) + bm25_agirlik / (k + rank)

    # Sirala
    sonuc = sorted(skorlar.items(), key=lambda x: x[1], reverse=True)
    return sonuc


# ─────────────────────────────────────────────────────────────
# CROSS-ENCODER BENZERI BASIT RE-RANKING
# ─────────────────────────────────────────────────────────────


def rerank_basit(
    sorgu: str, belgeler: list[tuple[str, str, float]], n: int = 3
) -> list[tuple[str, str, float]]:
    """
    Basit re-ranking: exact match bonus + uzunluk normalizasyonu.

    belgeler: [(doc_id, text, rrf_skor), ...]
    Doner: [(doc_id, text, final_skor), ...] en iyi n tanesi
    """
    sorgu_lower = sorgu.lower()
    sorgu_tokens = set(_tokenize(sorgu))

    skorlu = []
    for doc_id, text, rrf_skor in belgeler:
        text_lower = text.lower()

        # Exact phrase match bonus
        exact_bonus = 0.15 if sorgu_lower in text_lower else 0.0

        # Token coverage: sorgu kelimelerinin kaci belgede var?
        text_tokens = set(_tokenize(text))
        if sorgu_tokens:
            coverage = len(sorgu_tokens & text_tokens) / len(sorgu_tokens)
        else:
            coverage = 0.0

        # Uzunluk normalizasyonu (ne cok kisa ne cok uzun)
        uzunluk = len(text)
        uzunluk_bonus = 0.0
        if 50 < uzunluk < 500:
            uzunluk_bonus = 0.05
        elif uzunluk >= 500:
            uzunluk_bonus = 0.02

        final = rrf_skor + exact_bonus + coverage * 0.1 + uzunluk_bonus
        skorlu.append((doc_id, text, final))

    skorlu.sort(key=lambda x: x[2], reverse=True)
    return skorlu[:n]


# ─────────────────────────────────────────────────────────────
# ANA HYBRID ARAMA FONKSIYONU
# ─────────────────────────────────────────────────────────────


def hybrid_search(
    sorgu: str,
    dense_sonuclar: list[tuple[str, str, float, dict]],
    n: int = 3,
    dense_agirlik: float = 0.6,
    bm25_agirlik: float = 0.4,
) -> list[tuple[str, str, float]]:
    """
    ChromaDB dense sonuclarini BM25 ile zenginlestirip RRF ile birlestir.

    dense_sonuclar: [(doc_id, text, distance, metadata), ...]
                    ChromaDB'den gelen ham sonuclar

    Doner: [(doc_id, text, final_skor), ...] en iyi n tanesi
    """
    if not dense_sonuclar:
        return []

    # 1. Dense skorlari hazirla (distance -> similarity)
    dense_ranking = []
    doc_map = {}  # doc_id -> (text, metadata)
    belgeler = []

    for doc_id, text, distance, meta in dense_sonuclar:
        similarity = 1.0 / (1.0 + distance)
        dense_ranking.append((doc_id, similarity))
        doc_map[doc_id] = (text, meta)
        belgeler.append(text)

    # 2. BM25 skorlari hesapla
    bm25_skorlari = bm25_batch(sorgu, belgeler)
    bm25_ranking = []
    for i, (doc_id, _, _, _) in enumerate(dense_sonuclar):
        bm25_ranking.append((doc_id, bm25_skorlari[i]))

    # 3. RRF Fusion
    rrf_sonuc = rrf_fusion(
        dense_ranking, bm25_ranking, dense_agirlik=dense_agirlik, bm25_agirlik=bm25_agirlik
    )

    # 4. Re-ranking icin hazirla
    rerank_girdi = []
    for doc_id, rrf_skor in rrf_sonuc:
        text, meta = doc_map.get(doc_id, ("", {}))
        rerank_girdi.append((doc_id, text, rrf_skor))

    # 5. Basit re-ranking
    return rerank_basit(sorgu, rerank_girdi, n=n)
