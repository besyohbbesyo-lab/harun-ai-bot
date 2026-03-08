# globals.py — S5-3: Refactoring köprüsü
# Bu dosya artık sadece geriye dönük uyumluluk için var.
# Tüm içerik 4 modüle taşındı:
#   core/config.py       — TOKEN, GROQ_API_KEY, LOG_DOSYASI, log_yaz, uptime
#   core/state.py        — finetuning_onay_bekliyor, _son_yanit
#   core/plugins_init.py — ses_plugin, vision, otomasyon
#   core/bot_init.py     — groq_client, pc, memory, policy, rotator
#
# Mevcut import'lar kırmadan çalışmaya devam etsin diye:

# Diger sabit importlar (telegram_bot.py icin)
import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot_config import CFG
from core.bot_init import (
    _safe_active_provider,
    ask_deepseek,
    ask_gemini,
    code_runner,
    doc_creator,
    egitim_store,
    groq_client,
    memory,
    model_mgr,
    normalize_provider,
    pc,
    pdf_downloader,
    policy,
    prompt_evo,
    reward_sys,
    rotator,
    search_engine,
    strategy_mgr,
    supervisor,
)
from core.config import (
    BASE_DIR,
    BASLANGIC_ZAMANI,
    GROQ_API_KEY,
    LOG_DOSYASI,
    MASAUSTU,
    TOKEN,
    baslangic_zamanini_kaydet,
    log_yaz,
    son_dosyayi_bul,
    uptime_hesapla,
)
from core.plugins_init import (
    OTOMASYON_AKTIF,
    SES_AKTIF,
    VISION_AKTIF,
    otomasyon,
    ses_plugin,
    vision,
)
from core.state import (
    _son_yanit,
    finetuning_onay_bekliyor,
    son_yanit_al,
    son_yanit_kaydet,
    son_yanit_temizle,
)
from egitim_plugin import (
    bot_app_kaydet,
    egitim_command,
    egitim_onay_kontrol,
    otomatik_egitim_kontrol,
)
from egitim_toplayici import EgitimToplayici, egitim
from guvenlik import (
    KRITIK_KOMUTLAR,
    check_auth,
    guvenlik_ozeti,
    injection_kontrol,
    injection_logla,
    onay_al,
    onay_kaydet,
    onay_kontrol,
    onay_mesaji_olustur,
    onay_temizle,
    rate_limit_kontrol,
)
from memory_plugin import EpisodicMemory, ProceduralMemory
from planner_plugin import PlannerExecutor
from proaktif_zeka import (
    chat_id_kaydet,
    haftalik_rapor_gonder,
    kullanici_soru_kaydet,
    proaktif_oneri_gonder,
    sabah_ozeti_gonder,
)
from rag.retrieve import retrieve as rag_retrieve
from reward_system import (
    confidence_hesapla,
    confidence_metni_olustur,
    consistency_hesapla,
    consistency_kaydet,
    hata_siniflandir,
    soru_hash_olustur,
)
from test_suite import run_selftests, write_report
