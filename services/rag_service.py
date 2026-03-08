# services/rag_service.py - RAG yardimci fonksiyonlari
# S2-2: Hybrid RAG entegrasyonu

import re


def _rag_build_context(query: str, top_k: int = 6):
    """Return (context_text, hits). Hybrid RAG kullanir."""
    try:
        from core.globals import memory

        hits_raw = memory.benzer_gorev_bul(query, n=top_k)
        if not hits_raw:
            return "", []
        # hits_raw: list[str] (belge metinleri)
        hits = [(1.0, {"source": "memory", "text": h, "chunk_index": ""}) for h in hits_raw]
    except Exception:
        hits = []
    if not hits:
        return "", []
    parts = []
    for score, row in hits:
        src = (row or {}).get("source", "unknown")
        txt = (row or {}).get("text", "")
        cidx = (row or {}).get("chunk_index", "")
        merged = (row or {}).get("merged", False)
        tag = (
            f"[source={src}"
            + (f" chunk={cidx}" if cidx != "" else "")
            + (" MERGED" if merged else "")
            + f" score={float(score):.3f}]"
        )
        parts.append(f"{tag}\n{txt}".strip())
    return "\n\n---\n\n".join(parts).strip(), hits


def _rag_wants_verbatim(q: str) -> bool:
    ql = (q or "").lower()
    return any(
        k in ql
        for k in ("aynen yaz", "kelimesi kelimesine", "verbatim", "tam metin", "aynen aktar")
    )


def _rag_extract_section(text: str, section: str):
    """KB chunk'tan belirli bir bolumu cikar."""
    if not text:
        return None
    pattern = r"(?is)(^|\n)\s*(" + re.escape(section) + r")\s*:\s*\n(.*?)(\n\s*\n\s*#|\Z)"
    m = re.search(pattern, text)
    if m:
        body = (m.group(3) or "").strip()
        head = (m.group(2) or section).strip() + ":"
        if body:
            return head + "\n" + body
    return None


def _rag_extract_usage(text: str):
    """Kullanim bolumunu cikar."""
    return _rag_extract_section(text, "Kullanim") or _rag_extract_section(text, "Kullan\u0131m")


def _rag_get_source_label(hits) -> str:
    """En iyi hit'in kaynak etiketini dondur."""
    if not hits:
        return ""
    try:
        _, row = hits[0]
        src = (row or {}).get("source", "")
        merged = (row or {}).get("merged", False)
        count = (row or {}).get("merged_count", 1)
        if src:
            label = f"\n\n\U0001f4ce Kaynak: `{src}`"
            if merged and count > 1:
                label += f" ({count} bolum birlestirildi)"
            return label
    except Exception:
        pass
    return ""
