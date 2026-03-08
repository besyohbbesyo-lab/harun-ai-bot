# telegram_bot.py — Sprint 5 refactored
# globals import* kaldirildi, explicit importlar eklendi
# S5-5: Exponential Backoff entegre edildi

from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from core.bot_init import memory

# ── Core modüller (globals.py yerine direkt) ──────────────────
from core.config import LOG_DOSYASI, TOKEN, baslangic_zamanini_kaydet
from core.utils import log_yaz, set_log_dosyasi
from egitim_plugin import bot_app_kaydet, egitim_command

# ── Handler modülleri ─────────────────────────────────────────
from handlers.admin import (
    ab_force_command,
    abtest_command,
    aee_command,
    api_command,
    api_test_command,
    chat_command,
    egitim_export_command,
    egitim_incele_command,
    egitim_onayla_command,
    egitim_reddet_command,
    egitim_stats_command,
    egitimrapor_command,
    guvenlik_command,
    help_command,
    metrics_command,
    selftest_command,
    start,
    status_command,
)
from handlers.message import handle_message, sesli_mesaj_handler
from handlers.pc import (
    ekran_command,
    guncel_command,
    otomasyon_command,
    tikla_command,
    tus_command,
    web_command,
    yaz_command,
)
from handlers.tool import (
    ara_command,
    gonder_command,
    hafiza_command,
    hatirlat_command,
    kod_command,
    mkdir_command,
    mkfile_command,
    open_command,
    pdf_command,
    plan_command,
    sunum_command,
    word_command,
)
from proaktif_zeka import (
    ayar_yukle,
    haftalik_rapor_gonder,
    proaktif_oneri_gonder,
    sabah_ozeti_gonder,
)
from services.chat_service import ab_prompt_testini_hazirla

set_log_dosyasi(LOG_DOSYASI)


def komut_listesini_olustur():
    """Telegram komut/handler listesini tek yerden uretir.

    Not: /ab_force komutu her zaman kayit edilir. Guvenlik karari
    handler icinde verilir; debug kapaliyken kullaniciya acikca
    reddedildi mesaji doner.
    """
    return [
        ("start", start),
        ("help", help_command),
        ("status", status_command),
        ("abtest", abtest_command),
        ("ab_force", ab_force_command),
        ("api", api_command),
        ("api_test", api_test_command),
        ("aee", aee_command),
        ("guncel", guncel_command),
        ("tikla", tikla_command),
        ("yaz", yaz_command),
        ("tus", tus_command),
        ("web", web_command),
        ("otomasyon", otomasyon_command),
        ("plan", plan_command),
        ("ekran", ekran_command),
        ("mkdir", mkdir_command),
        ("mkfile", mkfile_command),
        ("open", open_command),
        ("ara", ara_command),
        ("pdf", pdf_command),
        ("gonder", gonder_command),
        ("kod", kod_command),
        ("selftest", selftest_command),
        ("sunum", sunum_command),
        ("word", word_command),
        ("chat", chat_command),
        ("hatirlat", hatirlat_command),
        ("hafiza", hafiza_command),
        ("egitim", egitim_command),
        ("egitimrapor", egitimrapor_command),
        ("egitim_incele", egitim_incele_command),
        ("egitim_onayla", egitim_onayla_command),
        ("egitim_reddet", egitim_reddet_command),
        ("egitim_export", egitim_export_command),
        ("egitim_stats", egitim_stats_command),
        ("guvenlik", guvenlik_command),
        ("metrics", metrics_command),
    ]


def main():
    if not TOKEN:
        print("HATA: TELEGRAM_TOKEN tanimlanmamis!")
        print("  1) .env.example dosyasini .env olarak kopyala")
        print("  2) .env icine gercek token'ini yaz")
        print("  3) Botu yeniden baslat")
        return

    print("Telegram Bot baslatiliyor...")
    print("Groq LLaMA 3.3 70B baglanıyor...")
    print("Lokal GLM-4.6V-Flash-9B yedek olarak hazirlaniyor...")
    print("Dokuman sistemi hazirlaniyor...")
    print("DuckDuckGo arama hazirlaniyor...")
    print("PDF indirici hazirlaniyor...")
    print("Kod yazici hazirlaniyor...")
    print("Dosya gonderici hazirlaniyor...")
    print("Hafiza sistemi (ChromaDB) hazirlaniyor...")
    print("Planner/Executor hazirlaniyor...")
    print("AEE (Autonomous Evolution Engine) hazirlaniyor...")
    print("Meta-Supervisor hazirlaniyor...")
    print("Prompt Evolution sistemi hazirlaniyor...")
    print("API Rotasyon sistemi hazirlaniyor (Gemini->Groq)...")
    print("Model Yoneticisi hazirlaniyor (Basit->Lokal | Karmasik->Cloud)...")

    memory.decay_uygula()

    # A/B prompt testini startup'ta hazirla
    try:
        ab_prompt_testini_hazirla()
        print("[AB] yanit_stili_v1 varyantlari hazirlandi")
    except Exception as e:
        print(f"[AB] startup hazirlama hatasi: {e}")

    # Prometheus metrics endpoint
    try:
        from monitoring.metrics import _prom_yukle, metrics

        if _prom_yukle():
            metrics.prometheus_baslat(port=8001)
            print("[Prometheus] Metrics endpoint: http://localhost:8001/metrics")
        else:
            print("[Prometheus] prometheus_client yuklu degil, atlaniyor")
    except Exception as e:
        print(f"[Prometheus] Baslama hatasi: {e}")

    # Baslangic yedegi
    try:
        from db_backup import yedek_al

        yedek_al()
    except Exception as e:
        print(f"[Backup] Baslangic yedegi hatasi: {e}")

    # S5-5: Backoff modülü yüklendi
    try:
        from core.backoff import guvenli_api_cagri  # noqa: F401

        print("[Backoff] Exponential backoff aktif (alpha=2, max=300s, jitter)")
    except Exception as e:
        print(f"[Backoff] Yuklenemedi: {e}")

    application = Application.builder().token(TOKEN).build()
    komutlar = komut_listesini_olustur()

    for komut, handler in komutlar:
        application.add_handler(CommandHandler(komut, handler))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, sesli_mesaj_handler))
    print("Sesli Mesaj Destegi (Google STT): Aktif")

    baslangic_zamanini_kaydet()
    log_yaz("Bot baslatildi")
    print("Bot hazir! Telegram'dan mesaj yazabilirsin.")
    bot_app_kaydet(application)

    # Proaktif görevler — 30 dakikada bir
    async def _proaktif_kontrol(context):
        ayar = ayar_yukle()
        chat_id = ayar.get("chat_id")
        if not chat_id:
            return
        saat = datetime.now().hour
        dakika = datetime.now().minute
        if saat == 8 and dakika < 30:
            await sabah_ozeti_gonder(context.bot, chat_id)
        if datetime.now().weekday() == 0 and saat == 9 and dakika < 30:
            await haftalik_rapor_gonder(context.bot, chat_id)
        await proaktif_oneri_gonder(context.bot, chat_id)

    jq = application.job_queue
    if jq:
        jq.run_repeating(_proaktif_kontrol, interval=1800, first=60)
        print("[ProaktifZeka] Scheduler baslatildi (30dk aralik)")

        from memory_plugin import etm as _etm

        async def _etm_consolidate(context):
            try:
                tasinan = _etm.consolidate(memory)
                if tasinan > 0:
                    print(f"[ETM] {tasinan} kayit LTM'ye tasinildi")
            except Exception as e:
                print(f"[ETM] Consolidation hatasi: {e}")

        jq.run_repeating(_etm_consolidate, interval=7200, first=300)
        print("[ETM] Consolidation scheduler baslatildi (2s aralik)")

        from db_backup import periyodik_yedek

        jq.run_repeating(periyodik_yedek, interval=3600, first=600)
        print("[Backup] Yedekleme scheduler baslatildi (gece 03:00)")
    else:
        print("[ProaktifZeka] job_queue bulunamadi, scheduler devre disi")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
