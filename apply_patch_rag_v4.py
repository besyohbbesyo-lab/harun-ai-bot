#!/usr/bin/env python
# apply_patch_rag_v4.py
# Fix: In verbatim ('aynen') mode, return multiple chunks from the SAME source (e.g., prepare_dataset.py chunk 5 + 6)
# Also refreshes rag/retrieve.py with stronger file-specific prioritization (safe overwrite).
#
# Usage (Windows):
#   cd /d "C:\\Users\\PC\\Desktop\\python temelleri"
#   python apply_patch_rag_v4.py
#
from __future__ import annotations

import re
from pathlib import Path

PROJECT = Path(".")
BOT = PROJECT / "telegram_bot.py"
RETRIEVE = PROJECT / "rag" / "retrieve.py"

NEW_RETRIEVE = 'import json\nimport re\nfrom pathlib import Path\n\nROOT = Path(".")\nKB_PATH = ROOT / "rag" / "kb.jsonl"\nTOP_K_DEFAULT = 4\n\ndef normalize(s: str) -> str:\n    s = s.lower()\n    s = re.sub(r"[^a-z0-9_\\.]+", " ", s)\n    s = re.sub(r"\\s+", " ", s).strip()\n    return s\n\ndef load_kb():\n    if not KB_PATH.exists():\n        return []\n    rows = []\n    with KB_PATH.open("r", encoding="utf-8") as f:\n        for line in f:\n            if not line.strip():\n                continue\n            obj = json.loads(line)\n            rows.append({\n                "source": obj.get("source", "unknown"),\n                "text": obj.get("text", "")\n            })\n    return rows\n\ndef _extract_targets(query: str):\n    q = (query or "").lower()\n    targets = set()\n    for m in re.findall(r"[a-z0-9_]+\\.py", q):\n        targets.add(m)\n    for stem in ("prepare_dataset", "telegram_bot", "api_rotator", "retrieve", "build_kb"):\n        if stem in q:\n            targets.add(stem + ".py")\n            targets.add(stem)\n    return targets\n\ndef _hard_boost(query: str, row: dict) -> float:\n    q = (query or "").lower()\n    src = (row.get("source") or "").lower()\n    txt = (row.get("text") or "").lower()\n    boost = 0.0\n    targets = _extract_targets(q)\n\n    for t in targets:\n        if t.endswith(".py") and (t == src or t in src):\n            boost += 5.0\n        if t.endswith(".py") and t in txt:\n            boost += 2.5\n        if (not t.endswith(".py")) and t in src:\n            boost += 1.5\n        if (not t.endswith(".py")) and t in txt:\n            boost += 1.0\n\n    if "prepare_dataset" in q and ("prepare_dataset.py" == src or "prepare_dataset.py" in txt):\n        boost += 8.0\n\n    return boost\n\ndef try_load_semantic():\n    try:\n        from sentence_transformers import SentenceTransformer\n        import numpy as np\n        return SentenceTransformer, np\n    except Exception:\n        return None, None\n\ndef semantic_retrieve(query: str, kb_rows, top_k: int):\n    SentenceTransformer, np = try_load_semantic()\n    if SentenceTransformer is None:\n        return None\n\n    model = SentenceTransformer("all-MiniLM-L6-v2")\n    texts = [r["text"] for r in kb_rows]\n\n    q_emb = model.encode([query], normalize_embeddings=True)\n    t_emb = model.encode(texts, normalize_embeddings=True)\n\n    sims = (t_emb @ q_emb[0]).tolist()\n\n    scored = []\n    for sim, row in zip(sims, kb_rows):\n        sim2 = float(sim) + _hard_boost(query, row)\n        scored.append((sim2, row))\n\n    scored.sort(key=lambda x: x[0], reverse=True)\n    return scored[:top_k]\n\ndef simple_score(query, text):\n    q = normalize(query)\n    t = normalize(text)\n\n    q_words = set(q.split())\n    t_words = set(t.split())\n\n    score = len(q_words & t_words)\n\n    if "prepare_dataset" in q and "prepare_dataset" in t:\n        score += 10\n    if "prepare_dataset.py" in q and "prepare_dataset.py" in t:\n        score += 20\n    if len(q) >= 6 and q in t:\n        score += 5\n    return score\n\ndef fallback_retrieve(query, kb_rows, top_k):\n    scored = []\n    for row in kb_rows:\n        s = simple_score(query, row["text"]) + _hard_boost(query, row) * 10.0\n        scored.append((float(s), row))\n    scored.sort(key=lambda x: x[0], reverse=True)\n    return scored[:top_k]\n\ndef retrieve(query, top_k=TOP_K_DEFAULT):\n    kb = load_kb()\n    if not kb:\n        return []\n    sem = semantic_retrieve(query, kb, top_k)\n    if sem is not None:\n        return sem\n    return fallback_retrieve(query, kb, top_k)\n\nif __name__ == "__main__":\n    q = input("Soru: ").strip()\n    results = retrieve(q, top_k=4)\n    print("\\n--- BULUNAN PARCALAR ---\\n")\n    for score, row in results:\n        print(f"[score={score:.4f}] source={row[\'source\']}")\n        print(row["text"])\n        print("\\n---\\n")\n'


def patch_bot(text: str) -> str:
    pattern = r"(?ms)^\s*# --- RAG v3: KB injection / verbatim mode ---.*?^\s*# --- /RAG v3 ---\s*$"
    repl = '        # --- RAG v4: KB injection / verbatim mode (join same-source chunks) ---\n        try:\n            rag_enabled = (os.getenv("RAG_ENABLED", "1") or "1").strip() != "0"\n            if rag_enabled and gorev_turu in ("sohbet", "genel", "kod", "word", "sunum"):\n                ctx, hits = _rag_build_context(prompt, top_k=6)\n                if ctx and hits:\n                    def _join_same_source(hits_list, max_chunks=2):\n                        first = hits_list[0][1] if hits_list and hits_list[0] and hits_list[0][1] else {}\n                        src0 = (first.get("source") or "").strip()\n                        chunks = []\n                        for _score, _row in hits_list:\n                            if not _row:\n                                continue\n                            if (str(_row.get("source","")).strip() == src0):\n                                t = str(_row.get("text","")).strip()\n                                if t:\n                                    chunks.append(t)\n                            if len(chunks) >= max_chunks:\n                                break\n                        return "\\n\\n".join(chunks).strip()\n\n                    if _rag_wants_verbatim(prompt):\n                        ql = (prompt or "").lower()\n                        joined = _join_same_source(hits, max_chunks=2)  # <= IMPORTANT\n                        if ("kullanım" in ql) or ("kullanim" in ql):\n                            sec = _rag_extract_usage(joined) or _rag_extract_usage(ctx)\n                            if sec:\n                                return sec\n                        if joined:\n                            return joined\n\n                    # Normal mode: prepend KB context and force grounding\n                    prompt = (\n                        "[PROJE_KB]\\n" + ctx + "\\n[/PROJE_KB]\\n\\n"\n                        "KURALLAR:\\n"\n                        "- Cevabi PROJE_KB icindeki bilgilere dayandir.\\n"\n                        "- KB\'de yoksa uydurma; emin degilsen soyle.\\n"\n                        "- Soru \'aynen\' isterse KB\'den dogrudan alinti yap.\\n\\n"\n                        "SORU:\\n" + prompt\n                    )\n        except Exception:\n            pass\n        # --- /RAG v4 ---'
    if re.search(pattern, text):
        return re.sub(pattern, repl, text)
    return text


def main():
    if not BOT.exists():
        raise SystemExit("telegram_bot.py bulunamadi. Proje klasorunde calistir.")

    original = BOT.read_text(encoding="utf-8", errors="replace")
    updated = patch_bot(original)
    if updated == original:
        print("UYARI: RAG v3 blogu bulunamadi veya zaten guncel. Degisiklik yapilmadi.")
    else:
        BOT.write_text(updated, encoding="utf-8")
        print("OK: telegram_bot.py RAG v4 blogu guncellendi.")

    try:
        RETRIEVE.parent.mkdir(parents=True, exist_ok=True)
        RETRIEVE.write_text(NEW_RETRIEVE, encoding="utf-8")
        print("OK: rag/retrieve.py guncellendi.")
    except Exception as e:
        print(f"UYARI: rag/retrieve.py yazilamadi: {e}")

    print("Bitti. Botu yeniden baslatin: python telegram_bot.py")


if __name__ == "__main__":
    main()
