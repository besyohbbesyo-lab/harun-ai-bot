# apply_unicodedata_fix.py
# Fixes SyntaxError caused by misplaced "import unicodedata" (e.g., inside parenthesized import blocks)
# Usage (run in project folder):  python apply_unicodedata_fix.py
from __future__ import annotations

import re
from pathlib import Path

TARGET = Path("telegram_bot.py")


def strip_invisibles(s: str) -> str:
    # Remove common invisible / zero-width chars that can break parsing
    return (
        s.replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\u2060", "")
    )


def main():
    if not TARGET.exists():
        raise SystemExit(f"ERROR: {TARGET} not found in current folder.")

    raw_bytes = TARGET.read_bytes()
    # Decode forgivingly; remove BOM if present
    text = raw_bytes.decode("utf-8", errors="replace")
    text = strip_invisibles(text)

    lines = text.splitlines(True)  # keep newlines

    # Remove all occurrences of "import unicodedata"
    new_lines = []
    removed = 0
    for ln in lines:
        if re.match(r"^\s*import\s+unicodedata\s*$", ln.strip("\r\n")):
            removed += 1
            continue
        new_lines.append(ln)

    # Ensure file has a UTF-8 coding cookie at top (helps some editors)
    if new_lines:
        first = new_lines[0]
        if not first.startswith("# -*- coding: utf-8 -*-"):
            # Insert after shebang if present
            if first.startswith("#!") and len(new_lines) > 1:
                new_lines.insert(1, "# -*- coding: utf-8 -*-\n")
            else:
                new_lines.insert(0, "# -*- coding: utf-8 -*-\n")

    # Insert "import unicodedata" into the top-level import section
    insert_at = None
    for i, ln in enumerate(new_lines[:200]):  # only scan beginning
        # Find end of initial import block
        if re.match(r"^\s*(import|from)\s+\w+", ln):
            insert_at = i + 1
            continue
        # Stop at first non-import non-empty non-comment after imports start
        if insert_at is not None and ln.strip() and not ln.lstrip().startswith("#"):
            break

    if insert_at is None:
        # No imports found; put after coding line (and optional shebang)
        insert_at = 0
        if new_lines and new_lines[0].startswith("#!"):
            insert_at = 1
        if new_lines and "coding" in new_lines[0]:
            insert_at = max(insert_at, 1)

    # Avoid duplicate insertion if already present (we removed all, so safe)
    new_lines.insert(insert_at, "import unicodedata\n")

    fixed = "".join(new_lines)
    # Normalize newlines to \n; Windows will still read fine
    fixed = fixed.replace("\r\n", "\n").replace("\r", "\n")

    backup = TARGET.with_suffix(".py.bak_unicodedata")
    backup.write_bytes(raw_bytes)
    TARGET.write_text(fixed, encoding="utf-8")
    print("OK: Fix applied.")
    print(f"Backup: {backup.name}")
    print("Now restart: start_bot.bat")


if __name__ == "__main__":
    main()
