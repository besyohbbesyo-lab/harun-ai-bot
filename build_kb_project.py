"""
build_kb_project.py
Proje KB'sini oluşturur.
- Tüm .py dosyalarını + önemli .md/.txt/.json dosyalarını indexler
- Akıllı chunk: fonksiyon/sınıf sınırlarında bölme, min 200 / max 1000 karakter
- Her chunk'a source, chunk_index, total_chunks bilgisi eklenir
"""

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(".")
KB_PATH = ROOT / "rag" / "kb.jsonl"

# İndexlenecek dosya/klasörler
INCLUDE_PATTERNS = [
    "*.py",  # tüm python dosyaları (root)
    "rag/*.py",  # rag klasörü
    "plugins/*.py",  # plugins
]

STATIC_FILES = [
    ROOT / "PROJECT_STATE.json",
    ROOT / "RUNBOOK_CMD.md",
    ROOT / "NEXT_STEPS.md",
    ROOT / "NEW_CHAT_PROMPT.txt",
    ROOT / "README_INSTRUCTIONS.md",
    ROOT / "ASAMA27_README.md",
]

# Bunları indexleme (çok büyük / alakasız)
EXCLUDE_NAMES = {
    "kb.jsonl",
    "finetuning_data.jsonl",
    "egitim_verisi.jsonl",
    "egitim_audit.jsonl",
    "hata_verisi.jsonl",
    "kullanici_soru_log.jsonl",
}

MAX_CHUNK = 1000
MIN_CHUNK = 150


def read_file(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def smart_chunk(text: str, source: str, max_chars=MAX_CHUNK):
    """
    Python dosyaları için fonksiyon/class sınırlarında böl.
    Diğerleri için paragraf sınırlarında böl.
    """
    chunks = []

    if source.endswith(".py"):
        # def / class sınırlarında böl
        lines = text.split("\n")
        current: Any = []
        current_len = 0

        for line in lines:
            is_boundary = re.match(r"^(def |class |async def )", line)

            if is_boundary and current_len >= MIN_CHUNK:
                chunk = "\n".join(current).strip()
                if chunk:
                    # Eğer çok uzunsa ikiye böl
                    if len(chunk) > max_chars:
                        for sub in _split_by_size(chunk, max_chars):
                            if sub.strip():
                                chunks.append(sub.strip())
                    else:
                        chunks.append(chunk)
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += len(line) + 1

        # Kalan
        if current:
            chunk = "\n".join(current).strip()
            if chunk:
                if len(chunk) > max_chars:
                    for sub in _split_by_size(chunk, max_chars):
                        if sub.strip():
                            chunks.append(sub.strip())
                else:
                    chunks.append(chunk)
    else:
        # Paragraf bazlı bölme
        paragraphs = re.split(r"\n{2,}", text)
        current: Any = ""  # type: ignore[no-redef]
        for para in paragraphs:
            if len(current) + len(para) + 2 <= max_chars:
                current = (current + "\n\n" + para).strip()
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = para.strip()
        if current.strip():
            chunks.append(current.strip())

    # Çok kısa chunk'ları bir öncekiyle birleştir
    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < MIN_CHUNK and len(merged[-1]) + len(c) < max_chars:
            merged[-1] = merged[-1] + "\n" + c
        else:
            merged.append(c)

    return merged


def _split_by_size(text: str, max_chars: int):
    """Uzun metni satır bazlı max_chars'a böl."""
    lines = text.split("\n")
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 <= max_chars:
            current += line + "\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            current = line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def collect_files():
    files = []
    seen = set()

    # Pattern bazlı topla
    for pattern in INCLUDE_PATTERNS:
        for p in sorted(ROOT.glob(pattern)):
            if p.name in EXCLUDE_NAMES:
                continue
            if p.name.startswith("apply_patch") or p.name.startswith("finetuning_approved"):
                continue
            if p.resolve() not in seen:
                seen.add(p.resolve())
                files.append(p)

    # Statik dosyalar
    for p in STATIC_FILES:
        if p.exists() and p.name not in EXCLUDE_NAMES and p.resolve() not in seen:
            seen.add(p.resolve())
            files.append(p)

    return files


def main():
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)

    files = collect_files()
    total_chunks = 0
    file_count = 0

    with KB_PATH.open("w", encoding="utf-8") as f_out:
        for file_path in files:
            content = read_file(file_path)
            if not content.strip():
                continue

            chunks = smart_chunk(content, file_path.name)
            if not chunks:
                continue

            file_count += 1
            for i, chunk in enumerate(chunks):
                record = {
                    "source": file_path.name,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "text": chunk,
                }
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

    print("Proje KB olusturuldu.")
    print(f"Dosya sayisi : {file_count}")
    print(f"Toplam chunk : {total_chunks}")
    print(f"Yol          : {KB_PATH}")


if __name__ == "__main__":
    main()
