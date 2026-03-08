"""
clean_dataset.py

Amaç:
- dataset/train.jsonl ve dataset/validation.jsonl içindeki "assistant" cevaplarına karışmış
  log / etiket / durum satırlarını temizlemek.
- Temizlenmiş dosyaları dataset_clean/ altına yazar.
- Orijinalleri silmez.

KULLANIM (Windows CMD):
  cd /d "C:/Users/PC/Desktop/python temelleri"
  python clean_dataset.py
"""

import json
import re
from pathlib import Path

ROOT = Path(".")
IN_DIR = ROOT / "dataset"
OUT_DIR = ROOT / "dataset_clean"

TRAILING_PATTERNS = [
    re.compile(r"\n?\s*\[\s*OK\s*\].*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\n?\s*\[\s*API\s*\].*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\n?\s*Lokal\s+Hata:.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\n?\s*G[uü]ven\s*:.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\n?\s*Tutarl[ıi]l[ıi]k\s*:.*$", re.IGNORECASE | re.DOTALL),
]

INLINE_SPLITS = [
    re.compile(r"\n\s*\[\s*OK\s*\]\s*.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\n\s*\[\s*API\s*\]\s*.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\n\s*Lokal\s+Hata:.*$", re.IGNORECASE | re.DOTALL),
]


def clean_text(s: str) -> str:
    if not s:
        return s
    s = s.replace("\u0000", "").replace("\r\n", "\n").replace("\r", "\n")
    for pat in INLINE_SPLITS:
        s = re.sub(pat, "", s)
    for pat in TRAILING_PATTERNS:
        s = re.sub(pat, "", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def clean_file(in_path: Path, out_path: Path):
    total = 0
    changed = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with in_path.open("r", encoding="utf-8") as f_in, out_path.open("w", encoding="utf-8") as f_out:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            total += 1
            obj = json.loads(line)
            msgs = obj.get("messages", [])

            for m in msgs:
                if m.get("role") == "assistant" and isinstance(m.get("content"), str):
                    before = m["content"]
                    after = clean_text(before)
                    if after != before:
                        changed += 1
                        m["content"] = after

            f_out.write(json.dumps(obj, ensure_ascii=False) + "\n")

    return total, changed


def main():
    train_in = IN_DIR / "train.jsonl"
    val_in = IN_DIR / "validation.jsonl"

    if not train_in.exists():
        print(f"HATA: Bulunamadı -> {train_in}")
        return
    if not val_in.exists():
        print(f"HATA: Bulunamadı -> {val_in}")
        return

    train_out = OUT_DIR / "train.jsonl"
    val_out = OUT_DIR / "validation.jsonl"

    t_total, t_changed = clean_file(train_in, train_out)
    v_total, v_changed = clean_file(val_in, val_out)

    print("OK — dataset temizlendi.")
    print(f"TRAIN: {t_total} satır, {t_changed} assistant mesajı temizlendi -> {train_out}")
    print(f"VALIDATION: {v_total} satır, {v_changed} assistant mesajı temizlendi -> {val_out}")
    print("Not: Orijinal dosyalar 'dataset/' içinde duruyor. Temizler 'dataset_clean/' içinde.")


if __name__ == "__main__":
    main()
