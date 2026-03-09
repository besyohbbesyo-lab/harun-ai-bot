# handlers/tool.py - Arac komutlari
# ara, pdf, kod, sunum, word, plan, hafiza, gonder, mkdir, mkfile, open

import asyncio
import json
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from core.decorators import gorev_kaydet, yetki_gerekli
from core.globals import (
    MASAUSTU,
    code_runner,
    doc_creator,
    memory,
    onay_kaydet,
    onay_mesaji_olustur,
    pdf_downloader,
    search_engine,
)
from core.utils import log_yaz, son_dosyayi_bul
from services.chat_service import ask_ai


@yetki_gerekli
async def ara_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        konu = " ".join(context.args)
        await update.message.reply_text(f"'{konu}' aranıyor...")
        content = search_engine.search_and_read(konu)
        if len(content) > 4000:
            content = content[:4000] + "..."
        await update.message.reply_text(f"Sonuc:\n\n{content}")
    else:
        await update.message.reply_text("Kullanim: /ara <konu>")


@yetki_gerekli
async def pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        konu = " ".join(context.args)
        await update.message.reply_text(f"'{konu}' icin PDF aranıyor...\n1-2 dakika surebilir...")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, pdf_downloader.download_pdfs, konu)
        gorev_kaydet(f"PDF indir: {konu}", result, "pdf")
        await update.message.reply_text(result + "\n\nGondermek icin: /gonder pdf")
    else:
        await update.message.reply_text("Kullanim: /pdf <konu>")


@yetki_gerekli
async def kod_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        aciklama = " ".join(context.args)
        await update.message.reply_text(f"'{aciklama}' kodu yaziliyor...")
        prompt = (
            f"Asagidaki aciklamaya gore Python kodu yaz:\n{aciklama}\n\n"
            "Sadece calisacak Python kodunu yaz, baska hicbir sey ekleme.\n"
            "Sadece standart kutuphaneleri kullan (tkinter, random, time, os, math).\n"
            "Kod hatasiz olmali."
        )
        kod = await ask_ai(prompt, gorev_turu="kod")
        dosya_adi = aciklama.replace(" ", "_")[:20]
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, code_runner.save_and_run, kod, dosya_adi)
        if result["basari"]:
            gorev_kaydet(f"Kod yaz: {aciklama}", "Basarili", "kod")
            await update.message.reply_text(
                f"Kod yazildi ve calistirildi!\nKonum: {result['filepath']}\n\nAlmak icin: /gonder kod"
            )
        else:
            await update.message.reply_text(f"Hata: {result['mesaj']}")
    else:
        await update.message.reply_text("Kullanim: /kod <aciklama>")


@yetki_gerekli
async def sunum_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        konu = " ".join(context.args)
        await update.message.reply_text(f"'{konu}' sunumu hazirlaniyor...\nBekleyin...")
        web_content = search_engine.search_and_read(konu)
        prompt = f"""'{konu}' konusunda 5 slaytlik sunum hazirla.
Bilgiler: {web_content}

Her slayt icin tam olarak bu formati kullan:
SLAYT1_BASLIK: baslik
SLAYT1_ICERIK: icerik
SLAYT2_BASLIK: baslik
SLAYT2_ICERIK: icerik
SLAYT3_BASLIK: baslik
SLAYT3_ICERIK: icerik
SLAYT4_BASLIK: baslik
SLAYT4_ICERIK: icerik
SLAYT5_BASLIK: baslik
SLAYT5_ICERIK: icerik

Turkce yaz. Her icerik en az 3 cumle olsun."""
        llama_response = await ask_ai(prompt, gorev_turu="sunum")
        slides = []
        current_slide = {}
        for line in llama_response.split("\n"):
            if "_BASLIK:" in line:
                if current_slide and "baslik" in current_slide:
                    slides.append(current_slide)
                current_slide = {"baslik": line.split("_BASLIK:")[-1].strip()}
            elif "_ICERIK:" in line:
                current_slide["icerik"] = line.split("_ICERIK:")[-1].strip()
        if current_slide and "baslik" in current_slide:
            slides.append(current_slide)
        if len(slides) < 3:
            basliklar = ["Giris", "Tarihce", "Gunumuzdeki Durum", "Onemli Gelismeler", "Sonuc"]
            slides = [
                {"baslik": basliklar[i], "icerik": llama_response[i * 300 : (i + 1) * 300]}
                for i in range(5)
            ]
        filepath = doc_creator.create_presentation(konu, slides)
        if "Hata" not in filepath:
            gorev_kaydet(f"Sunum hazirla: {konu}", f"Dosya: {filepath}", "sunum")
            await update.message.reply_text(
                f"Sunum hazirlandi!\nKonum: {filepath}\nSlayt sayisi: {len(slides)+1}\n\nAlmak icin: /gonder sunum"
            )
        else:
            await update.message.reply_text(f"Hata: {filepath}")
    else:
        await update.message.reply_text("Kullanim: /sunum <konu>")


@yetki_gerekli
async def word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        konu = " ".join(context.args)
        await update.message.reply_text(f"'{konu}' dokumani hazirlaniyor...")
        web_content = search_engine.search_and_read(konu)
        prompt = f"'{konu}' konusunda Turkce detayli rapor yaz. # ile baslik kullan. En az 5 bolum.\nBilgiler: {web_content}"
        content = await ask_ai(prompt, gorev_turu="word")
        filepath = doc_creator.create_word_document(konu, content)
        if "Hata" not in filepath:
            gorev_kaydet(f"Word hazirla: {konu}", f"Dosya: {filepath}", "word")
            await update.message.reply_text(
                f"Word dokuman hazirlandi!\nKonum: {filepath}\n\nAlmak icin: /gonder word"
            )
        else:
            await update.message.reply_text(f"Hata: {filepath}")
    else:
        await update.message.reply_text("Kullanim: /word <konu>")


@yetki_gerekli
async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "­şñû Canavar Mod — Agent Zinciri\n\n"
            "Kullanim: /plan <gorev>\n"
            "Ornek: /plan Python ile basit bir hesap makinesi yaz\n\n"
            "Yapilacaklar:\n"
            "— Gorevi adim adim planlar\n"
            "— Her adimi calistirip dogrular\n"
            "— Basarisiz adimlari tekrar dener\n"
            "— Sonunda detayli rapor uretir"
        )
        return

    gorev = " ".join(context.args)
    await update.message.reply_text(
        f"Canavar Mod baslatildi!\n\n"
        f"Gorev: {gorev}\n\n"
        f"Adimlar gerceklestikce bildirim gelecek..."
    )

    async def ilerleme(mesaj: str):
        try:
            await update.message.reply_text(mesaj)
        except Exception:
            pass

    try:
        sonuc = await planner.run(gorev, ilerleme)

        # Ozet mesaji
        ozet_mesaj = (
            f"Gorev tamamlandi!\n\n"
            f"Gorev: {gorev}\n"
            f"Basarili: {sonuc.get('basarili', '?')}/{len(sonuc.get('adimlar', []))} adim\n"
            f"Sure: {sonuc.get('sure_s', '?')}s\n\n"
            f"Ozet:\n{sonuc['ozet']}"
        )
        if len(ozet_mesaj) > 4000:
            ozet_mesaj = ozet_mesaj[:3997] + "..."
        await update.message.reply_text(ozet_mesaj)

        # Detayli rapor (ayri mesaj)
        rapor = sonuc.get("rapor", "")
        if rapor:
            # Telegram 4096 char siniri
            for i in range(0, min(len(rapor), 8000), 4000):
                parca = rapor[i : i + 4000]
                if parca.strip():
                    await update.message.reply_text(parca)

    except Exception as e:
        await update.message.reply_text(f"Planner hatasi: {e}")


@yetki_gerekli
async def hafiza_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].lower() == "temizle":
        sonuc = memory.hafizayi_temizle("gorevler")
        await update.message.reply_text(sonuc)
    else:
        ozet = memory.hafiza_ozeti()
        tercihler = memory.tum_tercihleri_al()
        mesaj = ozet
        if tercihler:
            mesaj += "\n\nKayitli tercihler:\n"
            for k, v in tercihler.items():
                mesaj += f"- {k}: {v}\n"
        await update.message.reply_text(mesaj)


@yetki_gerekli
async def hatirlat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        bilgi = " ".join(context.args)
        basari = memory.bilgi_kaydet("kullanici_notu", bilgi)
        if basari:
            await update.message.reply_text(f"Hafizaya kaydedildi: {bilgi}")
        else:
            await update.message.reply_text("Kayit sirasinda hata olustu.")
    else:
        await update.message.reply_text("Kullanim: /hatirlat <bilgi>")


@yetki_gerekli
async def gonder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Kullanim:\n/gonder word\n/gonder sunum\n/gonder pdf\n/gonder kod\n/gonder test\n/gonder egitim"
        )
        return
    tur = context.args[0].lower()
    uzanti_map = {
        "word": "docx",
        "sunum": "pptx",
        "pdf": "pdf",
        "kod": "py",
        "test": "json",
        "egitim": "json",
    }
    if tur not in uzanti_map:
        await update.message.reply_text("word, sunum, pdf, kod, test veya egitim yazin.")
        return
    dosya = son_dosyayi_bul(MASAUSTU, uzanti_map[tur])
    if not dosya:
        await update.message.reply_text(f"Hic {tur} dosyasi bulunamadi!")
        return
    await update.message.reply_text(f"Gonderiliyor: {dosya.name}")
    try:
        with open(dosya, "rb") as f:
            await update.message.reply_document(document=f, filename=dosya.name)
    except Exception as e:
        await update.message.reply_text(f"Gonderme hatasi: {e}")


@yetki_gerekli
async def mkdir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanim: /mkdir <path>")
        return
    arguman = " ".join(context.args)
    user_id = update.message.chat_id
    # Onay mekanizmasi
    onay_kaydet(user_id, "mkdir", arguman)
    await update.message.reply_text(onay_mesaji_olustur("mkdir", arguman))


@yetki_gerekli
async def mkfile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        path = " ".join(context.args)
        user_id = update.message.chat_id
        onay_kaydet(user_id, "mkfile", path)
        await update.message.reply_text(onay_mesaji_olustur("mkfile", path))
    else:
        await update.message.reply_text("Kullanim: /mkfile <path>")


@yetki_gerekli
async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        program = context.args[0]
        user_id = update.message.chat_id
        onay_kaydet(user_id, "open", program)
        await update.message.reply_text(onay_mesaji_olustur("open", program))
    else:
        await update.message.reply_text("Kullanim: /open <program>")
