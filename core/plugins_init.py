# core/plugins_init.py — S5-3: globals.py refactoring
# Sorumluluk: Opsiyonel plugin baslangici (lazy, hata toleranli)

from pyautogui_plugin import OtomasyonPlugin

# ── Ses Plugin ────────────────────────────────────────────────
ses_plugin = None
SES_AKTIF = False
try:
    from ses_plugin import SesPlugin

    ses_plugin = SesPlugin(dil="tr-TR")
    SES_AKTIF = True
    print("Ses Plugin (Google STT): Aktif")
except Exception as e:
    print(f"Ses Plugin: Devre disi ({e})")

# ── Vision Plugin ─────────────────────────────────────────────
vision = None
VISION_AKTIF = False
try:
    from vision_plugin import VisionTool

    vision = VisionTool(model="llava")
    VISION_AKTIF = True
    print("Vision (LLaVA): Aktif")
except Exception as e:
    print(f"Vision: Devre disi ({e})")

# ── Otomasyon Plugin ──────────────────────────────────────────
otomasyon = None
OTOMASYON_AKTIF = False
try:
    otomasyon = OtomasyonPlugin()
    OTOMASYON_AKTIF = True
    print("Otomasyon (pyautogui): Aktif")
except Exception as e:
    print(f"Otomasyon: Devre disi ({e})")
