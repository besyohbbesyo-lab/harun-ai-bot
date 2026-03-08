import json
import re

from egitim_store import EgitimStore

NOISE_WORDS = {
    "test",
    "ping",
    "deneme",
    "asdf",
    "qwe",
    "hello",
    "merhaba",
    "selam",
    "123",
    "1234",
    "12345",
}


def parse_doc(doc):
    if not doc:
        return "", ""
    try:
        if "PROMPT:\n" in doc and "\n\nANSWER:\n" in doc:
            prompt = doc.split("PROMPT:\n", 1)[1].split("\n\nANSWER:\n", 1)[0]
            answer = doc.split("\n\nANSWER:\n", 1)[1]
        else:
            prompt, answer = doc, ""
    except Exception:
        prompt, answer = doc, ""
    return prompt.strip(), answer.strip()


def is_noise(prompt):
    p = (prompt or "").strip().lower()
    if not p:
        return True
    if p in NOISE_WORDS:
        return True
    if len(p) <= 4 and p.isalpha():
        return True
    return False


def repetition_score(text):
    toks = re.findall(r"\w+", (text or "").lower())
    if len(toks) < 20:
        return 0.0
    uniq = len(set(toks))
    ratio = uniq / max(1, len(toks))
    return max(0.0, min(1.0, 1.0 - ratio * 2.0))


def reward_v2(prompt, answer, meta):
    try:
        base = float(meta.get("smoothed_reward", 0.0))
    except Exception:
        base = 0.0

    base = max(0.0, min(1.0, base))

    noise = is_noise(prompt)
    rep = repetition_score(answer)

    quality_bonus = 0.1 if len(answer) >= 200 else 0.0
    noise_penalty = 0.65 if noise else 0.0
    repetition_penalty = rep * 0.25

    r = base + quality_bonus - noise_penalty - repetition_penalty
    r = max(0.0, min(1.0, r))

    if r >= 0.78:
        auto = "AUTO_APPROVE"
    elif r <= 0.38:
        auto = "AUTO_REJECT"
    else:
        auto = "MANUAL"

    dbg = {
        "base_reward_v1": round(base, 4),
        "noise": int(noise),
        "repetition": round(rep, 4),
        "auto_suggest": auto,
    }

    return round(r, 4), dbg


def main():
    store = EgitimStore()
    res = store.col.get(include=["metadatas", "documents"])
    metas = res.get("metadatas") or []
    docs = res.get("documents") or []
    ids = res.get("ids") or []

    if not ids:
        print("Kayıt yok.")
        return

    update_ids, update_metas, update_docs = [], [], []
    counts = {"AUTO_APPROVE": 0, "AUTO_REJECT": 0, "MANUAL": 0}

    for rid, m, d in zip(ids, metas, docs, strict=False):
        m = m or {}
        prompt, answer = parse_doc(d or "")
        r2, dbg = reward_v2(prompt, answer, m)

        try:
            v1 = float(m.get("smoothed_reward", 0.0))
        except Exception:
            v1 = 0.0

        m["reward_v1"] = round(v1, 4)
        m["reward_v2"] = r2
        m["auto_suggest"] = dbg["auto_suggest"]
        m["reward_dbg_json"] = json.dumps(dbg, ensure_ascii=False)
        m["smoothed_reward"] = r2

        counts[dbg["auto_suggest"]] += 1

        update_ids.append(rid)
        update_metas.append(m)
        update_docs.append(d)

    store.col.update(ids=update_ids, metadatas=update_metas, documents=update_docs)

    print("OK — reward_v2 re-calc tamamlandı.")
    print("Kayıt sayısı:", len(update_ids))
    print("AUTO_APPROVE:", counts["AUTO_APPROVE"])
    print("AUTO_REJECT:", counts["AUTO_REJECT"])
    print("MANUAL:", counts["MANUAL"])


if __name__ == "__main__":
    main()
