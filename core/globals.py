# core/globals.py - Tum global nesneler ve paylasilan durum
# Orijinal telegram_bot.py satirlari 1-242'den cikarildi

# telegram_bot.py
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()  # .env dosyasindan ortam degiskenlerini yukle
import json
import re
import time
from datetime import datetime
from pathlib import Path

from groq import Groq
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from api_rotator import APIRotator, rotator
from bot_config import CFG
from code_plugin import CodeRunner
from document_plugin import DocumentCreator
from guvenlik import (
    KRITIK_KOMUTLAR,
    check_auth,  # ASAMA 15 + Whitelist
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
from log_utils import guvenli_log_yaz, maskele_pii
from memory_plugin import EpisodicMemory, MemorySystem, ProceduralMemory
from meta_supervisor import MetaSupervisor
from pc_control_plugin import PCControl
from pdf_plugin import PDFDownloader
from planner_plugin import PlannerExecutor
from policy_engine import PolicyEngine
from prompt_evolution import PromptEvolution
from rag.retrieve import retrieve as rag_retrieve
from reward_system import (
    RewardSystem,
    confidence_hesapla,
    confidence_metni_olustur,
    consistency_hesapla,
    consistency_kaydet,
    hata_siniflandir,
    soru_hash_olustur,
)
from search_plugin import SearchEngine
from strategy_manager import StrategyManager
from test_suite import run_selftests, write_report


def normalize_provider(p: dict | None) -> dict:
    """Provider sozlugunu canonical semaya donustur.
    Eski 'isim' anahtarini 'name' olarak normalize eder.
    Boylece KeyError riski ortadan kalkar."""
    if not p:
        _groq = CFG.get("groq", {})
        return {
            "name": "Groq",
            "mode": "cloud",
            "api_key": "",
            "model": _groq.get("default_model", "llama-3.1-8b-instant"),
            "max_tokens": _groq.get("default_max_tokens", 2000),
        }
    p = dict(p)  # kopya — orijinali bozma
    if "isim" in p and "name" not in p:
        p["name"] = p.pop("isim")
    if "mode" not in p:
        p["mode"] = "cloud"
    return p


def _safe_active_provider(rotator_obj):
    """
    Farkli api_rotator surumleriyle uyum icin:
    - aktif_provider_al()
    - get_active_provider()
    - active_provider
    Her zaman normalize_provider() ile canonical sema doner.
    """
    if rotator_obj is None:
        return normalize_provider(None)
    if hasattr(rotator_obj, "aktif_provider_al"):
        return normalize_provider(rotator_obj.aktif_provider_al())
    if hasattr(rotator_obj, "get_active_provider"):
        return normalize_provider(rotator_obj.get_active_provider())
    # en son fallback
    return normalize_provider(None)


from egitim_plugin import (
    bot_app_kaydet,
    egitim_command,
    egitim_onay_kontrol,
    otomatik_egitim_kontrol,
)
from egitim_store import EgitimStore
from egitim_toplayici import EgitimToplayici, egitim
from gemini_provider import ask_deepseek, ask_gemini
from model_manager import ModelManager, model_mgr
from pyautogui_plugin import OtomasyonPlugin

# Global EgitimStore instance (Asama 21 - Enterprise)
egitim_store = EgitimStore()
from proaktif_zeka import (
    chat_id_kaydet,
    haftalik_rapor_gonder,
    kullanici_soru_kaydet,  # ASAMA 19
    proaktif_oneri_gonder,
    sabah_ozeti_gonder,
)

# ASAMA 11: Sesli mesaj desteği
try:
    from ses_plugin import SesPlugin

    ses_plugin = SesPlugin(dil="tr-TR")
    SES_AKTIF = True
    print("Ses Plugin (Google STT): Aktif")
except Exception as e:
    ses_plugin = None
    SES_AKTIF = False
    print(f"Ses Plugin: Devre disi ({e})")

# ─────────────────────────────────────────────────────────────
# YAPILANDIRMA — .env dosyasindan okunur (bkz: .env.example)
# ─────────────────────────────────────────────────────────────
TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


def log_yaz(mesaj: str, seviye: str = "INFO"):
    """Bot loglarini PII maskeli ve rotation destekli yaz."""
    try:
        guvenli_log_yaz(mesaj, LOG_DOSYASI, seviye)
    except Exception:
        pass


# Dinamik base path - klasör nerede olursa olsun çalışır
BASE_DIR = Path(__file__).parent.resolve()
MASAUSTU = Path.home() / "Desktop"


def son_dosyayi_bul(desktop_dir: Path, ext: str, prefix: str | None = None) -> Path | None:
    """Desktop altında en yeni dosyayı bulur. prefix verilirse onunla başlayanları filtreler."""
    if not desktop_dir.exists():
        return None
    pat = f"{prefix}*.{ext}" if prefix else f"*.{ext}"
    dosyalar = list(desktop_dir.glob(pat))
    if not dosyalar:
        return None
    dosyalar.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dosyalar[0]


LOG_DOSYASI = BASE_DIR / "bot_log.txt"
BASLANGIC_ZAMANI = None


def baslangic_zamanini_kaydet():
    """Bot baslatilinca cagrilir — uptime takibi icin."""
    global BASLANGIC_ZAMANI
    BASLANGIC_ZAMANI = datetime.now()


def uptime_hesapla() -> str:
    """Uptime stringi doner — admin.py tarafindan kullanilir."""
    if BASLANGIC_ZAMANI is None:
        return "Bilinmiyor"
    gecen = datetime.now() - BASLANGIC_ZAMANI
    saat = int(gecen.total_seconds() // 3600)
    dakika = int((gecen.total_seconds() % 3600) // 60)
    return f"{saat} saat {dakika} dakika"


# ─────────────────────────────────────────────────────────────

# Vision - hata verirse bot yine de çalışır
try:
    from vision_plugin import VisionTool

    vision = VisionTool(model="llava")
    VISION_AKTIF = True
    print("Vision (LLaVA): Aktif")
except Exception as e:
    vision = None
    VISION_AKTIF = False
    print(f"Vision: Devre disi ({e})")

# Otomasyon - hata verirse bot yine de çalışır
try:
    otomasyon = OtomasyonPlugin()
    OTOMASYON_AKTIF = True
    print("Otomasyon (pyautogui): Aktif")
except Exception as e:
    otomasyon = None
    OTOMASYON_AKTIF = False
    print(f"Otomasyon: Devre disi ({e})")

# Global nesneler
pc = PCControl()
doc_creator = DocumentCreator()
search_engine = SearchEngine()
pdf_downloader = PDFDownloader()
code_runner = CodeRunner()
memory = MemorySystem()

# Groq client - key varsa oluştur
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

# AEE - Autonomous Evolution Engine
policy = PolicyEngine()
reward_sys = RewardSystem()
strategy_mgr = StrategyManager()
supervisor = MetaSupervisor(policy, reward_sys)
prompt_evo = PromptEvolution()

# Fine-tuning onay durumu
finetuning_onay_bekliyor = False

# ASAMA 8: Kullanici bazli son yanit takibi (memnuniyetsizlik tespiti)
# {user_id: {"soru": str, "yanit": str, "gorev_turu": str}}
_son_yanit: dict = {}

# ─────────────────────────────────────────────────────────────
# MODEL FONKSİYONLARI
# ─────────────────────────────────────────────────────────────
