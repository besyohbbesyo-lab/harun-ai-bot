"""
telegram_bot.py otomatik bolucu — Sprint 1: Handler Refactoring
================================================================
Bu script orijinal telegram_bot.py'yi okur ve modullere boler.
Calistirmak icin: python split_telegram_bot.py

Olusturulan dosyalar:
  core/__init__.py
  core/globals.py       — Global nesneler, import'lar, config
  core/utils.py         — normalize_provider, log_yaz, son_dosyayi_bul
  services/__init__.py
  services/rag_service.py  — RAG yardimci fonksiyonlari
  services/chat_service.py — ask_groq, ask_llama_local, ask_ai, reward
  handlers/__init__.py
  handlers/admin.py     — start, help, status, guvenlik, selftest, egitim_*
  handlers/tool.py      — ara, pdf, kod, sunum, word, plan, hafiza, gonder, mkdir, mkfile
  handlers/pc.py        — ekran, tikla, yaz, tus, web, guncel, otomasyon
  handlers/message.py   — handle_message, sesli_mesaj, _yetki_kontrol, _onay_isle
  telegram_bot.py       — ince giris noktasi (main + handler kaydi)
"""

import os
import re
from pathlib import Path

# Orijinal dosyayi oku
KAYNAK = Path(__file__).parent / "telegram_bot_original.py"
if not KAYNAK.exists():
    KAYNAK = Path(__file__).parent / "telegram_bot.py"

with open(KAYNAK, encoding="utf-8") as f:
    lines = f.readlines()
    content = "".join(lines)

# ─── Fonksiyon sinirlarini bul ───


def fonksiyon_bul(isim):
    """Fonksiyonun baslangic ve bitis satirini bul."""
    pattern = rf"^(async )?def {isim}\("
    baslangic = None
    for i, line in enumerate(lines):
        if re.match(pattern, line):
            baslangic = i
            break
    if baslangic is None:
        print(f"  [!] Fonksiyon bulunamadi: {isim}")
        return None, None

    # indent seviyesine gore bitis bul
    indent = len(lines[baslangic]) - len(lines[baslangic].lstrip())
    bitis = baslangic + 1
    for i in range(baslangic + 1, len(lines)):
        line = lines[i]
        if line.strip() == "":
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= indent and line.strip() != "":
            # Yeni fonksiyon/class/global — burada biter
            bitis = i
            break
    else:
        bitis = len(lines)

    return baslangic, bitis


def fonksiyonlari_cikar(isimler):
    """Birden fazla fonksiyonu cikar ve birlestir."""
    parcalar = []
    for isim in isimler:
        bas, bit = fonksiyon_bul(isim)
        if bas is not None:
            parcalar.append("".join(lines[bas:bit]))
    return "\n".join(parcalar)


# ─── Dizin yapisi ───

os.makedirs("core", exist_ok=True)
os.makedirs("services", exist_ok=True)
os.makedirs("handlers", exist_ok=True)

# ─── 1. core/__init__.py ───
with open("core/__init__.py", "w", encoding="utf-8") as f:
    f.write("# core/__init__.py\n")
print("[OK] core/__init__.py")

# ─── 2. core/globals.py ───
# Satir 1-242 arasi: import'lar + global nesneler
globals_end = None
for i, line in enumerate(lines):
    if line.strip().startswith("def ask_groq("):
        globals_end = i
        break

globals_content = "".join(lines[:globals_end])

# _rag fonksiyonlarini kaldir (services'a tasindi)
rag_start = globals_content.find("# --- RAG v3 helpers")
rag_end = globals_content.find("# --- /RAG helpers ---")
if rag_start > 0 and rag_end > 0:
    rag_end_line = globals_content.index("\n", rag_end) + 1
    globals_content = globals_content[:rag_start] + globals_content[rag_end_line:]

with open("core/globals.py", "w", encoding="utf-8") as f:
    f.write("# core/globals.py - Tum global nesneler ve paylasilan durum\n")
    f.write("# Orijinal telegram_bot.py satirlari 1-242'den cikarildi\n\n")
    f.write(globals_content)
print(f"[OK] core/globals.py ({globals_end} satir)")

# ─── 3. core/utils.py ───
utils_fonksiyonlar = ["normalize_provider", "_safe_active_provider", "log_yaz", "son_dosyayi_bul"]
utils_content = fonksiyonlari_cikar(utils_fonksiyonlar)

with open("core/utils.py", "w", encoding="utf-8") as f:
    f.write("# core/utils.py - Yardimci fonksiyonlar\n")
    f.write("# normalize_provider, log_yaz, son_dosyayi_bul\n\n")
    f.write("# NOT: Bu fonksiyonlar core/globals.py icerisinde tanimli olan\n")
    f.write("# nesneleri kullanir. Import icin:\n")
    f.write("#   from core.globals import *\n\n")
    f.write(utils_content)
print("[OK] core/utils.py")

# ─── 4. services/__init__.py ───
with open("services/__init__.py", "w", encoding="utf-8") as f:
    f.write("# services/__init__.py\n")
print("[OK] services/__init__.py")

# ─── 5. services/rag_service.py ───
rag_fonksiyonlar = [
    "_rag_build_context",
    "_rag_wants_verbatim",
    "_rag_extract_section",
    "_rag_extract_usage",
    "_rag_get_source_label",
]
rag_content = fonksiyonlari_cikar(rag_fonksiyonlar)

with open("services/rag_service.py", "w", encoding="utf-8") as f:
    f.write("# services/rag_service.py - RAG yardimci fonksiyonlari\n\n")
    f.write("import re\n")
    f.write("from rag.retrieve import retrieve as rag_retrieve\n\n")
    f.write(rag_content)
print("[OK] services/rag_service.py")

# ─── 6. services/chat_service.py ───
chat_fonksiyonlar = [
    "ask_groq",
    "ask_llama_local",
    "guncel_bilgi_gerekli_mi",
    "web_aramasiyla_zenginlestir",
    "compute_reward_v2",
    "auto_moderation_suggest",
    "ask_ai",
]
chat_content = fonksiyonlari_cikar(chat_fonksiyonlar)

with open("services/chat_service.py", "w", encoding="utf-8") as f:
    f.write("# services/chat_service.py - AI yanit servisleri\n")
    f.write("# ask_groq, ask_llama_local, ask_ai, reward hesaplama\n\n")
    f.write("import re\n")
    f.write("import time\n")
    f.write("import json\n")
    f.write("import httpx\n")
    f.write("import asyncio\n")
    f.write("from datetime import datetime\n")
    f.write("from pathlib import Path\n")
    f.write("from groq import Groq\n\n")
    f.write("from core.globals import *\n")
    f.write("from core.utils import normalize_provider, _safe_active_provider, log_yaz\n")
    f.write("from services.rag_service import (\n")
    f.write("    _rag_build_context, _rag_wants_verbatim,\n")
    f.write("    _rag_extract_section, _rag_extract_usage, _rag_get_source_label\n")
    f.write(")\n\n")
    f.write(chat_content)
print("[OK] services/chat_service.py")

# ─── 7. handlers/__init__.py ───
with open("handlers/__init__.py", "w", encoding="utf-8") as f:
    f.write("# handlers/__init__.py\n")
print("[OK] handlers/__init__.py")

# ─── 8. handlers/admin.py ───
admin_fonksiyonlar = [
    "start",
    "help_command",
    "status_command",
    "guvenlik_command",
    "selftest_command",
    "api_test_command",
    "_tek_key_test",
    "api_command",
    "aee_command",
    "chat_command",
    "egitimrapor_command",
    "egitim_incele_command",
    "egitim_onayla_command",
    "egitim_reddet_command",
    "egitim_export_command",
    "egitim_stats_command",
    "finetuning_baslat",
]
admin_content = fonksiyonlari_cikar(admin_fonksiyonlar)

with open("handlers/admin.py", "w", encoding="utf-8") as f:
    f.write("# handlers/admin.py - Yonetim komutlari\n")
    f.write("# start, help, status, guvenlik, selftest, api, aee, egitim_*\n\n")
    f.write("import json\n")
    f.write("import asyncio\n")
    f.write("from datetime import datetime\n")
    f.write("from pathlib import Path\n")
    f.write("from telegram import Update\n")
    f.write("from telegram.ext import ContextTypes\n\n")
    f.write("from core.globals import *\n")
    f.write("from core.utils import log_yaz\n")
    f.write("from handlers.message import _yetki_kontrol\n\n")
    f.write(admin_content)
print("[OK] handlers/admin.py")

# ─── 9. handlers/tool.py ───
tool_fonksiyonlar = [
    "ara_command",
    "pdf_command",
    "kod_command",
    "sunum_command",
    "word_command",
    "plan_command",
    "hafiza_command",
    "hatirlat_command",
    "gonder_command",
    "mkdir_command",
    "mkfile_command",
    "open_command",
]
tool_content = fonksiyonlari_cikar(tool_fonksiyonlar)

with open("handlers/tool.py", "w", encoding="utf-8") as f:
    f.write("# handlers/tool.py - Arac komutlari\n")
    f.write("# ara, pdf, kod, sunum, word, plan, hafiza, gonder, mkdir, mkfile, open\n\n")
    f.write("import json\n")
    f.write("import asyncio\n")
    f.write("from datetime import datetime\n")
    f.write("from pathlib import Path\n")
    f.write("from telegram import Update\n")
    f.write("from telegram.ext import ContextTypes\n\n")
    f.write("from core.globals import *\n")
    f.write("from core.utils import log_yaz, son_dosyayi_bul\n")
    f.write("from services.chat_service import ask_ai\n")
    f.write("from handlers.message import _yetki_kontrol\n\n")
    f.write(tool_content)
print("[OK] handlers/tool.py")

# ─── 10. handlers/pc.py ───
pc_fonksiyonlar = [
    "ekran_command",
    "tikla_command",
    "yaz_command",
    "tus_command",
    "web_command",
    "guncel_command",
    "otomasyon_command",
]
pc_content = fonksiyonlari_cikar(pc_fonksiyonlar)

with open("handlers/pc.py", "w", encoding="utf-8") as f:
    f.write("# handlers/pc.py - PC kontrol komutlari\n")
    f.write("# ekran, tikla, yaz, tus, web, guncel, otomasyon\n\n")
    f.write("import json\n")
    f.write("import asyncio\n")
    f.write("from datetime import datetime\n")
    f.write("from pathlib import Path\n")
    f.write("from telegram import Update\n")
    f.write("from telegram.ext import ContextTypes\n\n")
    f.write("from core.globals import *\n")
    f.write("from core.utils import log_yaz\n")
    f.write("from services.chat_service import ask_ai\n")
    f.write("from handlers.message import _yetki_kontrol\n\n")
    f.write(pc_content)
print("[OK] handlers/pc.py")

# ─── 11. handlers/message.py ───
msg_fonksiyonlar = ["_yetki_kontrol", "_onay_isle", "handle_message", "sesli_mesaj_handler"]
msg_content = fonksiyonlari_cikar(msg_fonksiyonlar)

with open("handlers/message.py", "w", encoding="utf-8") as f:
    f.write("# handlers/message.py - Mesaj isleyiciler\n")
    f.write("# handle_message, sesli_mesaj_handler, _yetki_kontrol, _onay_isle\n\n")
    f.write("import os\n")
    f.write("import re\n")
    f.write("import json\n")
    f.write("import asyncio\n")
    f.write("from datetime import datetime\n")
    f.write("from pathlib import Path\n")
    f.write("from telegram import Update\n")
    f.write("from telegram.ext import ContextTypes\n\n")
    f.write("from core.globals import *\n")
    f.write("from core.utils import log_yaz\n")
    f.write(
        "from services.chat_service import ask_ai, compute_reward_v2, auto_moderation_suggest\n\n"
    )
    f.write(msg_content)
print("[OK] handlers/message.py")

# ─── 12. Yeni telegram_bot.py (ince giris noktasi) ───
main_bas, main_bit = fonksiyon_bul("main")
proaktif_bas, proaktif_bit = fonksiyon_bul("_proaktif_kontrol")
main_content = "".join(lines[main_bas:main_bit])
if proaktif_bas:
    proaktif_content = "".join(lines[proaktif_bas:proaktif_bit])
else:
    proaktif_content = ""

with open("telegram_bot_new.py", "w", encoding="utf-8") as f:
    f.write("# telegram_bot.py — Ince giris noktasi (Sprint 1 refactored)\n")
    f.write("# ============================================================\n")
    f.write("# Orijinal 2024 satirlik monolith 8 module bolundu:\n")
    f.write("#   core/globals.py       — Global nesneler, config\n")
    f.write("#   core/utils.py         — Yardimci fonksiyonlar\n")
    f.write("#   services/rag_service.py  — RAG yardimcilari\n")
    f.write("#   services/chat_service.py — AI yanit servisleri\n")
    f.write("#   handlers/admin.py     — Yonetim komutlari\n")
    f.write("#   handlers/tool.py      — Arac komutlari\n")
    f.write("#   handlers/pc.py        — PC kontrol komutlari\n")
    f.write("#   handlers/message.py   — Mesaj isleyiciler\n")
    f.write("# ============================================================\n\n")
    f.write("from datetime import datetime\n")
    f.write("from telegram import Update\n")
    f.write("from telegram.ext import Application, CommandHandler, MessageHandler, filters\n\n")
    f.write("from core.globals import *\n")
    f.write("from core.utils import log_yaz, set_log_dosyasi\n")
    f.write("from handlers.admin import (\n")
    f.write("    start, help_command, status_command, guvenlik_command,\n")
    f.write("    selftest_command, api_test_command, api_command, aee_command,\n")
    f.write("    chat_command, egitimrapor_command, egitim_incele_command,\n")
    f.write("    egitim_onayla_command, egitim_reddet_command,\n")
    f.write("    egitim_export_command, egitim_stats_command\n")
    f.write(")\n")
    f.write("from handlers.tool import (\n")
    f.write("    ara_command, pdf_command, kod_command, sunum_command,\n")
    f.write("    word_command, plan_command, hafiza_command, hatirlat_command,\n")
    f.write("    gonder_command, mkdir_command, mkfile_command, open_command\n")
    f.write(")\n")
    f.write("from handlers.pc import (\n")
    f.write("    ekran_command, tikla_command, yaz_command, tus_command,\n")
    f.write("    web_command, guncel_command, otomasyon_command\n")
    f.write(")\n")
    f.write("from handlers.message import handle_message, sesli_mesaj_handler\n\n")
    f.write("# LOG_DOSYASI'ni utils'e bildir\n")
    f.write("set_log_dosyasi(LOG_DOSYASI)\n\n")
    f.write(main_content)
    f.write("\n\nif __name__ == '__main__':\n    main()\n")
print("[OK] telegram_bot_new.py")

# ─── Ozet ───
print("\n" + "=" * 60)
print("PARCALAMA TAMAMLANDI")
print("=" * 60)
toplam_satir = 0
for d in ["core", "services", "handlers"]:
    for dosya in Path(d).glob("*.py"):
        with open(dosya) as df:
            n = sum(1 for _ in df)
        toplam_satir += n
        print(f"  {dosya}: {n} satir")
with open("telegram_bot_new.py") as df:
    n = sum(1 for _ in df)
toplam_satir += n
print(f"  telegram_bot_new.py: {n} satir")
print(f"\nToplam: {toplam_satir} satir (orijinal: {len(lines)})")
print("\nKullanim:")
print("  1. Orijinal telegram_bot.py'yi telegram_bot_original.py olarak yedekle")
print("  2. telegram_bot_new.py'yi telegram_bot.py olarak kopyala")
print("  3. core/, services/, handlers/ klasorlerini proje kokune tasi")
print("  4. python telegram_bot.py ile test et")
