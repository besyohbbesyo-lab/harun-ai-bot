import json
from pathlib import Path

ROOT = Path(".")
DATASET_PATH = ROOT / "dataset" / "train.jsonl"
KB_PATH = ROOT / "rag" / "kb.jsonl"


def extract_assistant_text(messages):
    texts = []
    for m in messages:
        if m.get("role") == "assistant" and isinstance(m.get("content"), str):
            texts.append(m["content"].strip())
    return "\n".join(texts)


def chunk_text(text, max_chars=900, min_chars=200):
    chunks = []
    current = ""

    for line in text.split("\n"):
        if len(current) + len(line) + 1 <= max_chars:
            current += line + "\n"
        else:
            if len(current.strip()) >= min_chars:
                chunks.append(current.strip())
            current = line + "\n"

    if len(current.strip()) >= min_chars:
        chunks.append(current.strip())

    return chunks


def main():
    if not DATASET_PATH.exists():
        print("dataset/train.jsonl bulunamadı.")
        return

    KB_PATH.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0

    with (
        DATASET_PATH.open("r", encoding="utf-8") as f_in,
        KB_PATH.open("w", encoding="utf-8") as f_out,
    ):
        for line in f_in:
            if not line.strip():
                continue

            obj = json.loads(line)
            messages = obj.get("messages", [])
            text = extract_assistant_text(messages)

            if not text:
                continue

            chunks = chunk_text(text)

            for chunk in chunks:
                record = {"text": chunk}
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"KB oluşturuldu. Toplam chunk: {total_chunks}")
    print(f"Yol: {KB_PATH}")


if __name__ == "__main__":
    main()
