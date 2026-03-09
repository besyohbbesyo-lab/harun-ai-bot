# handlers/admin.py - Yonetim komutlari
# start, help, status, guvenlik, selftest, api, aee, egitim_*

import asyncio
import json
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from core.globals import (
    VISION_AKTIF,
    EgitimToplayici,
    code_runner,
    egitim,
    egitim_store,
    guvenlik_ozeti,
    memory,
    model_mgr,
    policy,
    prompt_evo,
    reward_sys,
    rotator,
    run_selftests,
    strategy_mgr,
    supervisor,
    write_report,
)
from core.utils import log_yaz
from handlers.message import _yetki_kontrol
from services.chat_service import ab_prompt_testini_hazirla, ask_ai
from token_budget import budget

try:
    from monitoring.metrics import metrics as _metrics

    _METRICS_AKTIF = True
except Exception:
    _metrics = None
    _METRICS_AKTIF = False

try:
    from core.ab_testing import kullaniciyi_varyanta_zorla, tum_testler_istatistik

    _AB_AKTIF = True
except Exception:
    tum_testler_istatistik = None
    kullaniciyi_varyanta_zorla = None
    _AB_AKTIF = False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Harun AI Bot aktif!\n\n"
        "/help - Tum komutlar\n"
        "/status - Sistem durumu\n"
        "/abtest - A/B test istatistiklerini goster\n"
        "/ab_force <test> <varyant> [user_id] - Kullaniciyi varyanta zorla"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    vision_durum = "Aktif" if VISION_AKTIF else "Devre disi"
    await update.message.reply_text(
        "Harun AI Bot Komutlari:\n\n"
        "/guncel <konu> - Guncel haber ve bilgi ara\n"
        "/aee - AI evolution engine durumu\n"
        "/tikla <x> <y> - Mouse tikla\n"
        "/yaz <metin> - Klavye ile yaz\n"
        "/tus <tus> - Tus bas (enter, ctrl+c vb)\n"
        "/web <url> - Tarayicida ac\n"
        "/otomasyon <gorev> - Akilli otomasyon\n"
        "/plan <gorev> - Gorevi planla ve calistir\n"
        f"/ekran [soru] - Ekran analiz et (Vision: {vision_durum})\n"
        "/sunum <konu> - Gorselli sunum hazirla\n"
        "/word <konu> - Word dokuman hazirla\n"
        "/pdf <konu> - PDF ara ve indir\n"
        "/kod <aciklama> - Kod yaz ve calistir\n"
        "/ara <konu> - Internette ara\n"
        "/gonder word|sunum|pdf|kod - Dosya gonder\n"
        "/hatirlat <bilgi> - Hafizaya bilgi kaydet\n"
        "/hafiza - Hafiza durumunu goster\n"
        "/mkdir <path> - Klasor olustur\n"
        "/mkfile <path> - Dosya olustur\n"
        "/open <program> - Program ac\n"
        "/chat <mesaj> - AI ile konus\n"
        "/api - API rotasyon durumu\n"
        "/egitim - Fine-tuning baslat\n"
        "/egitim_stats - Egitim store istatistikleri\n"
        "/egitim_incele - Onay bekleyen kayitlari goster\n"
        "/egitim_onayla <id> - Kayit onayla (veya: toplu 10)\n"
        "/egitim_reddet <id> - Kayit reddet\n"
        "/egitim_export - Onaylanan kayitlari JSONL export et\n"
        "/egitimrapor - Egitim raporu uret\n"
        "/status - Sistem durumu\n"
        "/abtest - A/B test istatistiklerini goster\n"
        "/ab_force <test> <varyant> [user_id] - Kullaniciyi varyanta zorla"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    hafiza_ozet = memory.hafiza_ozeti()
    vision_durum = "Aktif (LLaVA)" if VISION_AKTIF else "Devre disi"
    # Uptime hesapla
    import core.globals as _g

    uptime_str = _g.uptime_hesapla()
    await update.message.reply_text(
        "Groq LLaMA 3.3 70B: Aktif\n"
        "Lokal GLM-4.6V-Flash-9B: Yedek\n"
        "Sunum/Dokuman: Aktif\n"
        "DuckDuckGo Arama: Aktif\n"
        "PDF Indirici: Aktif\n"
        "Kod Yazici: Aktif\n"
        "Dosya Gonderici: Aktif\n"
        "Hafiza (ChromaDB): Aktif\n"
        "Planner/Executor: Aktif\n"
        f"Vision: {vision_durum}\n"
        f"Uptime: {uptime_str}\n\n"
        f"{hafiza_ozet}\n\n{rotator.durum_ozeti()}\n\n{budget.durum_ozeti()}\n\n{policy.ozet()}"
        + (f"\n\n{_metrics.ozet_metni()}" if _METRICS_AKTIF and _metrics else "")
        + (f"\n\n{_abtest_ozet_metni()}" if _AB_AKTIF else "")
    )


# ... rest of file omitted for brevity in patch generation? no, include all functions needed ...
def _abtest_ozet_metni() -> str:
    """A/B testleri icin okunabilir ozet metni uret."""
    if not _AB_AKTIF or tum_testler_istatistik is None:
        return "A/B Testing modulu aktif degil."

    try:
        tumu = tum_testler_istatistik() or {}
    except Exception as e:
        return f"A/B istatistik hatasi: {e}"

    if not tumu:
        return "A/B test kaydi yok."

    satirlar = ["A/B Test Ozeti:"]
    for test_adi, ist in sorted(tumu.items()):
        toplam = int((ist or {}).get("toplam_sonuc", 0))
        satirlar.append(f"\n[{test_adi}] toplam sonuc: {toplam}")
        varyantlar = (ist or {}).get("varyantlar", {}) or {}
        if not varyantlar:
            satirlar.append("  - varyant yok")
            continue
        for varyant_adi, v in varyantlar.items():
            satirlar.append(
                f"  - {varyant_adi}: toplam={int(v.get('toplam', 0))}, "
                f"basari=%{v.get('basari_orani', 0.0) * 100:.1f}, "
                f"ort={v.get('ort_sure_ms', 0.0):.1f}ms"
            )
    return "\n".join(satirlar)


async def abtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    await update.message.reply_text(_abtest_ozet_metni())


async def ab_force_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    if not _AB_AKTIF or kullaniciyi_varyanta_zorla is None:
        await update.message.reply_text("A/B Testing modulu aktif degil.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Kullanim: /ab_force <test_adi> <varyant_adi> [user_id]")
        return

    test_adi = context.args[0].strip()
    varyant_adi = context.args[1].strip()
    hedef_user_id = (
        context.args[2].strip() if len(context.args) >= 3 else str(update.message.from_user.id)
    )

    try:
        if test_adi == "yanit_stili_v1":
            ab_prompt_testini_hazirla()
        kullaniciyi_varyanta_zorla(test_adi, hedef_user_id, varyant_adi)
        await update.message.reply_text(
            f"A/B varyant zorlamasi tamam.\n"
            f"Test: {test_adi}\n"
            f"Varyant: {varyant_adi}\n"
            f"User: {hedef_user_id}"
        )
    except Exception as e:
        await update.message.reply_text(f"A/B force hatasi: {e}")


async def guvenlik_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    await update.message.reply_text(guvenlik_ozeti())


async def selftest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    await update.message.reply_text("Selftest basliyor... (yaklasik 10-30 sn)")
    loop = asyncio.get_running_loop()
    try:
        report = await loop.run_in_executor(None, run_selftests, code_runner)
        report_path = write_report(report)
        passed = sum(1 for t in report["tests"] if t["pass"])
        total = len(report["tests"])
        lines = [
            f"Selftest bitti: {passed}/{total} basarili",
            "",
        ]
        for t in report["tests"]:
            status = "OK" if t["pass"] else "FAIL"
            lines.append(f"- {status}: {t['name']} ({t.get('ms', 0)} ms)")
            if not t["pass"]:
                lines.append(f"  Sebep: {t.get('detail','')[:200]}")
        lines.append("")
        lines.append(f"Rapor: {report_path}")
        lines.append("Indirmek icin: /gonder test")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Selftest hatasi: {e}")


async def api_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    """Asama 25: Tum Groq key'lerini kisa bir istekte test eder ve raporlar.

    Not: Groq client senkron oldugu icin executor icinde calistiriyoruz.
    """
    await update.message.reply_text("API test basliyor... (her key icin kisa istek)")

    test_prompt = "Sadece 'ok' yaz."

    async def _tek_key_test(api_key: str):
        def _run():
            import time as _t

            from groq import Groq as _Groq

            c = _Groq(api_key=api_key)
            t0 = _t.perf_counter()
            try:
                r = c.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=10,
                    temperature=0,
                )
                t1 = _t.perf_counter()
                out = (r.choices[0].message.content or "").strip()
                return True, (t1 - t0) * 1000.0, out
            except Exception as e:
                t1 = _t.perf_counter()
                return False, (t1 - t0) * 1000.0, str(e)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run)

    try:
        key_states = getattr(rotator, "_keys", [])
        keys = [ks.key for ks in key_states]
    except Exception:
        keys = []

    if not keys:
        await update.message.reply_text("Hata: Test edilecek key bulunamadi.")
        return

    satirlar = []
    for idx, k in enumerate(keys, 1):
        ok, ms, msg = await _tek_key_test(k)
        if ok:
            try:
                rotator._active_idx = idx - 1
                rotator.basari_kaydet("Groq", latency_ms=ms)
            except Exception:
                pass
            satirlar.append(f"key#{idx}: OK | {ms:.0f}ms | cevap='{msg[:20]}'")
        else:
            try:
                rotator._active_idx = idx - 1
                rotator.hata_kaydet("Groq", msg, cooldown_s=60)
            except Exception:
                pass
            satirlar.append(f"key#{idx}: HATA | {ms:.0f}ms | {msg[:120]}")

    await update.message.reply_text("API Test Sonucu:\n" + "\n".join(satirlar))


async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    await update.message.reply_text(rotator.durum_ozeti())


async def aee_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    hata_ozet = ""
    try:
        hata_stats = egitim.hata_istatistigi()
        if hata_stats:
            en_cok = list(hata_stats.items())[:3]
            hata_satirlari = "\n".join(f"  {t}: {s} hata" for t, s in en_cok)
            toplam_hata = sum(hata_stats.values())
            hata_ozet = f"\n\n[!] Basarisiz Yanitlar:\nToplam: {toplam_hata}\n{hata_satirlari}"
        else:
            hata_ozet = "\n\n[OK] Kayitli hata yok."
    except Exception:
        pass

    mesaj = (
        "AEE - Autonomous Evolution Engine\n\n"
        f"{policy.ozet()}\n\n"
        f"{reward_sys.ozet()}\n\n"
        f"{strategy_mgr.ozet()}\n\n"
        f"{supervisor.ozet()}\n\n"
        f"{prompt_evo.ozet()}\n\n"
        f"{rotator.durum_ozeti()}\n\n"
        f"{model_mgr.ozet()}"
        f"{hata_ozet}"
    )
    await update.message.reply_text(mesaj)


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    if context.args:
        mesaj = " ".join(context.args)
        await update.message.reply_text("Dusunuyorum...")
        try:
            response = await ask_ai(
                mesaj, gorev_turu="sohbet", kullanici_id=update.message.from_user.id
            )
            if not response:
                await update.message.reply_text("Yanit uretilemedi.")
                return
            memory.gorev_kaydet(
                mesaj[:100], response[:200], "sohbet", reward=reward_sys.son_smoothed(), basari=True
            )
            if len(response) > 4000:
                for i in range(0, len(response), 4000):
                    await update.message.reply_text(response[i : i + 4000])
            else:
                await update.message.reply_text(response)
        except Exception as e:
            print(f"[chat_command] Hata: {e}")
            await update.message.reply_text(f"Hata: {e}")
    else:
        await update.message.reply_text("Kullanim: /chat <mesaj>")


async def egitimrapor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    try:
        toplayici = EgitimToplayici()
        rapor_path = toplayici.rapor_kaydet(masaustu=True, son_n=50)
        await update.message.reply_text(
            "Eğitim raporu üretildi!\n" f"Konum: {rapor_path}\n" "İndirmek için: /gonder egitim"
        )
    except Exception as e:
        await update.message.reply_text(f"Hata: Eğitim raporu üretilemedi: {e}")


async def egitim_incele_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    try:
        rows = egitim_store.listele_reward(status="PENDING_REVIEW", limit=10)
        if not rows:
            stats = egitim_store.stats()
            yeni = stats.get("NEW", 0)
            await update.message.reply_text(
                f"Onay bekleyen kayıt yok.\n"
                f"NEW kayıt sayısı: {yeni}\n"
                f"(Her {50} yeni kayıtta otomatik incelemeye alınır)"
            )
            return

        lines = [f"Onay Bekleyen Kayıtlar ({len(rows)} adet, reward'a göre):\n"]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"{i}. [{r['smoothed_reward']:.2f}] {r['gorev_turu']} | "
                f"{(r['prompt_preview'] or '')[:80]}\n"
                f"   ID: {r['id']}"
            )
        lines.append("\nOnaylamak: /egitim_onayla <ID> veya /egitim_onayla toplu 10")
        lines.append("Reddetmek: /egitim_reddet <ID>")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")


async def egitim_onayla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Kullanim:\n"
            "/egitim_onayla <kayit_id>\n"
            "/egitim_onayla toplu 10  (en iyi 10 kaydi onayla)"
        )
        return

    actor = {
        "user_id": update.message.from_user.id,
        "username": update.message.from_user.username or "",
    }

    try:
        if context.args[0].lower() == "toplu":
            n = int(context.args[1]) if len(context.args) > 1 else 10
            n = min(n, 50)
            sonuc = egitim_store.onayla_toplu(n, actor)
            await update.message.reply_text(
                f"Toplu Onay Tamamlandi!\n"
                f"Onaylanan: {sonuc['count']} kayit\n"
                f"Export icin: /egitim_export"
            )
        else:
            rid = context.args[0].strip()
            sonuc = egitim_store.status_degistir(rid, "APPROVED", actor)
            if sonuc["ok"]:
                await update.message.reply_text(f"Kayit onaylandi: {rid[:16]}...")
            else:
                await update.message.reply_text(f"Hata: {sonuc.get('error', 'Bilinmiyor')}")
    except Exception as e:
        await update.message.reply_text(f"Onay hatasi: {e}")


async def egitim_reddet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    if not context.args:
        await update.message.reply_text("Kullanim: /egitim_reddet <kayit_id>")
        return

    actor = {
        "user_id": update.message.from_user.id,
        "username": update.message.from_user.username or "",
    }
    rid = context.args[0].strip()
    try:
        sonuc = egitim_store.status_degistir(rid, "REJECTED", actor)
        if sonuc["ok"]:
            await update.message.reply_text(f"Kayit reddedildi: {rid[:16]}...")
        else:
            await update.message.reply_text(f"Hata: {sonuc.get('error', 'Bilinmiyor')}")
    except Exception as e:
        await update.message.reply_text(f"Red hatasi: {e}")


async def egitim_export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    await update.message.reply_text("Export basliyor...")
    try:
        sonuc = egitim_store.export_approved()
        if sonuc["count"] == 0:
            await update.message.reply_text(
                "Export edilecek APPROVED kayit yok.\n" "Once /egitim_incele ile kayitlari onayla."
            )
            return

        await update.message.reply_text(
            f"Export Tamamlandi!\n"
            f"Onaylanan kayit: {sonuc['count']}\n"
            f"prompt/completion: {Path(sonuc['prompt_completion']).name}\n"
            f"messages: {Path(sonuc['messages']).name}\n\n"
            f"Dosyalari gondermek icin /gonder egitim"
        )
        for fpath in [sonuc["prompt_completion"], sonuc["messages"]]:
            try:
                with open(fpath, "rb") as f:
                    await update.message.reply_document(document=f, filename=Path(fpath).name)
            except Exception:
                pass
    except Exception as e:
        await update.message.reply_text(f"Export hatasi: {e}")


async def egitim_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    try:
        stats = egitim_store.stats()
        rapor = egitim_store.rapor()
        lines = [
            "Egitim Store Durumu (Asama 21):\n",
            f"NEW (bekliyor): {stats.get('NEW', 0)}",
            f"PENDING_REVIEW (inceleme): {stats.get('PENDING_REVIEW', 0)}",
            f"APPROVED (onaylı): {stats.get('APPROVED', 0)}",
            f"REJECTED (reddedildi): {stats.get('REJECTED', 0)}",
            f"TOPLAM: {stats.get('TOTAL', 0)}",
            "",
            "Ortalama Reward (primary):",
        ]
        for st, avg in (rapor.get("avg_reward") or {}).items():
            lines.append(f"  {st}: {avg}")

        av1 = rapor.get("avg_reward_v1") or {}
        av2 = rapor.get("avg_reward_v2") or {}
        if any(v != 0.0 for v in av1.values()):
            lines.append("")
            lines.append("Ortalama Reward v1:")
            for st, avg in av1.items():
                lines.append(f"  {st}: {avg}")
        if any(v != 0.0 for v in av2.values()):
            lines.append("")
            lines.append("Ortalama Reward v2:")
            for st, avg in av2.items():
                lines.append(f"  {st}: {avg}")
        lines.append("\n/egitim_incele ile kayitlari gozden gecir")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")


async def finetuning_baslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    finetuning_onay_bekliyor = False
    await update.message.reply_text("Fine-tuning baslatildi...")


async def metrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _yetki_kontrol(update):
        return
    try:
        if _METRICS_AKTIF and _metrics:
            await update.message.reply_text(_metrics.ozet_metni(), parse_mode="Markdown")
        else:
            await update.message.reply_text("Metrics modülü aktif değil.")
    except Exception as e:
        await update.message.reply_text(f"Metrics hatası: {e}")
