"""
Harun AI — Proje Durum Tarayıcısı
Çalıştır: python status_raporu.py
Çıktıyı kopyalayıp Claude'a yapıştır.
"""

import ast
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent
SEP = "=" * 60


def dosya_var(ad):
    return (BASE / ad).exists()


def satir_say(ad):
    p = BASE / ad
    if not p.exists():
        return 0
    try:
        return len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
    except:
        return -1


def icerik_ara(dosya, aranacaklar):
    p = BASE / dosya
    if not p.exists():
        return {}
    try:
        metin = p.read_text(encoding="utf-8", errors="ignore")
        return {a: (a in metin) for a in aranacaklar}
    except:
        return {}


def klasor_listele(klasor):
    p = BASE / klasor
    if not p.exists():
        return []
    return [f.name for f in p.iterdir()]


print(SEP)
print("HARUN AI — PROJE DURUM RAPORU")
print(f"Dizin: {BASE}")
print(SEP)

# ── 1. KRİTİK DOSYALAR ──────────────────────────────────────
print("\n[1] KRİTİK DOSYALAR")
kritik = [
    "telegram_bot.py",
    "guvenlik.py",
    "api_rotator.py",
    "model_manager.py",
    "bot_config.py",
    "config.yaml",
    "log_utils.py",
    "requirements.txt",
    ".env.example",
    "Dockerfile",
    "docker-compose.yml",
]
for d in kritik:
    var = "✅" if dosya_var(d) else "❌"
    satir = satir_say(d)
    satir_str = f"({satir} satır)" if satir > 0 else ""
    print(f"  {var} {d} {satir_str}")

# ── 2. SPRINT 0 KONTROL ──────────────────────────────────────
print("\n[2] SPRINT 0 — GÜVENLİK")
s0 = {
    "guvenlik.py": ["RISK_CLASSES", "critical_confirm", "token_hex", "OTP", "otp_"],
    "code_plugin.py": ["network_mode", "mem_limit", "cpu_quota", "no-new-privileges", "read_only"],
    "Dockerfile": ["nonroot", "harun", "multi-stage", "AS builder", "HEALTHCHECK"],
}
for dosya, aranacaklar in s0.items():
    print(f"\n  📄 {dosya} ({satir_say(dosya)} satır):")
    sonuclar = icerik_ara(dosya, aranacaklar)
    for a, var in sonuclar.items():
        print(f"    {'✅' if var else '❌'} {a}")

# ── 3. SPRINT 1 KONTROL ──────────────────────────────────────
print("\n[3] SPRINT 1 — MİMARİ")
s1_dosyalar = [
    "core/resilience.py",
    "core/schemas.py",
    "core/models/provider_rotator.py",
    "handlers/admin.py",
    "handlers/ai.py",
    "handlers/tool.py",
    "handlers/pc.py",
    "services/chat_service.py",
    "services/memory_service.py",
    "services/model_service.py",
    "split_telegram_bot.py",
    "docker-compose.yml",
]
for d in s1_dosyalar:
    var = "✅" if dosya_var(d) else "❌"
    satir = satir_say(d)
    satir_str = f"({satir} satır)" if satir > 0 else ""
    print(f"  {var} {d} {satir_str}")

s1_kontrol = {
    "api_rotator.py": ["CircuitBreaker", "CLOSED", "OPEN", "HALF_OPEN", "tenacity"],
    "core/resilience.py": ["CircuitBreaker", "CLOSED", "OPEN"],
}
for dosya, aranacaklar in s1_kontrol.items():
    sonuclar = icerik_ara(dosya, aranacaklar)
    if any(sonuclar.values()):
        print(f"\n  📄 {dosya} içinde bulunanlar:")
        for a, var in sonuclar.items():
            if var:
                print(f"    ✅ {a}")

# ── 4. SPRINT 2 KONTROL ──────────────────────────────────────
print("\n[4] SPRINT 2 — HAFIZA & RAG")
s2_dosyalar = [
    "hybrid_rag.py",
    "token_budget.py",
    "token_budget_log.py",
    "memory_plugin.py",
    "etm_buffer.py",
    "core/memory/hierarchical_memory.py",
    "rag/hybrid_retriever.py",
    "tests/test_security.py",
]
for d in s2_dosyalar:
    var = "✅" if dosya_var(d) else "❌"
    satir = satir_say(d)
    satir_str = f"({satir} satır)" if satir > 0 else ""
    print(f"  {var} {d} {satir_str}")

s2_kontrol = {
    "hybrid_rag.py": ["BM25", "RRF", "CrossEncoder", "rank_bm25"],
    "token_budget.py": ["DAILY_LIMIT", "consume", "report", "reset"],
    "memory_plugin.py": ["stm", "etm", "ltm", "STM", "ETM", "LTM", "decay"],
}
for dosya, aranacaklar in s2_kontrol.items():
    sonuclar = icerik_ara(dosya, aranacaklar)
    bulunanlar = [a for a, v in sonuclar.items() if v]
    if bulunanlar:
        print(f"\n  📄 {dosya} — bulundu: {bulunanlar}")
    else:
        eksik = list(sonuclar.keys())
        if eksik:
            print(f"\n  📄 {dosya} — HİÇBİRİ YOK: {eksik}")

# ── 5. SPRINT 3 KONTROL ──────────────────────────────────────
print("\n[5] SPRINT 3 — OBSERVABILITY")
s3_dosyalar = [
    "structlog_config.py",
    "monitoring/metrics.py",
    "rol_yetki.py",
    "core/security/auth_manager.py",
    "safe_path.py",
    "core/security/fs_jail.py",
    "db_backup.py",
    "install.bat",
    "cache_manager.py",
]
for d in s3_dosyalar:
    var = "✅" if dosya_var(d) else "❌"
    satir = satir_say(d)
    satir_str = f"({satir} satır)" if satir > 0 else ""
    print(f"  {var} {d} {satir_str}")

s3_kontrol = {
    "structlog_config.py": ["structlog", "Prometheus", "Counter", "Histogram", "trace_id"],
    "rol_yetki.py": ["admin", "power_user", "basic", "ROLES", "check"],
    "safe_path.py": ["WORKSPACE", "resolve", "startswith", "PermissionError"],
}
for dosya, aranacaklar in s3_kontrol.items():
    sonuclar = icerik_ara(dosya, aranacaklar)
    bulunanlar = [a for a, v in sonuclar.items() if v]
    eksik = [a for a, v in sonuclar.items() if not v]
    if bulunanlar or eksik:
        print(f"\n  📄 {dosya}:")
        if bulunanlar:
            print(f"    ✅ var: {bulunanlar}")
        if eksik:
            print(f"    ❌ yok: {eksik}")

# ── 6. KLASÖR YAPISI ─────────────────────────────────────────
print("\n[6] KLASÖR YAPISI")
klasorler = ["core", "handlers", "services", "plugins", "tests", "monitoring", "rag", "memory_db"]
for k in klasorler:
    icerik = klasor_listele(k)
    if icerik:
        print(f"  📁 {k}/  ({len(icerik)} dosya)")
        for f in sorted(icerik)[:8]:
            print(f"    - {f}")
        if len(icerik) > 8:
            print(f"    ... ve {len(icerik)-8} dosya daha")
    else:
        print(f"  📁 {k}/  (boş veya yok)")

# ── 7. TELEGRAM_BOT ÖZET ─────────────────────────────────────
print("\n[7] TELEGRAM_BOT.PY ANALİZ")
kontrol = {
    "telegram_bot.py": [
        "from bot_config import",
        "from log_utils import",
        "guvenli_log_yaz",
        "CFG",
        "normalize_provider",
        "CircuitBreaker",
        "ToolResult",
        "trace_id",
        "from handlers",
        "from services",
        "token_budget",
        "structlog",
    ]
}
for dosya, aranacaklar in kontrol.items():
    print(f"  📄 {dosya} ({satir_say(dosya)} satır):")
    sonuclar = icerik_ara(dosya, aranacaklar)
    for a, var in sonuclar.items():
        print(f"    {'✅' if var else '❌'} {a}")

print(f"\n{SEP}")
print("RAPOR TAMAM — Bu çıktıyı Claude'a yapıştır.")
print(SEP)
