# apply_patch2.py
# Fix: NameError: egitim_store is not defined (telegram_bot.py)
# - Ensures: from egitim_store import EgitimStore
# - Ensures: egitim_store = EgitimStore()  (GLOBAL)
# - Prints confirmation

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

TARGET = Path(__file__).parent / "telegram_bot.py"

IMPORT_STMT = "from egitim_store import EgitimStore\n"
INIT_LINE = "egitim_store = EgitimStore()\n"


def backup(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_name(f"{path.stem}.bak_{ts}{path.suffix}")
    bak.write_bytes(path.read_bytes())
    return bak


def find_import_block_end(text: str) -> int:
    lines = text.splitlines(keepends=True)
    last = -1
    for i, ln in enumerate(lines[:300]):
        if re.match(r"^\s*(import\s+|from\s+)", ln):
            last = i
            continue
        if last != -1 and ln.strip() and not ln.lstrip().startswith("#"):
            break
    if last == -1:
        return 0
    return sum(len(x) for x in lines[: last + 1])


def ensure_import(text: str) -> str:
    if IMPORT_STMT in text:
        return text
    idx = find_import_block_end(text)
    return text[:idx] + IMPORT_STMT + text[idx:]


def ensure_init(text: str) -> str:
    if re.search(r"^\s*egitim_store\s*=\s*EgitimStore\(", text, flags=re.M):
        return text

    # place after imports, before any other code
    idx = find_import_block_end(text)
    block = (
        "\n# --- ASAMA 21 ENTERPRISE: Egitim Store (ChromaDB) ---\n"
        + INIT_LINE
        + "# --- /ASAMA 21 ENTERPRISE ---\n"
    )
    return text[:idx] + block + text[idx:]


def main():
    if not TARGET.exists():
        raise SystemExit(f"telegram_bot.py bulunamadı: {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")
    bak = backup(TARGET)

    text = ensure_import(text)
    text = ensure_init(text)

    TARGET.write_text(text, encoding="utf-8")

    # verify
    new_text = TARGET.read_text(encoding="utf-8", errors="replace")
    ok_import = "from egitim_store import EgitimStore" in new_text
    ok_init = re.search(r"^\s*egitim_store\s*=\s*EgitimStore\(", new_text, flags=re.M) is not None

    print("OK: Patch uygulandı.")
    print("Hedef:", TARGET.resolve())
    print("Yedek:", bak.name)
    print("Import OK:", ok_import)
    print("Init OK:", ok_init)
    print("Şimdi botu yeniden başlat: start_bot.bat")


if __name__ == "__main__":
    main()
