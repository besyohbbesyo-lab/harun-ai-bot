# tests/conftest.py — Ortak pytest fixture'ları
# ============================================================

import sys
from pathlib import Path

# Proje kök dizinini Python path'e ekle
# (tests/ klasöründen bir üst dizin = proje kökü)
sys.path.insert(0, str(Path(__file__).parent.parent))
