import json
from pathlib import Path

ROOT = Path(".")

SOURCE_FILES = [
    ROOT / "PROJECT_STATE.json",
    ROOT / "RUNBOOK_CMD.md",
    ROOT / "NEXT_STEPS.md",
    ROOT / "NEW_CHAT_PROMPT.txt",
    ROOT / "README_INSTRUCTIONS.md",
    ROOT / "prepare_dataset.py",
    ROOT / "telegram_bot.py",
]

KB_PATH = ROOT / "rag" / "kb.jsonl"


def read_file(path):
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except:
        return ""


def chunk_text(text, max_chars=1200):
    chunks = []
    current = ""

    for line in text.split("\n"):
        if len(current) + len(line) + 1 <= max_chars:
            current += line + "\n"
        else:
            chunks.append(current.strip())
            current = line + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks


def main():
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0

    with KB_PATH.open("w", encoding="utf-8") as f_out:
        for file_path in SOURCE_FILES:
            content = read_file(file_path)
            if not content:
                continue

            chunks = chunk_text(content, max_chars=350)

            for chunk in chunks:
                record = {"source": file_path.name, "text": chunk}
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"Proje KB oluşturuldu. Toplam chunk: {total_chunks}")
    print(f"Yol: {KB_PATH}")


if __name__ == "__main__":
    main()
