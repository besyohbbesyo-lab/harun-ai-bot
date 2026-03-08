# apply_patch.py
# Bu script, mevcut telegram_bot.py dosyana Enterprise Aşama21 için gerekli
# import + global egitim_store tanımını otomatik ekler ve yedek alır.
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

TARGET = Path(__file__).parent / "telegram_bot.py"

IMPORT_LINE = "from egitim_store import EgitimStore\n"
INIT_BLOCK = "\n# --- ASAMA 21 ENTERPRISE: Egitim Store (ChromaDB) ---\negitim_store = EgitimStore()\n# --- /ASAMA 21 ENTERPRISE ---\n"


def die(msg: str):
    raise SystemExit(msg)


def backup(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_name(f"{path.stem}.bak_{ts}{path.suffix}")
    bak.write_bytes(path.read_bytes())
    return bak


def find_import_insertion_point(text: str) -> int:
    # Insert after the last import line near the top.
    lines = text.splitlines(keepends=True)
    last_import_idx = -1
    for i, ln in enumerate(lines[:250]):  # imports are usually early
        if re.match(r"^\s*(import\s+\w+|from\s+\w+(\.\w+)*\s+import\s+)", ln):
            last_import_idx = i
            continue
        # stop after we left import section (first non-import, non-empty after seeing imports)
        if last_import_idx != -1 and ln.strip() and not ln.lstrip().startswith("#"):
            break
    if last_import_idx == -1:
        return 0
    # insert right after last import line
    return sum(len(x) for x in lines[: last_import_idx + 1])


def has_egitim_store_init(text: str) -> bool:
    return re.search(r"^\s*egitim_store\s*=\s*EgitimStore\(", text, flags=re.M) is not None


def insert_init_block(text: str) -> str:
    # Prefer placing after other global singletons (memory/reward/policy), else after imports.
    if has_egitim_store_init(text):
        return text
    anchor_patterns = [
        r"^memory\s*=\s*MemorySystem\(",
        r"^reward_system\s*=\s*RewardSystem\(",
        r"^policy_engine\s*=\s*PolicyEngine\(",
    ]
    for pat in anchor_patterns:
        m = re.search(pat, text, flags=re.M)
        if m:
            # place after the line where anchor is defined
            # find end of that line
            line_end = text.find("\n", m.end())
            if line_end == -1:
                line_end = len(text)
            return text[: line_end + 1] + INIT_BLOCK + text[line_end + 1 :]
    # fallback: after imports
    idx = find_import_insertion_point(text)
    return text[:idx] + INIT_BLOCK + text[idx:]


def main():
    if not TARGET.exists():
        die(f"telegram_bot.py bulunamadı: {TARGET}")
    text = TARGET.read_text(encoding="utf-8", errors="replace")

    bak = backup(TARGET)

    if IMPORT_LINE not in text:
        idx = find_import_insertion_point(text)
        text = text[:idx] + IMPORT_LINE + text[idx:]

    text = insert_init_block(text)

    TARGET.write_text(text, encoding="utf-8")
    print("OK: Patch uygulandı.")
    print(f"Yedek: {bak.name}")
    print("Şimdi botu yeniden başlatın (start_bot.bat).")


if __name__ == "__main__":
    main()
