"""
retrieve.py — RAG retrieval + Cross-Encoder Re-ranking
S6-1: cross-encoder/ms-marco-MiniLM-L-6-v2 entegrasyonu
- Semantic (sentence-transformers) + keyword fallback
- Cross-Encoder ile top-10 → top-k re-ranking
- Hard boost: dosya adı eşleşmesi
- chunk_index bilgisiyle aynı source'tan ardışık chunk birleştirme
- Döndürülen row: {source, chunk_index, total_chunks, text}
"""

import json
import re
from pathlib import Path

ROOT = Path(".")
KB_PATH = ROOT / "rag" / "kb.jsonl"
TOP_K_DEFAULT = 6
CROSS_ENC_CANDIDATE = 10  # Cross-Encoder öncesi aday sayısı


def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9_\.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_kb():
    if not KB_PATH.exists():
        return []
    rows = []
    with KB_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            rows.append(
                {
                    "source": obj.get("source", "unknown"),
                    "chunk_index": obj.get("chunk_index", 0),
                    "total_chunks": obj.get("total_chunks", 1),
                    "text": obj.get("text", ""),
                }
            )
    return rows


# ── Hedef dosya çıkarımı ──────────────────────────────────────
def _extract_targets(query: str):
    q = (query or "").lower()
    targets = set()
    for m in re.findall(r"[a-z0-9_]+\.py", q):
        targets.add(m)
    STEMS = [
        "prepare_dataset",
        "telegram_bot",
        "api_rotator",
        "retrieve",
        "build_kb",
        "memory_plugin",
        "pdf_plugin",
        "vision_plugin",
        "search_plugin",
        "ses_plugin",
        "planner_plugin",
        "pc_control",
        "policy_engine",
        "policy_state",
        "reward_system",
        "reward_history",
        "strategy_manager",
        "strategy_data",
        "model_manager",
        "model_perf",
        "meta_supervisor",
        "proaktif",
        "guvenlik",
        "start_bot",
    ]
    for stem in STEMS:
        if stem in q:
            targets.add(stem + ".py")
            targets.add(stem)
    return targets


# ── Hard boost ────────────────────────────────────────────────
def _hard_boost(query: str, row: dict) -> float:
    q = (query or "").lower()
    src = (row.get("source") or "").lower()
    txt = (row.get("text") or "").lower()
    boost = 0.0
    targets = _extract_targets(q)

    for t in targets:
        if t.endswith(".py"):
            if t == src or src.endswith(t):
                boost += 6.0
            if t in txt:
                boost += 2.0
        else:
            if t in src:
                boost += 2.0
            if t in txt:
                boost += 1.0

    SECTION_KEYWORDS = {
        "kullanım": ["kullanım", "kullanim", "usage", "nasıl kullanılır"],
        "kurulum": ["kurulum", "install", "setup"],
        "açıklama": ["açıklama", "description", "nedir"],
    }
    for section, kws in SECTION_KEYWORDS.items():
        if any(k in q for k in kws):
            if any(k in txt for k in kws):
                boost += 3.0

    return boost


# ── Cross-Encoder Re-ranking (S6-1) ──────────────────────────
_CE_MODEL = None
_CE_AKTIF = False


def _cross_encoder_yukle():
    """Cross-Encoder modelini lazy-load et."""
    global _CE_MODEL, _CE_AKTIF
    if _CE_AKTIF:
        return True
    try:
        from sentence_transformers import CrossEncoder

        _CE_MODEL = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        _CE_AKTIF = True
        print("[CrossEncoder] ms-marco-MiniLM-L-6-v2 yuklendi")
        return True
    except Exception as e:
        print(f"[CrossEncoder] Yuklenemedi, devre disi: {e}")
        return False


def cross_encoder_rerank(query: str, hits: list, top_k: int) -> list:
    """
    Cross-Encoder ile hits listesini yeniden sırala.
    hits: [(score, row), ...]
    Döner: [(yeni_score, row), ...] top_k adet
    """
    if not _cross_encoder_yukle() or not hits:
        return hits[:top_k]

    try:
        pairs = [(query, row["text"][:512]) for _, row in hits]
        scores = _CE_MODEL.predict(pairs)
        reranked = sorted(
            zip(scores, [row for _, row in hits], strict=False), key=lambda x: x[0], reverse=True
        )
        return [(float(s), row) for s, row in reranked[:top_k]]
    except Exception as e:
        print(f"[CrossEncoder] Re-ranking hatasi, fallback: {e}")
        return hits[:top_k]


# ── Semantic retrieval ────────────────────────────────────────
def try_load_semantic():
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer, np
    except Exception:
        return None, None


_SEM_MODEL = None


def semantic_retrieve(query: str, kb_rows, top_k: int):
    global _SEM_MODEL
    SentenceTransformer, np = try_load_semantic()
    if SentenceTransformer is None:
        return None

    if _SEM_MODEL is None:
        _SEM_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [r["text"] for r in kb_rows]
    q_emb = _SEM_MODEL.encode([query], normalize_embeddings=True)
    t_emb = _SEM_MODEL.encode(texts, normalize_embeddings=True)
    sims = (t_emb @ q_emb[0]).tolist()

    scored = []
    for sim, row in zip(sims, kb_rows, strict=False):
        final = float(sim) + _hard_boost(query, row)
        scored.append((final, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


# ── Keyword fallback ──────────────────────────────────────────
def simple_score(query: str, text: str) -> float:
    q = normalize(query)
    t = normalize(text)
    q_words = set(q.split())
    t_words = set(t.split())
    score = float(len(q_words & t_words))
    if len(q) >= 6 and q in t:
        score += 5.0
    return score


def fallback_retrieve(query: str, kb_rows, top_k: int):
    scored = []
    for row in kb_rows:
        s = simple_score(query, row["text"]) + _hard_boost(query, row) * 10.0
        scored.append((s, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


# ── Ardışık chunk birleştirici ────────────────────────────────
def merge_consecutive_chunks(hits, max_chunks=3):
    if not hits:
        return hits

    best_score, best_row = hits[0]
    src = best_row.get("source", "")
    base_idx = best_row.get("chunk_index", 0)

    kb = load_kb()
    result_texts = []
    collected_indices = set()

    for offset in range(max_chunks):
        target_idx = base_idx + offset
        for row in kb:
            if row.get("source") == src and row.get("chunk_index") == target_idx:
                if target_idx not in collected_indices:
                    result_texts.append(row["text"])
                    collected_indices.add(target_idx)
                break

    if len(result_texts) <= 1:
        return hits

    merged_text = "\n\n".join(result_texts).strip()
    merged_row = {
        "source": src,
        "chunk_index": base_idx,
        "total_chunks": best_row.get("total_chunks", 1),
        "text": merged_text,
        "merged": True,
        "merged_count": len(result_texts),
    }

    new_hits = [(best_score + 1.0, merged_row)]
    for score, row in hits[1:]:
        if row.get("source") != src:
            new_hits.append((score, row))

    return new_hits


# ── Ana retrieve ──────────────────────────────────────────────
def retrieve(query: str, top_k: int = TOP_K_DEFAULT, query_expansion: bool = True):
    """
    RAG retrieve — S6-3: Query expansion destekli.
    query_expansion=True ise sorgu 3 varyasyona genisletilir.
    """

    kb = load_kb()
    if not kb:
        return []

    # S6-3: Query expansion — birden fazla varyasyonla arama
    if query_expansion:
        try:
            from rag.query_expansion import query_genislet

            varyasyonlar = query_genislet(query)
        except Exception:
            varyasyonlar = [query]
    else:
        varyasyonlar = [query]

    # 1. Her varyasyon için semantic/keyword retrieve
    goruldu: set = set()
    candidate_hits: list = []
    candidate_k = max(CROSS_ENC_CANDIDATE, top_k * 2)

    for v in varyasyonlar:
        sem = semantic_retrieve(v, kb, candidate_k)
        v_hits = sem if sem is not None else fallback_retrieve(v, kb, candidate_k)
        for score, row in v_hits:
            anahtar = (row.get("source", ""), row.get("chunk_index", 0))
            if anahtar not in goruldu:
                goruldu.add(anahtar)
                candidate_hits.append((score, row))

    candidate_hits.sort(key=lambda x: x[0], reverse=True)
    hits = candidate_hits[:candidate_k]

    # 2. Cross-Encoder re-ranking (S6-1)
    hits = cross_encoder_rerank(query, hits, top_k)

    # 3. Verbatim sorgularda ardışık chunk birleştir
    q_lower = (query or "").lower()
    verbatim_keywords = (
        "aynen",
        "kelimesi kelimesine",
        "verbatim",
        "tam metin",
        "aynen aktar",
        "kullanım",
    )
    if any(k in q_lower for k in verbatim_keywords):
        hits = merge_consecutive_chunks(hits, max_chunks=3)

    return hits


if __name__ == "__main__":
    q = input("Soru: ").strip()
    results = retrieve(q, top_k=6)
    print("\n--- BULUNAN PARCALAR ---\n")
    for score, row in results:
        merged_info = (
            f" [BİRLEŞTİRİLDİ: {row.get('merged_count', 1)} chunk]" if row.get("merged") else ""
        )
        print(
            f"[score={score:.4f}] source={row['source']} "
            f"chunk={row.get('chunk_index','?')}{merged_info}"
        )
        print(row["text"][:500])
        print("\n---\n")
