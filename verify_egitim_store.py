# verify_egitim_store.py
# Bu script, egitim_store.py içinde "include" satırını gösterir.
# Amaç: doğru dosyanın (ids'siz) yüklendiğini saniyeler içinde doğrulamak.

import re
from pathlib import Path

p = Path(__file__).parent / "egitim_store.py"
txt = p.read_text(encoding="utf-8", errors="replace")

print("FILE:", p.resolve())
# show first 5 lines
print("HEAD:")
for i, ln in enumerate(txt.splitlines()[:8], 1):
    print(f"{i:02d}: {ln}")

print("\nINCLUDE LINES:")
for ln in txt.splitlines():
    if "include=" in ln and "get(" in ln:
        print("  ", ln.strip())

# hard check
bad = re.search(r'include\s*=\s*\[.*"ids".*\]', txt)
print("\nCHECK:", "FAIL (ids still present)" if bad else "OK (ids not present)")
