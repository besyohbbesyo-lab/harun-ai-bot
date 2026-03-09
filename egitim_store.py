# egitim_store.py - Enterprise Training Store (ChromaDB) + Approval Gate + Audit
# FIX2: remove include='ids' and add self-check helpers
# FIX (2026-02-26): ChromaDB Collection.get() 'include' param DOES NOT accept "ids".
# ids are returned by default; include should be subset of: documents, embeddings, metadatas, distances, uris, data.

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions

BASE_DIR = Path(__file__).parent.resolve()
AUDIT_FILE = BASE_DIR / "egitim_audit.jsonl"

REVIEW_BATCH_SIZE = int(
    os.getenv("EGITIM_REVIEW_BATCH", "50")
)  # Enterprise kuralı (ENV ile override)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _audit(action: str, actor: dict[str, Any], record_id: str | None = None, note: str = ""):
    try:
        row = {"ts": _now(), "action": action, "record_id": record_id, "actor": actor, "note": note}
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


class EgitimStore:
    """
    Ayrı bir ChromaDB koleksiyonu:
      - Koleksiyon: egitim_ornekleri
      - Status: NEW -> (50 olunca) PENDING_REVIEW -> APPROVED/REJECTED
      - Audit: egitim_audit.jsonl
    """

    def __init__(self, db_path: str | None = None):
        db_path = db_path or str(BASE_DIR / "memory_db")
        self.client = chromadb.PersistentClient(path=db_path)
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.col = self.client.get_or_create_collection(
            name="egitim_ornekleri", embedding_function=self.ef
        )

    def _doc_from_sample(self, prompt: str, answer: str) -> str:
        prompt = (prompt or "")[:2000]
        answer = (answer or "")[:2000]
        return f"PROMPT:\n{prompt}\n\nANSWER:\n{answer}"

    def kaydet_ornek(
        self,
        prompt: str,
        answer: str,
        gorev_turu: str,
        user_id: int,
        chat_id: int,
        basari: bool,
        smoothed_reward: float,
        extra: dict[str, Any] | None = None,
    ) -> str:
        rid = str(uuid.uuid4())
        meta = {
            "id": rid,
            "status": "NEW",
            "created_at": _now(),
            "gorev_turu": gorev_turu,
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "basari": 1 if basari else 0,
            "smoothed_reward": round(float(smoothed_reward), 4),
        }
        if extra:
            meta.update(extra)

        doc = self._doc_from_sample(prompt, answer)
        self.col.add(ids=[rid], documents=[doc], metadatas=[meta])
        return rid

    def listele(self, status: str = "PENDING_REVIEW", limit: int = 20) -> list[dict[str, Any]]:
        # NOTE: do NOT include "ids" in include. ids are returned by default.
        res = self.col.get(include=["metadatas", "documents"])
        metas = res.get("metadatas") or []
        docs = res.get("documents") or []
        ids = res.get("ids") or []

        rows = []
        for rid, m, d in zip(ids, metas, docs, strict=False):
            if status and m.get("status") != status:
                continue
            created = m.get("created_at", "")
            rows.append((created, rid, m, d))

        rows.sort(key=lambda x: x[0], reverse=True)

        out: list[dict[str, Any]] = []
        for _, rid, m, d in rows[: max(1, min(int(limit), 200))]:
            prompt_preview = ""
            try:
                if "PROMPT:\n" in d and "\n\nANSWER:\n" in d:
                    prompt_preview = d.split("PROMPT:\n", 1)[1].split("\n\nANSWER:\n", 1)[0].strip()
                    prompt_preview = prompt_preview.replace("\n", " ")[:120]
            except Exception:
                pass
            out.append(
                {
                    "id": rid,
                    "created_at": m.get("created_at"),
                    "gorev_turu": m.get("gorev_turu"),
                    "smoothed_reward": m.get("smoothed_reward"),
                    "status": m.get("status"),
                    "prompt_preview": prompt_preview,
                }
            )
        return out

    def status_degistir(
        self, rid: str, new_status: str, actor: dict[str, Any], note: str = ""
    ) -> dict[str, Any]:
        got = self.col.get(ids=[rid], include=["metadatas", "documents"])
        if not got.get("ids"):
            return {"ok": False, "error": "Kayıt bulunamadı", "id": rid}

        meta = (got["metadatas"] or [{}])[0]
        old = meta.get("status", "NEW")
        meta["status"] = new_status
        meta["review_ts"] = _now()
        meta["review_actor"] = actor.get("user_id")
        meta["review_note"] = (note or "")[:500]

        doc = (got["documents"] or [""])[0]
        self.col.update(ids=[rid], metadatas=[meta], documents=[doc])

        _audit("STATUS_CHANGE", actor, rid, f"{old}->{new_status} | {note}".strip())
        return {"ok": True, "id": rid, "old": old, "new": new_status}

    def gate_kontrol(self, actor: dict[str, Any] | None = None) -> dict[str, Any]:
        actor = actor or {"user_id": None, "username": "system"}
        res = self.col.get(include=["metadatas", "documents"])
        metas = res.get("metadatas") or []
        docs = res.get("documents") or []
        ids = res.get("ids") or []

        new_ids = [
            rid for rid, m in zip(ids, metas, strict=False) if m.get("status", "NEW") == "NEW"
        ]
        if len(new_ids) < REVIEW_BATCH_SIZE:
            return {
                "ok": True,
                "gated": False,
                "new_count": len(new_ids),
                "threshold": REVIEW_BATCH_SIZE,
            }

        update_ids, update_metas, update_docs = [], [], []
        for rid, m, d in zip(ids, metas, docs, strict=False):
            if m.get("status", "NEW") == "NEW":
                m["status"] = "PENDING_REVIEW"
                m["gate_ts"] = _now()
                update_ids.append(rid)
                update_metas.append(m)
                update_docs.append(d)

        if update_ids:
            self.col.update(ids=update_ids, metadatas=update_metas, documents=update_docs)

        _audit("GATE_TRIGGER", actor, None, f"NEW->PENDING_REVIEW for {len(update_ids)} record(s)")
        return {
            "ok": True,
            "gated": True,
            "new_count": len(new_ids),
            "threshold": REVIEW_BATCH_SIZE,
        }

    def stats(self) -> dict[str, int]:
        """Durum sayacı: NEW/PENDING_REVIEW/APPROVED/REJECTED"""
        res = self.col.get(include=["metadatas"])
        metas = res.get("metadatas") or []
        counts: dict[str, int] = {"NEW": 0, "PENDING_REVIEW": 0, "APPROVED": 0, "REJECTED": 0}
        for m in metas:
            st = (m or {}).get("status", "NEW")
            if st not in counts:
                counts[st] = 0
            counts[st] += 1
        counts["TOTAL"] = sum(v for k, v in counts.items() if k != "TOTAL")
        return counts

    def export_approved(self, out_path: str | None = None) -> dict[str, Any]:
        """APPROVED kayıtları JSONL olarak dışa aktarır. İki format üretir:
        - prompt/completion
        - chat messages (OpenAI tarzı)
        """
        out_dir = BASE_DIR
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pc_path = (
            Path(out_path)
            if out_path
            else (out_dir / f"finetuning_approved_{ts}.prompt_completion.jsonl")
        )
        msg_path = out_dir / f"finetuning_approved_{ts}.messages.jsonl"

        res = self.col.get(include=["metadatas", "documents"])
        metas = res.get("metadatas") or []
        docs = res.get("documents") or []
        ids = res.get("ids") or []

        approved = []
        for rid, m, d in zip(ids, metas, docs, strict=False):
            if (m or {}).get("status") != "APPROVED":
                continue
            approved.append((rid, m, d))

        if not approved:
            return {"ok": True, "count": 0, "prompt_completion": None, "messages": None}

        def parse_doc(d: str):
            prompt, answer = "", ""
            try:
                if "PROMPT:\n" in d and "\n\nANSWER:\n" in d:
                    prompt = d.split("PROMPT:\n", 1)[1].split("\n\nANSWER:\n", 1)[0]
                    answer = d.split("\n\nANSWER:\n", 1)[1]
                else:
                    prompt = d[:2000]
                    answer = ""
            except Exception:
                prompt = d[:2000]
                answer = ""
            return prompt.strip(), answer.strip()

        # prompt/completion
        with open(pc_path, "w", encoding="utf-8") as f:
            for rid, m, d in approved:
                prompt, answer = parse_doc(d or "")
                row = {"id": rid, "prompt": prompt, "completion": answer}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        # messages
        with open(msg_path, "w", encoding="utf-8") as f:
            for rid, m, d in approved:
                prompt, answer = parse_doc(d or "")
                row = {
                    "id": rid,
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": answer},
                    ],
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        return {
            "ok": True,
            "count": len(approved),
            "prompt_completion": str(pc_path),
            "messages": str(msg_path),
        }

    def listele_reward(
        self, status: str = "PENDING_REVIEW", limit: int = 20
    ) -> list[dict[str, Any]]:
        """Kayıtları reward'a göre (yüksekten düşüğe) listeler."""
        res = self.col.get(include=["metadatas", "documents"])
        metas = res.get("metadatas") or []
        docs = res.get("documents") or []
        ids = res.get("ids") or []

        rows = []
        for rid, m, d in zip(ids, metas, docs, strict=False):
            if status and (m or {}).get("status") != status:
                continue
            reward = float((m or {}).get("smoothed_reward", 0.0))
            created = (m or {}).get("created_at", "")
            rows.append((reward, created, rid, m, d))

        rows.sort(key=lambda x: x[0], reverse=True)

        out: list[dict[str, Any]] = []
        for reward, _, rid, m, d in rows[: max(1, min(int(limit), 200))]:
            prompt_preview = ""
            try:
                if "PROMPT:\n" in d and "\n\nANSWER:\n" in d:
                    prompt_preview = d.split("PROMPT:\n", 1)[1].split("\n\nANSWER:\n", 1)[0].strip()
                    prompt_preview = prompt_preview.replace("\n", " ")[:120]
            except Exception:
                pass
            out.append(
                {
                    "id": rid,
                    "created_at": (m or {}).get("created_at"),
                    "gorev_turu": (m or {}).get("gorev_turu"),
                    "smoothed_reward": round(float(reward), 4),
                    "status": (m or {}).get("status"),
                    "prompt_preview": prompt_preview,
                }
            )
        return out

    def rapor(self) -> dict[str, Any]:
        """Günlük rapor için özet metrikler.
        Not: ASAMA 27 ile metadata'ya reward_v1/reward_v2 yazılabilir.
        - smoothed_reward: artık çoğunlukla reward_v2 olarak kullanılır.
        """
        res = self.col.get(include=["metadatas"])
        metas = res.get("metadatas") or []

        counts: dict[str, int] = {}
        # v2 (primary)
        reward_sum: dict[str, float] = {}
        reward_n: dict[str, int] = {}
        # explicit v1/v2
        r1_sum: dict[str, float] = {}
        r1_n: dict[str, int] = {}
        r2_sum: dict[str, float] = {}
        r2_n: dict[str, int] = {}

        for m in metas:
            m = m or {}
            st = m.get("status", "NEW")
            counts[st] = counts.get(st, 0) + 1

            # primary reward (backward compat)
            try:
                r = float(m.get("smoothed_reward", 0.0))
            except Exception:
                r = 0.0
            reward_sum[st] = reward_sum.get(st, 0.0) + r
            reward_n[st] = reward_n.get(st, 0) + 1

            # v1/v2 explicit fields (if present)
            try:
                r1 = float(m.get("reward_v1")) if m.get("reward_v1") is not None else None
            except Exception:
                r1 = None
            try:
                r2 = float(m.get("reward_v2")) if m.get("reward_v2") is not None else None
            except Exception:
                r2 = None

            if r1 is not None:
                r1_sum[st] = r1_sum.get(st, 0.0) + r1
                r1_n[st] = r1_n.get(st, 0) + 1
            if r2 is not None:
                r2_sum[st] = r2_sum.get(st, 0.0) + r2
                r2_n[st] = r2_n.get(st, 0) + 1

        def avg(dsum: dict[str, float], dn: dict[str, int], st: str) -> float:
            n = dn.get(st, 0)
            return round((dsum.get(st, 0.0) / n), 4) if n else 0.0

        total = sum(counts.values())
        statuses = list(counts.keys())
        return {
            "counts": counts,
            "total": total,
            "avg_reward": {st: avg(reward_sum, reward_n, st) for st in statuses},
            "avg_reward_v1": {st: avg(r1_sum, r1_n, st) for st in statuses},
            "avg_reward_v2": {st: avg(r2_sum, r2_n, st) for st in statuses},
        }

    def onayla_toplu(self, n: int, actor: dict[str, Any], note: str = "bulk") -> dict[str, Any]:
        """En yüksek reward'lü n adet PENDING_REVIEW kaydını APPROVED yapar."""
        rows = self.listele_reward(status="PENDING_REVIEW", limit=max(1, n))
        approved = []
        for r in rows[:n]:
            rid = r["id"]
            self.status_degistir(rid, "APPROVED", actor, note=note)
            approved.append(rid)
        return {"ok": True, "approved": approved, "count": len(approved)}
