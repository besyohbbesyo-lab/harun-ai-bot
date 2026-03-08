# core/bot_init.py — S5-3: globals.py refactoring
# Sorumluluk: Bot servislerini ve AI motorunu baslat

from __future__ import annotations

from bot_config import CFG
from core.config import GROQ_API_KEY

# ── Groq Client ───────────────────────────────────────────────
groq_client = None
try:
    if GROQ_API_KEY:
        from groq import Groq

        groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"Groq client: Baslatilamadi ({e})")

# ── API Rotator ───────────────────────────────────────────────
from api_rotator import APIRotator, rotator


def normalize_provider(p: dict | None) -> dict:
    if not p:
        _groq = CFG.get("groq", {})
        return {
            "name": "Groq",
            "mode": "cloud",
            "api_key": "",
            "model": _groq.get("default_model", "llama-3.1-8b-instant"),
            "max_tokens": _groq.get("default_max_tokens", 2000),
        }
    p = dict(p)
    if "isim" in p and "name" not in p:
        p["name"] = p.pop("isim")
    if "mode" not in p:
        p["mode"] = "cloud"
    return p


def _safe_active_provider(rotator_obj) -> dict:
    if rotator_obj is None:
        return normalize_provider(None)
    if hasattr(rotator_obj, "aktif_provider_al"):
        return normalize_provider(rotator_obj.aktif_provider_al())
    if hasattr(rotator_obj, "get_active_provider"):
        return normalize_provider(rotator_obj.get_active_provider())
    return normalize_provider(None)


# ── Temel Servisler ───────────────────────────────────────────
from code_plugin import CodeRunner
from document_plugin import DocumentCreator
from memory_plugin import MemorySystem
from pc_control_plugin import PCControl
from pdf_plugin import PDFDownloader
from search_plugin import SearchEngine

pc = PCControl()
doc_creator = DocumentCreator()
search_engine = SearchEngine()
pdf_downloader = PDFDownloader()
code_runner = CodeRunner()
memory = MemorySystem()

# ── AEE — Otonom Evrim Motoru ─────────────────────────────────
from meta_supervisor import MetaSupervisor
from policy_engine import PolicyEngine
from prompt_evolution import PromptEvolution
from reward_system import RewardSystem
from strategy_manager import StrategyManager

policy = PolicyEngine()
reward_sys = RewardSystem()
strategy_mgr = StrategyManager()
supervisor = MetaSupervisor(policy, reward_sys)
prompt_evo = PromptEvolution()

# ── Egitim Sistemi ────────────────────────────────────────────
from egitim_store import EgitimStore

egitim_store = EgitimStore()

# ── Model Manager ─────────────────────────────────────────────
from gemini_provider import ask_deepseek, ask_gemini
from model_manager import ModelManager, model_mgr
